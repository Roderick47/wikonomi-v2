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
    25 * 1024 * 1024,
)
MAX_ROWS = _integer('BULK_IMPORT_MAX_ROWS', 50000)
MAX_IMAGE_SIZE = _integer('BULK_IMPORT_MAX_IMAGE_SIZE', 15 * 1024 * 1024)
MAX_IMAGES = _integer('BULK_IMPORT_MAX_IMAGES', 50000)
MAX_ARCHIVE_SIZE = _integer(
    'BULK_IMPORT_MAX_ARCHIVE_SIZE',
    2 * 1024 * 1024 * 1024,
)
MAX_EXTRACTED_SIZE = _integer(
    'BULK_IMPORT_MAX_EXTRACTED_SIZE',
    4 * 1024 * 1024 * 1024,
)
FUZZY_THRESHOLD = _floating_point('BULK_IMPORT_FUZZY_THRESHOLD', 95)
SESSION_DAYS = _integer('BULK_IMPORT_SESSION_DAYS', 7)
