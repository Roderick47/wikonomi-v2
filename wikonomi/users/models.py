from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django_resized import ResizedImageField

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = ResizedImageField(
        upload_to='profile_pics/', 
        default='profile_pics/default.jpg',
        null=True, 
        blank=True,
        size=[300, 300], 
        quality=85, 
        force_format='JPEG'
    )
    
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
