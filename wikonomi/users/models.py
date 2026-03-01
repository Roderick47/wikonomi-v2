from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from PIL import Image
import os

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pics/', default='profile_pics/default.jpg')
    
    def __str__(self):
        return f'{self.user.username} Profile'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        # Optimize profile picture
        if self.profile_picture and hasattr(self.profile_picture, 'path') and os.path.exists(self.profile_picture.path):
            try:
                img = Image.open(self.profile_picture.path)
                
                # Convert to RGB if necessary (for JPEG compatibility)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize to optimize storage (max 300x300 pixels)
                max_size = (300, 300)
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Save with optimization
                img.save(self.profile_picture.path, 'JPEG', quality=85, optimize=True)
            except Exception:
                pass

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
