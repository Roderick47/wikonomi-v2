from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'catalog'
    verbose_name = 'Product Catalog Identity'

    def ready(self):
        from .compat import install_core_product_matching_adapter
        from . import signals  # noqa: F401

        install_core_product_matching_adapter()
