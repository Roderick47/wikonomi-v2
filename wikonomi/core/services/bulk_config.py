import os


def _integer(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _floating_point(name, default):
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


MAX_SPREADSHEET_SIZE = _integer(
    'BULK_IMPORT_MAX_SPREADSHEET_SIZE',
    10 * 1024 * 1024,
)
MAX_ROWS = _integer('BULK_IMPORT_MAX_ROWS', 10000)
MAX_IMAGE_SIZE = _integer('BULK_IMPORT_MAX_IMAGE_SIZE', 10 * 1024 * 1024)
MAX_IMAGES = _integer('BULK_IMPORT_MAX_IMAGES', 1000)
MAX_ARCHIVE_SIZE = _integer(
    'BULK_IMPORT_MAX_ARCHIVE_SIZE',
    100 * 1024 * 1024,
)
MAX_EXTRACTED_SIZE = _integer(
    'BULK_IMPORT_MAX_EXTRACTED_SIZE',
    500 * 1024 * 1024,
)
FUZZY_THRESHOLD = _floating_point('BULK_IMPORT_FUZZY_THRESHOLD', 95)
SESSION_DAYS = _integer('BULK_IMPORT_SESSION_DAYS', 7)
