import hashlib
import io
import re
import zipfile
from pathlib import Path, PurePosixPath

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

from core.models import BulkImportImage, ProductImage
from core.services.bulk_config import (
    MAX_ARCHIVE_SIZE,
    MAX_EXTRACTED_SIZE,
    MAX_IMAGES,
    MAX_IMAGE_SIZE,
)


ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
ALLOWED_FORMATS = {'JPEG', 'PNG', 'WEBP'}
FORMAT_MIMES = {
    'JPEG': 'image/jpeg',
    'PNG': 'image/png',
    'WEBP': 'image/webp',
}
EXECUTABLE_EXTENSIONS = {
    '.bat', '.bin', '.cmd', '.com', '.dll', '.dmg', '.exe', '.htm', '.html',
    '.jar', '.js', '.msi', '.php', '.ps1', '.py', '.sh', '.svg', '.vbs',
}


def safe_client_filename(value):
    name = Path(str(value or '')).name
    name = re.sub(r'[\x00-\x1f\x7f]', '', name).strip()
    if not name or name in {'.', '..'}:
        raise ValueError('Image filename is invalid.')
    if Path(name).suffix.lower() in EXECUTABLE_EXTENSIONS:
        raise ValueError(f'Executable file "{name}" is not allowed.')
    if Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(f'Unsupported image format for "{name}".')
    return name[:255]


def _read_limited(file_obj, max_size):
    data = file_obj.read(max_size + 1)
    if len(data) > max_size:
        raise ValueError(f'Image exceeds the {max_size // (1024 * 1024)} MB limit.')
    return data


def validate_image_bytes(data, filename):
    if not data:
        raise ValueError(f'Image "{filename}" is empty.')
    try:
        with Image.open(io.BytesIO(data)) as image:
            detected_format = image.format
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError(f'Image "{filename}" is corrupt or unsupported.') from exc
    if detected_format not in ALLOWED_FORMATS:
        raise ValueError(f'Image "{filename}" has an unsupported MIME type.')
    return FORMAT_MIMES[detected_format]


def create_staged_image(session, *, file_obj, filename, declared_content_type=''):
    max_image_size = MAX_IMAGE_SIZE
    safe_name = safe_client_filename(filename)
    data = _read_limited(file_obj, max_image_size)
    detected_content_type = validate_image_bytes(data, safe_name)
    if declared_content_type and declared_content_type not in {
        detected_content_type,
        'application/octet-stream',
        'binary/octet-stream',
    }:
        raise ValueError(f'Image "{safe_name}" content does not match its MIME type.')

    digest = hashlib.sha256(data).hexdigest()
    duplicate = (
        session.images.filter(content_hash=digest).order_by('uploaded_at', 'id').first()
        or session.images.filter(original_filename__iexact=safe_name)
        .order_by('uploaded_at', 'id').first()
    )
    image = BulkImportImage(
        session=session,
        original_filename=safe_name,
        content_type=detected_content_type,
        size_bytes=len(data),
        content_hash=digest,
        duplicate_of=duplicate,
        status=(
            BulkImportImage.Status.DUPLICATE
            if duplicate
            else BulkImportImage.Status.UPLOADED
        ),
        warning=(
            f'Duplicate of {duplicate.original_filename}'
            if duplicate
            else ''
        ),
    )
    image.file.save(safe_name, ContentFile(data), save=False)
    image.save()
    return image


def stage_uploaded_images(session, uploaded_files):
    created = []
    errors = []
    max_files = MAX_IMAGES
    remaining = max_files - session.images.count()
    for uploaded in list(uploaded_files)[:max(0, remaining)]:
        try:
            uploaded.seek(0)
            created.append(create_staged_image(
                session,
                file_obj=uploaded,
                filename=uploaded.name,
                declared_content_type=getattr(uploaded, 'content_type', ''),
            ))
        except ValueError as exc:
            errors.append(str(exc))
    if len(uploaded_files) > remaining:
        errors.append(f'Only {max_files:,} images are allowed in one import.')
    return created, errors


def stage_zip_archive(session, archive):
    max_archive_size = MAX_ARCHIVE_SIZE
    max_total_size = MAX_EXTRACTED_SIZE
    max_image_size = MAX_IMAGE_SIZE
    max_files = MAX_IMAGES
    if archive.size > max_archive_size:
        raise ValueError('ZIP archive is larger than the configured upload limit.')

    created = []
    errors = []
    try:
        archive.seek(0)
        with zipfile.ZipFile(archive) as zip_file:
            members = [member for member in zip_file.infolist() if not member.is_dir()]
            if len(members) + session.images.count() > max_files:
                raise ValueError(f'ZIP archive exceeds the {max_files:,}-image limit.')
            total_size = sum(member.file_size for member in members)
            if total_size > max_total_size:
                raise ValueError('ZIP expands beyond the configured safety limit.')

            for member in members:
                path = PurePosixPath(member.filename.replace('\\', '/'))
                if path.is_absolute() or '..' in path.parts:
                    errors.append(f'Unsafe ZIP path rejected: {member.filename}')
                    continue
                if member.flag_bits & 0x1:
                    errors.append(f'Encrypted ZIP member rejected: {member.filename}')
                    continue
                extension = Path(path.name).suffix.lower()
                if extension in EXECUTABLE_EXTENSIONS:
                    errors.append(f'Executable ZIP member rejected: {member.filename}')
                    continue
                if extension not in ALLOWED_EXTENSIONS:
                    continue
                if member.file_size > max_image_size:
                    errors.append(f'Image is too large: {member.filename}')
                    continue
                if member.compress_size and member.file_size / member.compress_size > 200:
                    errors.append(f'Suspicious compression ratio: {member.filename}')
                    continue
                try:
                    with zip_file.open(member) as extracted:
                        created.append(create_staged_image(
                            session,
                            file_obj=extracted,
                            filename=path.name,
                        ))
                except (ValueError, RuntimeError, zipfile.BadZipFile) as exc:
                    errors.append(str(exc))
    except zipfile.BadZipFile as exc:
        raise ValueError('The uploaded ZIP archive is invalid or corrupt.') from exc
    return created, errors


def _jpeg_derivative(image, max_dimensions, quality):
    derivative = ImageOps.exif_transpose(image)
    if derivative.mode not in ('RGB', 'L'):
        derivative = derivative.convert('RGB')
    elif derivative.mode == 'L':
        derivative = derivative.convert('RGB')
    derivative.thumbnail(max_dimensions, Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    derivative.save(buffer, format='JPEG', quality=quality, optimize=True)
    return buffer.getvalue()


def create_product_image(staged_image):
    """Copy the original and create responsive derivatives idempotently."""
    if staged_image.status == BulkImportImage.Status.IMPORTED:
        return ProductImage.objects.filter(
            product=staged_image.matched_row.product,
            business=staged_image.session.business,
            content_hash=staged_image.content_hash,
        ).first()
    if not staged_image.matched_row_id or not staged_image.matched_row.product_id:
        raise ValueError('The image is not linked to an imported product.')

    existing = ProductImage.objects.filter(
        product=staged_image.matched_row.product,
        business=staged_image.session.business,
        content_hash=staged_image.content_hash,
    ).first()
    if existing:
        return existing

    with staged_image.file.open('rb') as source:
        original_data = source.read()
    try:
        with Image.open(io.BytesIO(original_data)) as image:
            medium_data = _jpeg_derivative(image, (1200, 1200), 82)
        with Image.open(io.BytesIO(original_data)) as image:
            thumbnail_data = _jpeg_derivative(image, (320, 320), 78)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError('Image became unreadable during processing.') from exc

    product_image = ProductImage(
        product=staged_image.matched_row.product,
        business=staged_image.session.business,
        original_filename=staged_image.original_filename,
        content_hash=staged_image.content_hash,
        is_primary=staged_image.is_primary,
        sort_order=staged_image.sort_order,
    )
    extension = Path(staged_image.original_filename).suffix.lower() or '.jpg'
    product_image.original.save(
        f'original{extension}',
        ContentFile(original_data),
        save=False,
    )
    product_image.medium.save('medium.jpg', ContentFile(medium_data), save=False)
    product_image.thumbnail.save('thumb.jpg', ContentFile(thumbnail_data), save=False)
    product_image.save()

    if product_image.is_primary:
        ProductImage.objects.filter(
            product=product_image.product,
            is_primary=True,
        ).exclude(pk=product_image.pk).update(is_primary=False)
    return product_image
