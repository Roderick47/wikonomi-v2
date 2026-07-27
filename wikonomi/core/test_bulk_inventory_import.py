import io
import tempfile
import zipfile
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook
from PIL import Image

from core.models import (
    BulkImportImage,
    BulkImportRow,
    BulkImportSession,
    Business,
    BusinessInventoryItem,
    PriceReport,
    Product,
    ProductImage,
)
from core.services.image_matcher import ImageMatcher, normalize_filename
from core.services.image_processor import (
    stage_uploaded_images,
    stage_zip_archive,
)
from core.services.inventory_importer import process_import_batch
from core.services.spreadsheet_parser import parse_inventory_session


def image_bytes(color='red', image_format='JPEG'):
    buffer = io.BytesIO()
    Image.new('RGB', (80, 60), color=color).save(buffer, format=image_format)
    return buffer.getvalue()


@override_settings(BULK_IMPORT_MAX_ROWS=10000)
class SpreadsheetParserTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='bulk-user', password='pass')
        self.business = Business.objects.create(name='Bulk Store', slug='bulk-store')

    def create_session(self, filename, content):
        session = BulkImportSession(
            user=self.user,
            business=self.business,
            inventory_filename=filename,
            expires_at=timezone.now() + timedelta(days=7),
        )
        session.inventory_file.save(filename, ContentFile(content), save=False)
        session.save()
        return session

    def test_csv_supports_new_and_legacy_columns(self):
        content = (
            b'SKU,Barcode,product_name,Description,Brand,Category,Unit,price,'
            b'currency,Stock Quantity,notes,tags\n'
            b'RICE-1,930001,Rice 10kg,White rice,Local,Food,bag,45.00,PGK,12,Fresh,staple\n'
        )
        session = self.create_session('inventory.csv', content)
        result = parse_inventory_session(session)
        row = session.rows.get()

        self.assertEqual(result['valid_rows'], 1)
        self.assertEqual(row.sku, 'RICE-1')
        self.assertEqual(row.barcode, '930001')
        self.assertEqual(row.price, Decimal('45.00'))
        self.assertEqual(row.stock_quantity, Decimal('12'))
        self.assertEqual(row.tags, 'staple')

    def test_xlsx_is_streamed_and_validated(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(['SKU', 'Product Name', 'Price', 'Currency'])
        sheet.append(['COKE-1', 'Coca-Cola 1.25L', 8.5, 'PGK'])
        buffer = io.BytesIO()
        workbook.save(buffer)
        session = self.create_session('inventory.xlsx', buffer.getvalue())

        result = parse_inventory_session(session)

        self.assertEqual(result['valid_rows'], 1)
        self.assertEqual(session.rows.get().product_name, 'Coca-Cola 1.25L')

    def test_invalid_and_duplicate_rows_block_progress(self):
        content = (
            b'Product Name,Price,SKU\n'
            b',10,A\n'
            b'Rice,invalid,B\n'
            b'Sugar,5,C\n'
            b'Sugar,6,C\n'
        )
        session = self.create_session('inventory.csv', content)

        result = parse_inventory_session(session)

        self.assertEqual(result['valid_rows'], 1)
        self.assertEqual(result['invalid_rows'], 3)
        self.assertEqual(session.duplicate_products, 1)

    def test_thousands_of_rows_are_batched(self):
        rows = ['Product Name,Price,SKU']
        rows.extend(f'Product {index},1.00,SKU-{index}' for index in range(2500))
        session = self.create_session('large.csv', '\n'.join(rows).encode())

        result = parse_inventory_session(session)

        self.assertEqual(result['valid_rows'], 2500)
        self.assertEqual(session.rows.count(), 2500)


@override_settings(
    BULK_IMPORT_MAX_IMAGE_SIZE=2 * 1024 * 1024,
    BULK_IMPORT_MAX_ARCHIVE_SIZE=10 * 1024 * 1024,
    BULK_IMPORT_MAX_EXTRACTED_SIZE=20 * 1024 * 1024,
)
class ImageUploadAndMatchingTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.media.cleanup)
        self.user = User.objects.create_user(username='photo-user', password='pass')
        self.business = Business.objects.create(name='Photo Store', slug='photo-store')
        self.session = BulkImportSession.objects.create(
            user=self.user,
            business=self.business,
            inventory_file='imports/inventory.csv',
            inventory_filename='inventory.csv',
            valid_rows=4,
            expires_at=timezone.now() + timedelta(days=7),
        )
        self.sku_row = BulkImportRow.objects.create(
            session=self.session,
            row_number=2,
            sku='12345',
            barcode='9300675001234',
            product_name='Rice 10kg',
            price=10,
        )
        self.name_row = BulkImportRow.objects.create(
            session=self.session,
            row_number=3,
            sku='COKE-125',
            product_name='Coca-Cola 1.25L',
            price=8,
        )

    def upload(self, name, color='red'):
        uploaded = SimpleUploadedFile(
            name,
            image_bytes(color),
            content_type='image/jpeg',
        )
        created, errors = stage_uploaded_images(self.session, [uploaded])
        self.assertFalse(errors)
        return created[0]

    def test_filename_normalisation(self):
        self.assertEqual(normalize_filename('Coca-Cola 1.25L.jpg'), 'cocacola125l')

    def test_sku_barcode_name_and_gallery_suffix_matching(self):
        sku = self.upload('12345_front.jpg')
        barcode = self.upload('9300675001234.jpg', 'blue')
        exact_name = self.upload('Coca-Cola 1.25L.jpg', 'green')
        normalised = self.upload('Coca Cola 1.25L_side.jpg', 'yellow')

        ImageMatcher().match_session(self.session)
        for image in (sku, barcode, exact_name, normalised):
            image.refresh_from_db()

        self.assertEqual(sku.matched_row, self.sku_row)
        self.assertEqual(sku.match_method, 'sku')
        self.assertEqual(barcode.match_method, 'barcode')
        self.assertEqual(exact_name.match_method, 'exact_name')
        self.assertEqual(normalised.match_method, 'normalized_name')

    def test_fuzzy_below_threshold_becomes_suggestion(self):
        image = self.upload('Coca Cola 1.35L.jpg')
        ImageMatcher(threshold=99).match_session(self.session)
        image.refresh_from_db()

        self.assertEqual(image.status, BulkImportImage.Status.UNMATCHED)
        self.assertEqual(image.matched_row, self.name_row)
        self.assertEqual(image.match_method, 'fuzzy_suggestion')

    def test_fuzzy_above_threshold_is_accepted(self):
        image = self.upload('Coca Colaa 1.25L.jpg')
        ImageMatcher(threshold=95).match_session(self.session)
        image.refresh_from_db()

        self.assertEqual(image.status, BulkImportImage.Status.MATCHED)
        self.assertEqual(image.matched_row, self.name_row)
        self.assertEqual(image.match_method, 'fuzzy_name')

    def test_primary_image_prefers_front_then_numeric_then_upload_order(self):
        side = self.upload('12345_side.jpg')
        numbered = self.upload('12345-1.jpg', 'blue')
        front = self.upload('12345_front.jpg', 'green')
        ImageMatcher().match_session(self.session)
        side.refresh_from_db()
        numbered.refresh_from_db()
        front.refresh_from_db()

        self.assertTrue(front.is_primary)
        self.assertFalse(side.is_primary)
        self.assertFalse(numbered.is_primary)
        self.assertEqual(front.sort_order, 0)

    def test_duplicate_hash_is_detected(self):
        first = self.upload('12345_front.jpg')
        second = self.upload('12345_back.jpg')
        ImageMatcher().match_session(self.session)
        first.refresh_from_db()
        second.refresh_from_db()

        self.assertIsNone(first.duplicate_of)
        self.assertEqual(second.duplicate_of, first)
        self.assertEqual(second.status, BulkImportImage.Status.DUPLICATE)
        self.assertEqual(second.matched_row, self.sku_row)

    def test_zip_slip_is_rejected_and_valid_member_is_kept(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('../escape.jpg', image_bytes())
            archive.writestr('safe/12345.jpg', image_bytes('blue'))
            archive.writestr('run.exe', b'bad')
        uploaded = SimpleUploadedFile(
            'photos.zip',
            buffer.getvalue(),
            content_type='application/zip',
        )

        created, errors = stage_zip_archive(self.session, uploaded)

        self.assertEqual(len(created), 1)
        self.assertTrue(any('Unsafe ZIP path' in error for error in errors))
        self.assertTrue(any('Executable ZIP member' in error for error in errors))

    def test_invalid_zip_and_corrupt_image_are_rejected(self):
        bad_zip = SimpleUploadedFile('bad.zip', b'not-a-zip', content_type='application/zip')
        with self.assertRaisesMessage(ValueError, 'invalid or corrupt'):
            stage_zip_archive(self.session, bad_zip)

        corrupt = SimpleUploadedFile('bad.jpg', b'not-an-image', content_type='image/jpeg')
        created, errors = stage_uploaded_images(self.session, [corrupt])
        self.assertFalse(created)
        self.assertTrue(any('corrupt or unsupported' in error for error in errors))


class ImportJobTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.media.cleanup)
        self.user = User.objects.create_user(username='job-user', password='pass')
        self.business = Business.objects.create(name='Job Store', slug='job-store')
        self.session = BulkImportSession.objects.create(
            user=self.user,
            business=self.business,
            inventory_file='imports/inventory.csv',
            inventory_filename='inventory.csv',
            status=BulkImportSession.Status.PROCESSING,
            valid_rows=2,
            matched_images=1,
            progress_percent=40,
            expires_at=timezone.now() + timedelta(days=7),
        )
        self.first_row = BulkImportRow.objects.create(
            session=self.session,
            row_number=2,
            sku='A-1',
            product_name='Imported Rice',
            description='A bag of rice',
            brand='Local',
            unit='bag',
            price=Decimal('15.00'),
            currency='PGK',
            stock_quantity=5,
        )
        BulkImportRow.objects.create(
            session=self.session,
            row_number=3,
            sku='B-1',
            product_name='Imported Sugar',
            price=Decimal('8.00'),
            currency='PGK',
        )
        uploaded = SimpleUploadedFile(
            'A-1_front.jpg',
            image_bytes(),
            content_type='image/jpeg',
        )
        staged, errors = stage_uploaded_images(self.session, [uploaded])
        self.assertFalse(errors)
        self.image = staged[0]
        self.image.matched_row = self.first_row
        self.image.status = BulkImportImage.Status.MATCHED
        self.image.is_primary = True
        self.image.save()

    def run_to_completion(self):
        for _ in range(10):
            self.session.refresh_from_db()
            payload = process_import_batch(
                self.session,
                row_batch_size=1,
                image_batch_size=1,
            )
            if payload['status'] == BulkImportSession.Status.COMPLETED:
                return payload
        self.fail('Import did not complete')

    def test_resumable_import_creates_inventory_prices_and_responsive_images(self):
        payload = self.run_to_completion()

        self.assertEqual(payload['progress_percent'], 100)
        self.assertEqual(Product.objects.count(), 2)
        self.assertEqual(PriceReport.objects.count(), 2)
        self.assertEqual(BusinessInventoryItem.objects.count(), 2)
        product_image = ProductImage.objects.get()
        self.assertTrue(product_image.original)
        self.assertTrue(product_image.medium)
        self.assertTrue(product_image.thumbnail)
        self.assertTrue(product_image.is_primary)

    def test_completed_job_is_idempotent_after_refresh(self):
        self.run_to_completion()
        self.session.refresh_from_db()
        process_import_batch(self.session)

        self.assertEqual(Product.objects.count(), 2)
        self.assertEqual(PriceReport.objects.count(), 2)
        self.assertEqual(ProductImage.objects.count(), 1)


class BulkWizardViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='wizard-user', password='pass')
        self.business = Business.objects.create(name='Wizard Store', slug='wizard-store')
        self.client.login(username='wizard-user', password='pass')

    def test_business_and_price_pages_expose_bulk_wizard(self):
        business_page = self.client.get(reverse('business_detail', args=[self.business.pk]))
        price_page = self.client.get(reverse('add_price'))

        self.assertContains(business_page, 'Bulk Upload Inventory')
        self.assertContains(price_page, 'Bulk Inventory')

    def test_csv_wizard_advances_to_photo_step(self):
        inventory = SimpleUploadedFile(
            'inventory.csv',
            b'SKU,Product Name,Price\nABC,Test Product,10.00\n',
            content_type='text/csv',
        )
        response = self.client.post(reverse('bulk_upload'), {
            'business': self.business.pk,
            'inventory_file': inventory,
        })

        session = BulkImportSession.objects.get()
        self.assertRedirects(
            response,
            reverse('bulk_upload_photos', args=[session.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(session.valid_rows, 1)

    def test_folder_style_multi_file_upload_reaches_review(self):
        session = BulkImportSession.objects.create(
            user=self.user,
            business=self.business,
            inventory_file='imports/inventory.csv',
            inventory_filename='inventory.csv',
            status=BulkImportSession.Status.PHOTOS,
            valid_rows=1,
            expires_at=timezone.now() + timedelta(days=7),
        )
        BulkImportRow.objects.create(
            session=session,
            row_number=2,
            sku='ABC',
            product_name='Test Product',
            price=10,
        )
        response = self.client.post(reverse('bulk_upload_photos', args=[session.pk]), {
            'action': 'upload',
            'photos': [
                SimpleUploadedFile('ABC_front.jpg', image_bytes(), content_type='image/jpeg'),
                SimpleUploadedFile('ABC_back.jpg', image_bytes('blue'), content_type='image/jpeg'),
            ],
        })

        self.assertRedirects(
            response,
            reverse('bulk_upload_review', args=[session.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(session.images.count(), 2)
        self.assertEqual(
            session.images.filter(status=BulkImportImage.Status.MATCHED).count(),
            2,
        )
        review = self.client.get(reverse('bulk_upload_review', args=[session.pk]))
        self.assertEqual(review.status_code, 200)
        self.assertContains(review, 'Review automatic matches')

    def test_other_user_cannot_resume_session(self):
        other = User.objects.create_user(username='other-user', password='pass')
        session = BulkImportSession.objects.create(
            user=other,
            business=self.business,
            inventory_file='imports/inventory.csv',
            inventory_filename='inventory.csv',
            expires_at=timezone.now() + timedelta(days=7),
        )

        response = self.client.get(reverse('bulk_upload_photos', args=[session.pk]))

        self.assertEqual(response.status_code, 404)
