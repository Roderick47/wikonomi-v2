from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Load model classes that live outside models.py so Django registers them.
        try:
            import core.price_photo_models  # noqa: F401
        except Exception:
            pass
