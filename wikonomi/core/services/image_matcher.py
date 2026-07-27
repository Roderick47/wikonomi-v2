import re
import unicodedata
from pathlib import Path

from rapidfuzz import fuzz, process

from core.models import BulkImportImage, BulkImportRow
from core.services.bulk_config import FUZZY_THRESHOLD


PRIMARY_TOKENS = ('main', 'cover', 'front')
VARIANT_SUFFIX = re.compile(
    r'(?:[\s_-]+(?:main|cover|front|back|side|rear|detail|\d+))$',
    flags=re.IGNORECASE,
)


def normalize_filename(value):
    """Normalise a filename or identifier into a comparison-safe token."""
    text = str(value or '')
    suffix = Path(text).suffix.lower()
    stem = text[:-len(suffix)] if suffix in {'.jpg', '.jpeg', '.png', '.webp'} else text
    stem = unicodedata.normalize('NFKD', stem)
    stem = stem.replace('_', ' ').replace('-', ' ')
    stem = re.sub(r'[^\w\s]', '', stem, flags=re.UNICODE)
    stem = re.sub(r'\s+', ' ', stem).strip().lower()
    return re.sub(r'\s+', '', stem)


def filename_candidates(filename):
    """Return the full stem and a base stem with gallery suffixes removed."""
    stem = Path(filename or '').stem.strip()
    candidates = [stem]
    base = stem
    while True:
        stripped = VARIANT_SUFFIX.sub('', base).strip(' _-')
        if stripped == base or not stripped:
            break
        base = stripped
        candidates.append(base)
    return list(dict.fromkeys(candidates))


class ImageMatcher:
    """Deterministic matcher with an extension point for future AI strategies."""

    def __init__(self, threshold=None):
        self.threshold = float(
            threshold
            if threshold is not None
            else FUZZY_THRESHOLD
        )

    def match_session(self, session):
        rows = list(session.rows.filter(status=BulkImportRow.Status.VALID))
        images = list(session.images.exclude(
            status__in=[
                BulkImportImage.Status.REJECTED,
                BulkImportImage.Status.SKIPPED,
                BulkImportImage.Status.IMPORTED,
            ]
        ))
        indexes = self._build_indexes(rows)
        updates = []
        duplicate_updates = []

        for image in images:
            if image.duplicate_of_id:
                duplicate_updates.append(image)
                continue

            result = self._match_filename(image.original_filename, rows, indexes)
            if result:
                row, method, confidence, *flags = result
                accepted = flags[0] if flags else True
                image.matched_row = row
                image.match_method = method
                image.confidence = confidence
                image.status = (
                    BulkImportImage.Status.MATCHED
                    if accepted
                    else BulkImportImage.Status.UNMATCHED
                )
                image.warning = (
                    ''
                    if accepted
                    else f'Suggested match below {self.threshold:g}% threshold.'
                )
            else:
                image.matched_row = None
                image.match_method = ''
                image.confidence = 0
                image.status = BulkImportImage.Status.UNMATCHED
                image.warning = ''
            updates.append(image)

        if updates:
            BulkImportImage.objects.bulk_update(
                updates,
                ['matched_row', 'match_method', 'confidence', 'status', 'warning'],
                batch_size=500,
            )

        if duplicate_updates:
            source_images = BulkImportImage.objects.in_bulk({
                image.duplicate_of_id for image in duplicate_updates
            })
            for image in duplicate_updates:
                source = source_images.get(image.duplicate_of_id)
                image.status = BulkImportImage.Status.DUPLICATE
                image.matched_row_id = source.matched_row_id if source else None
                image.match_method = 'duplicate'
                image.confidence = source.confidence if source else 0
                image.warning = (
                    f'Duplicate of {source.original_filename}'
                    if source
                    else image.warning
                )
            BulkImportImage.objects.bulk_update(
                duplicate_updates,
                [
                    'matched_row',
                    'match_method',
                    'confidence',
                    'status',
                    'warning',
                ],
                batch_size=500,
            )

        self._assign_primary_images(session)
        self._update_session_counts(session)
        return session

    def _build_indexes(self, rows):
        indexes = {
            'sku_exact': {},
            'sku_folded': {},
            'barcode_exact': {},
            'barcode_folded': {},
            'name_exact': {},
            'name_folded': {},
            'name_normalized': {},
        }
        for row in rows:
            if row.sku:
                indexes['sku_exact'].setdefault(row.sku, row)
                indexes['sku_folded'].setdefault(row.sku.casefold(), row)
            if row.barcode:
                indexes['barcode_exact'].setdefault(row.barcode, row)
                indexes['barcode_folded'].setdefault(row.barcode.casefold(), row)
            indexes['name_exact'].setdefault(row.product_name, row)
            indexes['name_folded'].setdefault(row.product_name.casefold(), row)
            indexes['name_normalized'].setdefault(
                normalize_filename(row.product_name),
                row,
            )
        return indexes

    def _match_filename(self, filename, rows, indexes):
        candidates = filename_candidates(filename)

        for candidate in reversed(candidates):
            if candidate in indexes['sku_exact']:
                return indexes['sku_exact'][candidate], 'sku', 100
        for candidate in reversed(candidates):
            if candidate in indexes['barcode_exact']:
                return indexes['barcode_exact'][candidate], 'barcode', 100
        for candidate in reversed(candidates):
            if candidate in indexes['name_exact']:
                return indexes['name_exact'][candidate], 'exact_name', 100

        for candidate in reversed(candidates):
            folded = candidate.casefold()
            if folded in indexes['sku_folded']:
                return indexes['sku_folded'][folded], 'sku_case_insensitive', 99
            if folded in indexes['barcode_folded']:
                return indexes['barcode_folded'][folded], 'barcode_case_insensitive', 99
            if folded in indexes['name_folded']:
                return indexes['name_folded'][folded], 'name_case_insensitive', 99

        for candidate in reversed(candidates):
            normalized = normalize_filename(candidate)
            if normalized in indexes['name_normalized']:
                return indexes['name_normalized'][normalized], 'normalized_name', 98

        normalized = normalize_filename(candidates[-1] if candidates else filename)
        if not normalized or not indexes['name_normalized']:
            return None
        best = process.extractOne(
            normalized,
            indexes['name_normalized'].keys(),
            scorer=fuzz.ratio,
        )
        if not best:
            return None
        matched_name, confidence, _ = best
        return (
            indexes['name_normalized'][matched_name],
            'fuzzy_name' if confidence >= self.threshold else 'fuzzy_suggestion',
            confidence,
            confidence >= self.threshold,
        )

    def _assign_primary_images(self, session):
        matched = list(
            session.images.filter(status=BulkImportImage.Status.MATCHED)
            .select_related('matched_row')
            .order_by('uploaded_at', 'id')
        )
        grouped = {}
        for image in matched:
            grouped.setdefault(image.matched_row_id, []).append(image)

        updates = []
        for images in grouped.values():
            primary = min(images, key=self._primary_sort_key)
            ordered = sorted(images, key=lambda image: (
                0 if image.pk == primary.pk else 1,
                image.uploaded_at,
                image.pk,
            ))
            for index, image in enumerate(ordered):
                image.is_primary = image.pk == primary.pk
                image.sort_order = index
                updates.append(image)
        if updates:
            BulkImportImage.objects.bulk_update(
                updates,
                ['is_primary', 'sort_order'],
                batch_size=500,
            )

    def _primary_sort_key(self, image):
        stem = Path(image.original_filename).stem.casefold()
        for index, token in enumerate(PRIMARY_TOKENS):
            if re.search(rf'(^|[\s_-]){token}($|[\s_-])', stem):
                return index, image.uploaded_at, image.pk
        if re.search(r'(^|[\s_-])1($|[\s_-])', stem):
            return len(PRIMARY_TOKENS), image.uploaded_at, image.pk
        return len(PRIMARY_TOKENS) + 1, image.uploaded_at, image.pk

    def _update_session_counts(self, session):
        session.total_images = session.images.exclude(
            status=BulkImportImage.Status.REJECTED
        ).count()
        session.matched_images = session.images.filter(
            status=BulkImportImage.Status.MATCHED
        ).count()
        session.unmatched_images = session.images.filter(
            status=BulkImportImage.Status.UNMATCHED
        ).count()
        session.duplicate_images = session.images.filter(
            status=BulkImportImage.Status.DUPLICATE
        ).count()
        session.status = session.Status.REVIEW
        session.current_stage = 'Automatic photo matching'
        session.progress_percent = 35
        session.save(update_fields=[
            'total_images',
            'matched_images',
            'unmatched_images',
            'duplicate_images',
            'status',
            'current_stage',
            'progress_percent',
            'updated_at',
        ])


class ImageAnalysisHook:
    """No-op interface reserved for future AI image analysis implementations."""

    def analyse(self, *, image, row):  # pragma: no cover - interface only
        return {
            'product_recognition': None,
            'barcode_ocr': None,
            'crop': None,
            'background_removal': None,
            'duplicate_detection': None,
            'blur_detection': None,
            'wrong_product_detection': None,
            'generated_description': None,
        }
