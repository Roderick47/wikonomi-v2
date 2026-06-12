from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=60, blank=True, help_text="Tabler icon class e.g. ti-basket")
    is_png_specific = models.BooleanField(default=False, help_text="Category unique to PNG informal economy")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name


class Subcategory(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100)
    slug = models.SlugField()
    examples = models.CharField(max_length=255, blank=True, help_text="Comma-separated examples shown as hints")
    is_png_specific = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        unique_together = [['category', 'slug']]
        verbose_name_plural = 'subcategories'

    def __str__(self):
        return f"{self.category.name} › {self.name}"


class BusinessCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    icon = models.CharField(max_length=60, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = 'business categories'

    def __str__(self):
        return self.name


class BusinessSubcategory(models.Model):
    category = models.ForeignKey(BusinessCategory, on_delete=models.CASCADE, related_name='subcategories')
    name = models.CharField(max_length=100)
    slug = models.SlugField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        unique_together = [['category', 'slug']]
        verbose_name_plural = 'business subcategories'

    def __str__(self):
        return f"{self.category.name} › {self.name}"
