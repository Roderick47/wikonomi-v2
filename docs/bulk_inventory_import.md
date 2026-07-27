# Bulk inventory and photo import

The catalogue wizard stores spreadsheet rows, staged images, matches, and job
progress in the database. Import work is idempotent and split into short batches
requested by the progress page, so a browser refresh resumes from the last
completed row instead of recreating records.

## Flow

1. `spreadsheet_parser.py` streams CSV or XLSX rows into `BulkImportRow`.
2. `image_processor.py` validates individual files or securely extracts a ZIP.
3. `image_matcher.py` matches filenames by SKU, barcode, exact/normalised name,
   then configurable fuzzy confidence.
4. The review page resolves suggestions, missing photos, and duplicates.
5. `inventory_importer.py` creates products, business inventory metadata, price
   reports, and responsive `ProductImage` derivatives in resumable batches.

The import service does not depend on an HTTP request. A future queue or Render
worker can call `process_import_batch(session)` without changing parsing,
matching, review, or image processing.

## Configuration

All limits have safe defaults and can be overridden with environment variables:

- `BULK_IMPORT_MAX_SPREADSHEET_SIZE`
- `BULK_IMPORT_MAX_ROWS`
- `BULK_IMPORT_MAX_IMAGE_SIZE`
- `BULK_IMPORT_MAX_IMAGES`
- `BULK_IMPORT_MAX_ARCHIVE_SIZE`
- `BULK_IMPORT_MAX_EXTRACTED_SIZE`
- `BULK_IMPORT_FUZZY_THRESHOLD`
- `BULK_IMPORT_SESSION_DAYS`

Run `python manage.py cleanup_bulk_imports` from a daily maintenance job to
remove expired spreadsheets and staging images. Imported product originals and
responsive derivatives are not removed.

## AI extension

`ImageAnalysisHook` is intentionally a no-op interface. Future implementations
can add product recognition, barcode OCR, cropping, background removal, image
quality checks, wrong-product detection, and generated descriptions without
changing the deterministic matcher.
