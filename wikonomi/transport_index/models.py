import uuid

from django.db import models
from django.utils.text import slugify


class CabDriver(models.Model):
    class VehicleType(models.TextChoices):
        TAXI = 'taxi', 'Taxi'
        PMV = 'pmv', 'PMV'
        INFORMAL = 'informal', 'Informal'

    class ProfileCompleteness(models.TextChoices):
        MINIMAL = 'minimal', 'Minimal'
        COMPLETE = 'complete', 'Complete'

    whatsapp_number = models.CharField(max_length=32, unique=True, db_index=True)
    display_name = models.CharField(max_length=120)
    vehicle_type = models.CharField(max_length=20, choices=VehicleType.choices)
    vehicle_make_model = models.CharField(max_length=120, blank=True)
    vehicle_plate = models.CharField(max_length=40)
    profile_photo = models.ImageField(upload_to='transport_index/profile_photos/', blank=True)
    vehicle_photo = models.ImageField(upload_to='transport_index/vehicle_photos/', blank=True)
    bio = models.CharField(max_length=300, blank=True)
    home_area = models.CharField(max_length=120, blank=True)
    profile_completeness = models.CharField(
        max_length=20,
        choices=ProfileCompleteness.choices,
        default=ProfileCompleteness.MINIMAL,
    )
    is_verified = models.BooleanField(default=False)
    is_active_listing = models.BooleanField(default=True)
    slug = models.SlugField(max_length=160, unique=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_name']

    def __str__(self):
        return self.display_name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._generate_unique_slug()
        super().save(*args, **kwargs)

    def _generate_unique_slug(self):
        base_slug = slugify(self.display_name) or 'cab-driver'

        while True:
            candidate = f'{base_slug}-{uuid.uuid4().hex[:8]}'
            if not CabDriver.objects.filter(slug=candidate).exists():
                return candidate


class CabStatus(models.Model):
    class Availability(models.TextChoices):
        AVAILABLE = 'available', 'Available'
        BUSY = 'busy', 'Busy'
        OFFLINE = 'offline', 'Offline'

    driver = models.OneToOneField(
        CabDriver,
        on_delete=models.CASCADE,
        related_name='status',
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    area_label = models.CharField(max_length=120, blank=True)
    availability = models.CharField(
        max_length=20,
        choices=Availability.choices,
        default=Availability.OFFLINE,
    )
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'cab statuses'

    def __str__(self):
        return f'{self.driver.display_name}: {self.get_availability_display()}'
