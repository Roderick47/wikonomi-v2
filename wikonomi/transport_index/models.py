import uuid

from django.db import models
from django.utils import timezone
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
    profile_completeness = models.CharField(max_length=20, choices=ProfileCompleteness.choices, default=ProfileCompleteness.MINIMAL)
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

    def whatsapp_deep_link(self, text='Hi, I found your cab on Wikonomi. Are you available?'):
        from urllib.parse import quote
        return f'https://wa.me/{self.whatsapp_number}?text={quote(text)}'


class CabStatus(models.Model):
    class Availability(models.TextChoices):
        AVAILABLE = 'available', 'Available'
        BUSY = 'busy', 'Busy'
        OFFLINE = 'offline', 'Offline'

    driver = models.OneToOneField(CabDriver, on_delete=models.CASCADE, related_name='status')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    area_label = models.CharField(max_length=120, blank=True)
    availability = models.CharField(max_length=20, choices=Availability.choices, default=Availability.OFFLINE)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'cab statuses'

    def __str__(self):
        return f'{self.driver.display_name}: {self.get_availability_display()}'

    def last_seen_minutes(self):
        return max(0, int((timezone.now() - self.last_updated).total_seconds() // 60))


class ContactAttempt(models.Model):
    driver = models.ForeignKey(CabDriver, on_delete=models.CASCADE, related_name='contact_attempts')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Contact {self.driver} at {self.created_at:%Y-%m-%d %H:%M}'


class RouterEvent(models.Model):
    class Stage(models.TextChoices):
        LOCATION_UPDATE = 'location_update', 'Driver location update'
        KEYWORD_MATCH = 'keyword_match', 'Keyword match'
        WIZARD_STEP = 'wizard_step', 'Wizard step'
        RIDER_LOCATION = 'rider_location', 'Rider location search'
        GAZETTEER_HIT = 'gazetteer_hit', 'Gazetteer hit'
        LLM_FALLBACK = 'llm_fallback', 'LLM fallback'
        UNHANDLED = 'unhandled', 'Unhandled'

    phone_number = models.CharField(max_length=32, blank=True, db_index=True)
    stage = models.CharField(max_length=32, choices=Stage.choices, db_index=True)
    message_type = models.CharField(max_length=32, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class LLMFallbackLog(models.Model):
    input_text = models.TextField()
    extracted_intent = models.CharField(max_length=120, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    estimated_cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
