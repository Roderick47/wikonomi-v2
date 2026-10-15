"""Regression checks for mobile contribution safety and publication."""
import io
import tempfile
import uuid
from decimal import Decimal

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
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
