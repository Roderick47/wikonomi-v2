import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class MobileSubmission(models.Model):
    """An untrusted, reviewable observation; not a public price report."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_submission_id = models.UUIDField(unique=True, db_index=True)
    contributor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="mobile_price_submissions",
    )
    product = models.ForeignKey(
        "core.Product", on_delete=models.PROTECT,
        related_name="mobile_submissions",
    )
    business_branch = models.ForeignKey(
        "core.BusinessBranch", on_delete=models.PROTECT,
        related_name="mobile_submissions",
    )
    price = models.DecimalField(max_digits=12, decimal_places=2)
    photo = models.ImageField(upload_to="mobile_price_evidence/%Y/%m/")
    observed_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING,
        db_index=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="reviewed_mobile_submissions",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)
    published_report = models.OneToOneField(
        "core.PriceReport", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="mobile_submission",
    )

    class Meta:
        ordering = ["-submitted_at"]
        indexes = [
            models.Index(fields=["contributor", "-submitted_at"], name="mobile_sub_contrib_1"),
            models.Index(fields=["status", "-submitted_at"], name="mobile_sub_status_1"),
        ]

    def __str__(self):
        return f"{self.product} · {self.business_branch} · K{self.price}"
