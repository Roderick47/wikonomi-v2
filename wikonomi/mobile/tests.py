"""Regression checks for mobile contribution safety and publication."""
import io
import tempfile
import uuid
from decimal import Decimal

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.models import Business, BusinessBranch, PriceReport, Product
from mobile.models import MobileSubmission
from mobile.services import approve_submission, reject_submission

User = get_user_model()


def photo_file():
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(buffer, "PNG")
    return SimpleUploadedFile("shelf.png", buffer.getvalue(), content_type="image/png")


class MobileContributionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.contributor = User.objects.create_user(username="contributor", password="test-pass")
        cls.reviewer = User.objects.create_user(username="reviewer", password="test-pass", is_staff=True)
        cls.product = Product.objects.create(name="Rice 1kg", slug="rice-1kg")
        cls.business = Business.objects.create(name="Test Grocery", slug="test-grocery")
        cls.branch = BusinessBranch.objects.create(
            canonical_business=cls.business, name="Main", slug="main",
            latitude=-9.46, longitude=147.16,
        )

    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        media_override = override_settings(MEDIA_ROOT=self.media.name)
        media_override.enable()
        self.addCleanup(media_override.disable)

    def payload(self, identifier=None):
        return {
            "product": self.product.pk,
            "business_branch": self.branch.pk,
            "price": "12.50",
            "client_submission_id": str(identifier or uuid.uuid4()),
            "photo": photo_file(),
        }

    def test_authentication_required(self):
        response = self.client.get(reverse("mobile:home"))
        self.assertEqual(response.status_code, 302)

    def test_mobile_submit_remains_pending_until_review(self):
        self.client.force_login(self.contributor)
        response = self.client.post(reverse("mobile:submit"), self.payload())
        self.assertEqual(response.status_code, 302)
        submission = MobileSubmission.objects.get()
        self.assertEqual(submission.status, MobileSubmission.Status.PENDING)
        self.assertEqual(PriceReport.objects.count(), 0)

        report = approve_submission(submission.pk, self.reviewer)
        self.assertEqual(report.price, Decimal("12.50"))
        self.assertEqual(report.user_id, self.contributor.pk)
        self.assertEqual(report.business_branch_id, self.branch.pk)
        submission.refresh_from_db()
        self.assertEqual(submission.status, MobileSubmission.Status.APPROVED)
        self.assertEqual(submission.published_report_id, report.pk)

    def test_duplicate_submission_id_does_not_create_more_records(self):
        identifier = uuid.uuid4()
        self.client.force_login(self.contributor)
        self.client.post(reverse("mobile:submit"), self.payload(identifier))
        self.client.post(reverse("mobile:submit"), self.payload(identifier))
        self.assertEqual(MobileSubmission.objects.count(), 1)

    def test_approval_is_idempotent(self):
        self.client.force_login(self.contributor)
        self.client.post(reverse("mobile:submit"), self.payload())
        submission = MobileSubmission.objects.get()
        self.assertIsNotNone(approve_submission(submission.pk, self.reviewer))
        self.assertIsNone(approve_submission(submission.pk, self.reviewer))
        self.assertEqual(PriceReport.objects.count(), 1)

    def test_rejection_keeps_report_unpublished(self):
        self.client.force_login(self.contributor)
        self.client.post(reverse("mobile:submit"), self.payload())
        submission = MobileSubmission.objects.get()
        self.assertTrue(reject_submission(submission.pk, self.reviewer))
        self.assertEqual(PriceReport.objects.count(), 0)
        self.assertIsNone(approve_submission(submission.pk, self.reviewer))

    def test_search_requires_login(self):
        for name in ("search_products", "search_branches"):
            response = self.client.get(reverse("mobile:" + name), {"q": "rice"})
            self.assertEqual(response.status_code, 302)

    def test_negative_and_zero_prices_are_rejected(self):
        self.client.force_login(self.contributor)
        for value in ("0", "-0.50"):
            with self.subTest(price=value):
                payload = self.payload()
                payload["price"] = value
                response = self.client.post(reverse("mobile:submit"), payload)
                self.assertEqual(response.status_code, 200)
        self.assertEqual(MobileSubmission.objects.count(), 0)

    def test_non_image_evidence_is_rejected(self):
        self.client.force_login(self.contributor)
        payload = self.payload()
        payload["photo"] = SimpleUploadedFile(
            "fake.png", b"not an actual image", content_type="image/png"
        )
        self.assertEqual(self.client.post(reverse("mobile:submit"), payload).status_code, 200)
        self.assertEqual(MobileSubmission.objects.count(), 0)

    def test_normal_user_cannot_approve_or_reject(self):
        self.client.force_login(self.contributor)
        self.client.post(reverse("mobile:submit"), self.payload())
        submission = MobileSubmission.objects.get()
        with self.assertRaises(PermissionDenied):
            approve_submission(submission.pk, self.contributor)
        with self.assertRaises(PermissionDenied):
            reject_submission(submission.pk, self.contributor)
        self.assertEqual(PriceReport.objects.count(), 0)

    def test_hourly_limit_rejects_21st_submission(self):
        self.client.force_login(self.contributor)
        MobileSubmission.objects.bulk_create([
            MobileSubmission(
                client_submission_id=uuid.uuid4(), contributor=self.contributor,
                product=self.product, business_branch=self.branch,
                price=Decimal("2.50"), photo="test.jpg",
            ) for _ in range(20)
        ])
        response = self.client.post(reverse("mobile:submit"), self.payload())
        self.assertEqual(response.status_code, 429)
        self.assertEqual(MobileSubmission.objects.count(), 20)

    def test_photo_evidence_survives_review_and_publishes_with_same_bytes(self):
        """HTTP upload -> pending evidence file -> approval -> published image."""
        self.client.force_login(self.contributor)
        response = self.client.post(reverse("mobile:submit"), self.payload())
        self.assertEqual(response.status_code, 302)
        pending = MobileSubmission.objects.get()
        with pending.photo.open("rb") as image:
            original_bytes = image.read()
        self.assertTrue(original_bytes.startswith(b"\\x89PNG"))

        report = approve_submission(pending.pk, self.reviewer)
        self.assertIsNotNone(report)
        report.refresh_from_db()
        self.assertEqual(report.image.name, pending.photo.name)
        with report.image.open("rb") as published_image:
            self.assertEqual(published_image.read(), original_bytes)
        self.assertEqual(PriceReport.objects.count(), 1)

    def test_product_and_branch_search_return_existing_entities(self):
        self.client.force_login(self.contributor)
        product_results = self.client.get(
            reverse("mobile:search_products"), {"q": "Rice"}
        ).json()["results"]
        branch_results = self.client.get(
            reverse("mobile:search_branches"), {"q": "Grocery"}
        ).json()["results"]
        self.assertIn(self.product.pk, [row["id"] for row in product_results])
        self.assertIn(self.branch.pk, [row["id"] for row in branch_results])

    def test_mobile_form_requires_csrf_token(self):
        guarded_client = Client(enforce_csrf_checks=True)
        guarded_client.force_login(self.contributor)
        response = guarded_client.post(
            reverse("mobile:submit"), self.payload()
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(MobileSubmission.objects.count(), 0)

    def test_cannot_reuse_another_users_submission_id(self):
        self.client.force_login(self.contributor)
        submission_id = uuid.uuid4()
        self.client.post(reverse("mobile:submit"), self.payload(submission_id))
        another = User.objects.create_user(username="other", password="test-pass")
        self.client.force_login(another)
        response = self.client.post(
            reverse("mobile:submit"), self.payload(submission_id)
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(MobileSubmission.objects.count(), 1)
