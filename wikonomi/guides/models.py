from django.conf import settings
from django.db import models
from django_resized import ResizedImageField


class Guide(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    organization = models.ForeignKey(
        'core.Business',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='guides',
    )
    category = models.ForeignKey(
        'categories.BusinessCategory',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='guides',
    )
    summary = models.TextField(blank=True)
    forked_from = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='forks',
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    current_version = models.ForeignKey(
        'GuideVersion',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title

    @property
    def average_rating(self):
        return self.ratings.aggregate(avg=models.Avg('score'))['avg'] or 0


class GuideVersion(models.Model):
    STATUS_CHOICES = [('published', 'Published'), ('pending', 'Pending Review'), ('rejected', 'Rejected')]
    guide = models.ForeignKey(Guide, on_delete=models.CASCADE, related_name='versions')
    edited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='published')
    edit_summary = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.guide} ({self.created_at:%Y-%m-%d %H:%M})'


class Step(models.Model):
    version = models.ForeignKey(GuideVersion, on_delete=models.CASCADE, related_name='steps')
    position = models.FloatField()
    title = models.CharField(max_length=120, blank=True)
    instruction = models.TextField()

    class Meta:
        ordering = ['position']

    def __str__(self):
        return self.title or self.instruction[:80]


class StepPhoto(models.Model):
    step = models.ForeignKey(Step, on_delete=models.CASCADE, related_name='photos')
    image = ResizedImageField(upload_to='guide_step_photos/', size=[1200, 1200], quality=80, force_format='JPEG')
    caption = models.CharField(max_length=160, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return self.caption or f'Photo for step {self.step_id}'


class StepTip(models.Model):
    step = models.ForeignKey(Step, on_delete=models.CASCADE, related_name='tips')
    body = models.CharField(max_length=300)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    upvotes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-upvotes']

    def __str__(self):
        return self.body


class GuideRating(models.Model):
    guide = models.ForeignKey(Guide, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    score = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('guide', 'user')


class StepTipPhoto(models.Model):
    tip = models.ForeignKey(StepTip, on_delete=models.CASCADE, related_name='photos')
    image = ResizedImageField(upload_to='guide_tip_photos/', size=[1200, 1200], quality=80, force_format='JPEG')
    caption = models.CharField(max_length=160, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return self.caption or f'Photo for tip {self.tip_id}'
