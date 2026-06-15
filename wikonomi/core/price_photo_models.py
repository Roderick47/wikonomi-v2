from django.db import models
from django_resized import ResizedImageField


class PriceReportPhoto(models.Model):
    price_report = models.ForeignKey(
        'core.PriceReport',
        on_delete=models.CASCADE,
        related_name='photos',
    )
    image = ResizedImageField(
        upload_to='price_report_photos/',
        size=[1000, 1000],
        quality=75,
        force_format='JPEG',
    )
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'core'
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"Photo for {self.price_report}"
