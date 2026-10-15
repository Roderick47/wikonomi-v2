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
        self.assertTrue(original_bytes.startswith(bytes((0x89, 0x50, 0x4e, 0x47))))

        report = approve_submission(pending.pk, self.reviewer)
        self.assertIsNotNone(report)
        report.refresh_from_db()
        # V2's ResizedImageField produces a separate JPEG for the published
        # report; the original PNG remains retained as review evidence.
        self.assertNotEqual(report.image.name, pending.photo.name)
        with report.image.open("rb") as published_image:
            with Image.open(published_image) as decoded:
                self.assertEqual(decoded.size, (32, 32))
                self.assertEqual(decoded.format, "JPEG")
        with pending.photo.open("rb") as original_evidence:
            self.assertEqual(original_evidence.read(), original_bytes)
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

    def test_s3_compatible_storage_preserves_price_photo(self):
        """Mock S3 verifies Django/R2-compatible object storage integration.

        This is NOT a live Cloudflare R2 credential or persistence test.
        """
        try:
            import boto3
            from moto import mock_aws
        except ImportError:
            self.skipTest("Install moto[s3] to run S3 compatibility test")

        with mock_aws():
            region = "us-east-1"
            bucket = "wikonomi-mobile-ci"
            s3 = boto3.client("s3", region_name=region)
            s3.create_bucket(Bucket=bucket)
            storage_settings = {
                "default": {
                    "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
                    "OPTIONS": {
                        "access_key": "mock-access-key",
                        "secret_key": "mock-secret-key",
                        "bucket_name": bucket,
                        "region_name": region,
                        "querystring_auth": False,
                        "default_acl": None,
                    },
                },
                "staticfiles": {
                    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
                },
            }
            with override_settings(STORAGES=storage_settings):
                self.client.force_login(self.contributor)
                response = self.client.post(reverse("mobile:submit"), self.payload())
                self.assertEqual(response.status_code, 302)
                submission = MobileSubmission.objects.get()
                image_key = submission.photo.name
                self.assertTrue(image_key.startswith("mobile_price_evidence/"))
                raw_image = s3.get_object(Bucket=bucket, Key=image_key)["Body"].read()
                self.assertTrue(raw_image.startswith(bytes((0x89, 0x50, 0x4e, 0x47))))
                report = approve_submission(submission.pk, self.reviewer)
                self.assertNotEqual(report.image.name, image_key)
                # S3-compatible storage contains both review evidence and
                # the publication-safe resized JPEG.
                report_bytes = s3.get_object(
                    Bucket=bucket, Key=report.image.name
                )["Body"].read()
                with Image.open(io.BytesIO(report_bytes)) as decoded:
                    self.assertEqual(decoded.format, "JPEG")
                    self.assertEqual(decoded.size, (32, 32))
                self.assertEqual(
                    s3.get_object(Bucket=bucket, Key=image_key)["Body"].read(),
                    raw_image,
                )

    def test_home_mobile_screen_renders_after_login(self):
        self.client.force_login(self.contributor)
        response = self.client.get(reverse("mobile:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "mobile/home.html")
        html = response.content.decode("utf-8")
        for label in ("Snap a price", "My contributions", "Offline drafts", "Saved drafts"):
            self.assertIn(label, html)
        self.assertIn('name="viewport"', html)
        self.assertIn('rel="manifest"', html)

    def test_submit_mobile_screen_contains_camera_price_and_csrf(self):
        self.client.force_login(self.contributor)
        response = self.client.get(reverse("mobile:submit"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "mobile/submit.html")
        html = response.content.decode("utf-8")
        for required in (
            'id="price-form"', 'enctype="multipart/form-data"',
            'name="csrfmiddlewaretoken"', 'name="photo"', 'capture="environment"',
            'name="product"', 'name="business_branch"', 'name="price"',
            'id="save-draft"', 'id="submit-price"',
        ):
            with self.subTest(required=required):
                self.assertIn(required, html)

    def test_success_message_and_my_prices_are_contributor_scoped(self):
        self.client.force_login(self.contributor)
        response = self.client.post(reverse("mobile:submit"), self.payload(), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Price submitted for review")
        self.assertContains(response, "Rice 1kg")
        self.assertContains(response, "Pending review")
        other = User.objects.create_user(username="another_buyer", password="test-pass")
        self.client.force_login(other)
        my_home = self.client.get(reverse("mobile:home"))
        self.assertNotContains(my_home, "Rice 1kg")
        self.assertContains(my_home, "Every price starts with one person")

    def test_pwa_manifest_worker_and_assets_exist(self):
        from django.contrib.staticfiles.finders import find
        response = self.client.get(reverse("mobile:manifest"))
        self.assertEqual(response.status_code, 200)
        manifest = response.json()
        self.assertEqual(manifest["start_url"], "/app/")
        self.assertEqual(manifest["scope"], "/app/")
        self.assertEqual(manifest["display"], "standalone")
        for icon in manifest["icons"]:
            if icon["src"].startswith("/static/mobile/"):
                self.assertIsNotNone(find(icon["src"].removeprefix("/static/")))
            else:
                self.assertTrue(icon["src"].startswith("/app/icon-"))
                rendered = self.client.get(icon["src"])
                self.assertEqual(rendered.status_code, 200)
                self.assertEqual(rendered["Content-Type"], "image/png")
                with Image.open(io.BytesIO(rendered.content)) as image:
                    self.assertEqual(image.format, "PNG")
                    expected = int(icon["sizes"].split("x")[0])
                    self.assertEqual(image.size, (expected, expected))
                self.assertTrue("maskable" not in icon["purpose"] or "maskable" in icon["src"])
        for asset in ("mobile/app.css", "mobile/app.js", "mobile/offline.html", "mobile/sw.js"):
            self.assertIsNotNone(find(asset), asset)
        worker = self.client.get(reverse("mobile:service_worker"))
        self.assertEqual(worker.status_code, 200)
        self.assertEqual(worker["Service-Worker-Allowed"], "/app/")
        self.assertIn(b"wikonomi-mobile-static", worker.content)

    def test_mobile_pages_are_not_cached(self):
        self.client.force_login(self.contributor)
        for name in ("mobile:home", "mobile:submit"):
            response = self.client.get(reverse(name))
            self.assertIn("no-store", response.get("Cache-Control", ""))

    def test_price_tag_evidence_is_owner_or_staff_only(self):
        self.client.force_login(self.contributor)
        self.client.post(reverse("mobile:submit"), self.payload())
        submission = MobileSubmission.objects.get()
        url = reverse("mobile:evidence", args=[submission.pk])
        for allowed_user in (self.contributor, self.reviewer):
            self.client.force_login(allowed_user)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.streaming)
            self.assertIn("no-store", response["Cache-Control"])
            raw = b"".join(response.streaming_content)
            self.assertTrue(raw.startswith(bytes((0x89, 0x50, 0x4e, 0x47))))

        other = User.objects.create_user(username="private_photo_test", password="test-pass")
        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)


    def test_staging_database_probe_not_exposed_outside_staging_domain(self):
        response = self.client.get(reverse("mobile:staging_db_status"))
        self.assertEqual(response.status_code, 404)

    def test_staging_database_probe_rejects_temporary_sqlite(self):
        with override_settings(
            ALLOWED_HOSTS=["wikonomi-mobile-staging.onrender.com"],
            MOBILE_STAGING_EPHEMERAL_DB=True,
        ):
            response = self.client.get(
                reverse("mobile:staging_db_status"),
                HTTP_HOST="wikonomi-mobile-staging.onrender.com",
            )
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["staging_database_ready"])
        self.assertIn("no-store", response["Cache-Control"])

    def test_staging_media_config_enforces_separate_private_r2_bucket(self):
        from django.core.exceptions import ImproperlyConfigured
        from mobile.staging_media import staging_media_storage

        config, enabled = staging_media_storage({})
        self.assertFalse(enabled)
        self.assertEqual(config["BACKEND"], "django.core.files.storage.FileSystemStorage")

        endpoint = "https://" + ("a" * 32) + ".r2.cloudflarestorage.com"
        staging_variables = {
            "STAGING_R2_ACCESS_KEY_ID": "fake-ci-key",
            "STAGING_R2_SECRET_ACCESS_KEY": "fake-ci-secret",
            "STAGING_R2_ENDPOINT_URL": endpoint,
            "STAGING_R2_BUCKET_NAME": "wikonomi-mobile-staging",
        }
        config, enabled = staging_media_storage(staging_variables)
        self.assertTrue(enabled)
        self.assertEqual(config["BACKEND"], "storages.backends.s3boto3.S3Boto3Storage")
        options = config["OPTIONS"]
        self.assertTrue(options["querystring_auth"])
        self.assertEqual(options["bucket_name"], "wikonomi-mobile-staging")
        self.assertFalse(options["file_overwrite"])
        self.assertIsNone(options["default_acl"])
        with self.assertRaises(ImproperlyConfigured):
            staging_media_storage({"STAGING_R2_ACCESS_KEY_ID": "incomplete"})
        with self.assertRaises(ImproperlyConfigured):
            staging_media_storage({**staging_variables, "STAGING_R2_BUCKET_NAME": "wikonomi-production"})
        with self.assertRaises(ImproperlyConfigured):
            staging_media_storage({**staging_variables, "STAGING_R2_ENDPOINT_URL": "https://example.com"})

    def test_production_rollout_flag_hides_contribution_routes(self):
        self.client.force_login(self.contributor)
        with override_settings(MOBILE_CONTRIBUTOR_ENABLED=False):
            for url in (
                reverse("mobile:home"),
                reverse("mobile:submit"),
                reverse("mobile:search_products"),
                reverse("mobile:search_branches"),
            ):
                with self.subTest(url=url):
                    self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(
                reverse("mobile:submit"), self.payload()
            ).status_code, 404)
            self.assertEqual(MobileSubmission.objects.count(), 0)

    def test_admin_moderation_approve_publishes_exactly_once(self):
        from django.contrib.auth.models import Permission

        self.client.force_login(self.contributor)
        self.assertEqual(self.client.post(
            reverse("mobile:submit"), self.payload()
        ).status_code, 302)
        submission = MobileSubmission.objects.get()
        self.reviewer.user_permissions.add(Permission.objects.get(
            content_type__app_label="mobile", codename="change_mobilesubmission"
        ))

        changelist = reverse("admin:mobile_mobilesubmission_changelist")
        self.client.force_login(self.reviewer)
        listing = self.client.get(changelist)
        self.assertEqual(listing.status_code, 200)
        self.assertContains(listing, "View original photo")
        self.assertContains(listing, reverse("mobile:evidence", args=[submission.pk]))

        post = {
            "action": "approve_selected",
            "_selected_action": [str(submission.pk)],
            "select_across": "0",
            "index": "0",
        }
        self.assertEqual(self.client.post(changelist, post).status_code, 302)
        submission.refresh_from_db()
        self.assertEqual(submission.status, MobileSubmission.Status.APPROVED)
        self.assertEqual(PriceReport.objects.count(), 1)
        report = submission.published_report
        self.assertEqual(report.price, Decimal("12.50"))
        self.assertEqual(report.user, self.contributor)
        self.assertEqual(submission.reviewed_by, self.reviewer)
        self.assertIsNotNone(submission.reviewed_at)

        # Repeating the admin action must never republish the same price.
        self.assertEqual(self.client.post(changelist, post).status_code, 302)
        self.assertEqual(PriceReport.objects.count(), 1)

    def test_admin_moderation_reject_does_not_publish(self):
        from django.contrib.auth.models import Permission

        self.client.force_login(self.contributor)
        self.client.post(reverse("mobile:submit"), self.payload())
        submission = MobileSubmission.objects.get()
        self.reviewer.user_permissions.add(Permission.objects.get(
            content_type__app_label="mobile", codename="change_mobilesubmission"
        ))
        self.client.force_login(self.reviewer)
        changelist = reverse("admin:mobile_mobilesubmission_changelist")
        post = {
            "action": "reject_selected",
            "_selected_action": [str(submission.pk)],
            "select_across": "0",
            "index": "0",
        }
        self.assertEqual(self.client.post(changelist, post).status_code, 302)
        submission.refresh_from_db()
        self.assertEqual(submission.status, MobileSubmission.Status.REJECTED)
        self.assertEqual(submission.reviewed_by, self.reviewer)
        self.assertEqual(PriceReport.objects.count(), 0)

    def test_regular_user_cannot_use_admin_review_actions(self):
        self.client.force_login(self.contributor)
        self.client.post(reverse("mobile:submit"), self.payload())
        submission = MobileSubmission.objects.get()
        response = self.client.post(
            reverse("admin:mobile_mobilesubmission_changelist"),
            {"action": "approve_selected",
             "_selected_action": [str(submission.pk)]},
        )
        self.assertIn(response.status_code, (302, 403))
        self.assertEqual(PriceReport.objects.count(), 0)
        submission.refresh_from_db()
        self.assertEqual(submission.status, MobileSubmission.Status.PENDING)
