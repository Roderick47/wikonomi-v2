from django.db import models
from django.contrib.auth.models import User
from taggit.managers import TaggableManager
import h3
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django_resized import ResizedImageField

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    image = ResizedImageField(upload_to='product_images/', null=True, blank=True, size=[1000, 1000], quality=75, force_format='JPEG')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    tags = TaggableManager()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Business(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(unique=True)
    image = ResizedImageField(upload_to='business_images/', null=True, blank=True, size=[1000, 1000], quality=75, force_format='JPEG')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class PriceReport(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='price_reports')
    business = models.ForeignKey(Business, on_delete=models.SET_NULL, null=True, blank=True, related_name='price_reports')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='price_reports')
    last_edited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='edited_price_reports')
    
    price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='PGK')
    
    image = ResizedImageField(upload_to='price_report_images/', null=True, blank=True, size=[1000, 1000], quality=75, force_format='JPEG')
    
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
    observed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)

    # H3 for fast "same vicinity" comparison
    h3_res9 = models.CharField(max_length=16, null=True, blank=True, db_index=True)
    h3_res8 = models.CharField(max_length=16, null=True, blank=True, db_index=True)

    class Meta:
        ordering = ['-observed_at']

    def __str__(self):
        return f"{self.price} {self.currency} — {self.product}"

    def get_lat_lng(self):
        return (self.latitude, self.longitude) if self.latitude and self.longitude else None

class PriceHistory(models.Model):
    price_report = models.ForeignKey(PriceReport, on_delete=models.CASCADE, related_name='price_history')
    old_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    new_price = models.DecimalField(max_digits=12, decimal_places=2)
    old_currency = models.CharField(max_length=3, null=True, blank=True)
    new_currency = models.CharField(max_length=3, default='PGK')
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f"Price change for {self.price_report.product}: {self.old_price} → {self.new_price}"

# Auto H3 population
@receiver(pre_save, sender=PriceReport)
def populate_h3_index(sender, instance, **kwargs):
    lat = getattr(instance, 'latitude', None)
    lng = getattr(instance, 'longitude', None)
    if lat is not None and lng is not None:
        try:
            instance.h3_res9 = h3.latlng_to_cell(lat, lng, 9)
            instance.h3_res8 = h3.latlng_to_cell(lat, lng, 8)
        except Exception:
            instance.h3_res9 = None
            instance.h3_res8 = None

class ProductWatchlist(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='watched_products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='watchers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.username} watching {self.product.name}"

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='notifications')
    price_report = models.ForeignKey(PriceReport, on_delete=models.CASCADE)
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message}"

@receiver(post_save, sender=PriceHistory)
def create_price_change_notification(sender, instance, created, **kwargs):
    if created:
        product = instance.price_report.product
        # Temporarily removing .exclude(user=instance.changed_by) so you can test with your own account
        watchers = ProductWatchlist.objects.filter(product=product)
        
        for watch in watchers:
            message = f"Price change alert: {product.name} changed from {instance.old_price} to {instance.new_price} at {instance.price_report.business.name if instance.price_report.business else 'a location'}."
            Notification.objects.create(
                user=watch.user,
                product=product,
                price_report=instance.price_report,
                message=message
            )

@receiver(post_save, sender=PriceReport)
def create_new_price_notification(sender, instance, created, **kwargs):
    if created:
        product = instance.product
        # Temporarily removing .exclude(user=instance.user) so you can test with your own account
        watchers = ProductWatchlist.objects.filter(product=product)
        
        for watch in watchers:
            message = f"New price alert: {product.name} is now {instance.price} at {instance.business.name if instance.business else 'a new location'}."
            Notification.objects.create(
                user=watch.user,
                product=product,
                price_report=instance,
                message=message
            )

class ShoppingList(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shopping_lists')
    name = models.CharField(max_length=255, default="My Shopping List")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} ({self.user.username})"

class ShoppingListItem(models.Model):
    shopping_list = models.ForeignKey(ShoppingList, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    item_name = models.CharField(max_length=255, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    is_checked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['is_checked', '-created_at']

    def __str__(self):
        return self.item_name or (self.product.name if self.product else "Unknown Item")
