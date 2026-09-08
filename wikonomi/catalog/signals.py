from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Product

from .models import ProductIdentity
from .services import ensure_product_identity


@receiver(post_save, sender=Product, dispatch_uid='catalog.ensure_product_identity')
def create_product_identity(sender, instance, created, **kwargs):
    if created:
        ensure_product_identity(
            instance,
            source=ProductIdentity.Source.INFERRED,
        )
