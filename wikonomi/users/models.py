from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django_resized import ResizedImageField
from django.utils import timezone
from django.templatetags.static import static
import uuid


DEFAULT_PROFILE_PICTURE = 'profile_pics/default.jpg'
DEFAULT_PROFILE_PICTURE_STATIC = 'img/default-profile.svg'


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = ResizedImageField(
        upload_to='profile_pics/', 
        default=DEFAULT_PROFILE_PICTURE,
        null=True, 
        blank=True,
        size=[300, 300], 
        quality=85, 
        force_format='JPEG'
    )
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.UUIDField(default=uuid.uuid4, editable=False)
    email_verification_sent_at = models.DateTimeField(null=True, blank=True)
    deletion_notifications_enabled = models.BooleanField(default=True)
    

    @property
    def has_custom_profile_picture(self):
        """Return True when the user uploaded a non-default profile picture."""
        picture_name = getattr(self.profile_picture, 'name', '')
        return bool(picture_name and picture_name != DEFAULT_PROFILE_PICTURE)

    @property
    def profile_picture_url(self):
        """Return the custom profile picture URL or the bundled default avatar."""
        if self.has_custom_profile_picture:
            try:
                return self.profile_picture.url
            except Exception:
                pass
        return static(DEFAULT_PROFILE_PICTURE_STATIC)
    
    def generate_verification_token(self):
        self.email_verification_token = uuid.uuid4()
        self.email_verification_sent_at = timezone.now()
        self.save()
        return self.email_verification_token
    
    def verify_email(self):
        """Mark email as verified and track for analytics"""
        self.email_verified = True
        self.save()
        
        # Track email verification for analytics
        try:
            from wikonomi.analytics.models import track_email_verification
            track_email_verification(self.user)
        except ImportError:
            pass  # Analytics app not yet installed
    
    def is_verification_token_valid(self, token, max_age_hours=24):
        if self.email_verification_token != token:
            return False
        if not self.email_verification_sent_at:
            return False
        time_diff = timezone.now() - self.email_verification_sent_at
        return time_diff.total_seconds() <= max_age_hours * 3600
    
    def __str__(self):
        return f'{self.user.username} Profile'

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a profile for new users"""
    if created:
        Profile.objects.create(user=instance)
    else:
        # Just in case an existing user doesn't have a profile
        if hasattr(instance, 'profile'):
            pass
        else:
            Profile.objects.create(user=instance)
