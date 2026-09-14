from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import PriceLike


@receiver(post_save, sender=PriceLike)
def refresh_price_when_accuracy_is_confirmed(sender, instance, created, **kwargs):
    """Treat a newly recorded Yes/like as a fresh community confirmation.

    Price staleness is based on PriceReport.updated_at. The public "Is this
    price accurate?" Yes button records a PriceLike, so a new confirmation
    must refresh that timestamp as well. Removing an existing confirmation
    does not refresh the report.
    """
    if not created:
        return

    report = instance.price_report
    report.updated_at = timezone.now()
    # Use save() rather than QuerySet.update() so existing PriceReport
    # post-save hooks (including cache invalidation) still run.
    report.save(update_fields=['updated_at'])
