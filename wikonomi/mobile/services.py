from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from core.models import PriceReport
from .models import MobileSubmission


@transaction.atomic
def approve_submission(submission_id, reviewer):
    """Publish once, even when two reviewers act at the same time."""
    if not reviewer.is_active or not reviewer.is_staff:
        raise PermissionDenied("Staff review required.")

    submission = (
        MobileSubmission.objects.select_for_update()
        .select_related("business_branch__canonical_business", "product")
        .get(pk=submission_id)
    )
    if submission.status != MobileSubmission.Status.PENDING:
        return None

    branch = submission.business_branch
    if not branch.is_active:
        raise ValueError("The selected store branch is inactive.")

    report = PriceReport.objects.create(
        product=submission.product,
        business=branch.canonical_business,
        business_branch=branch,
        user=submission.contributor,
        price=submission.price,
        currency="PGK",
        image=submission.photo.name,  # Same persistent storage; no duplicate upload.
        latitude=branch.latitude,
        longitude=branch.longitude,
        notes="Price contributed through Wikonomi mobile.",
    )
    # The original time the contributor saw the price matters for freshness.
    PriceReport.objects.filter(pk=report.pk).update(
        observed_at=submission.observed_at,
    )
    submission.status = MobileSubmission.Status.APPROVED
    submission.published_report = report
    submission.reviewed_by = reviewer
    submission.reviewed_at = timezone.now()
    submission.save(update_fields=[
        "status", "published_report", "reviewed_by", "reviewed_at",
    ])
    return report


@transaction.atomic
def reject_submission(submission_id, reviewer):
    if not reviewer.is_active or not reviewer.is_staff:
        raise PermissionDenied("Staff review required.")
    submission = (
        MobileSubmission.objects.select_for_update().get(pk=submission_id)
    )
    if submission.status != MobileSubmission.Status.PENDING:
        return False
    submission.status = MobileSubmission.Status.REJECTED
    submission.reviewed_by = reviewer
    submission.reviewed_at = timezone.now()
    submission.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    return True
