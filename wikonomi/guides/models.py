from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.validators import MaxValueValidator, MinValueValidator
from django_resized import ResizedImageField


class Guide(models.Model):
    CREATION_SOURCE_CHOICES = [
        ('web', 'Website'),
        ('mcp', 'MCP'),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=255, unique=True)
    photo = ResizedImageField(
        upload_to='guide_photos/',
        size=[1600, 1000],
        quality=82,
        force_format='JPEG',
        null=True,
        blank=True,
    )
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
    created_via = models.CharField(max_length=20, choices=CREATION_SOURCE_CHOICES, default='web', db_index=True)
    ai_assisted = models.BooleanField(default=False, db_index=True)
    ai_provider = models.CharField(max_length=80, blank=True)
    ai_model = models.CharField(max_length=120, blank=True)
    ai_confidence = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    ai_source_note = models.TextField(blank=True)
    mcp_idempotency_key = models.CharField(max_length=160, null=True, blank=True, unique=True)
    marked_for_deletion = models.BooleanField(default=False)
    marked_for_deletion_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='marked_guides_for_deletion',
    )
    marked_for_deletion_at = models.DateTimeField(null=True, blank=True)
    deletion_reason = models.TextField(blank=True)
    deletion_votes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='confirmed_guide_deletions',
    )

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title

    @property
    def average_rating(self):
        return self.ratings.aggregate(avg=models.Avg('score'))['avg'] or 0

    def can_delete(self, user):
        return bool(
            user.is_authenticated
            and (user.is_staff or user.is_superuser or self.created_by_id == user.id)
        )

    def mark_for_deletion(self, user, reason=''):
        self.marked_for_deletion = True
        self.marked_for_deletion_by = user
        self.marked_for_deletion_at = timezone.now()
        self.deletion_reason = reason
        self.save(update_fields=[
            'marked_for_deletion', 'marked_for_deletion_by',
            'marked_for_deletion_at', 'deletion_reason',
        ])


class GuideVersion(models.Model):
    STATUS_CHOICES = [('published', 'Published'), ('pending', 'Pending Review'), ('rejected', 'Rejected')]
    guide = models.ForeignKey(Guide, on_delete=models.CASCADE, related_name='versions')
    edited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='published')
    edit_summary = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_via = models.CharField(max_length=20, choices=Guide.CREATION_SOURCE_CHOICES, default='web', db_index=True)
    ai_assisted = models.BooleanField(default=False, db_index=True)
    ai_provider = models.CharField(max_length=80, blank=True)
    ai_model = models.CharField(max_length=120, blank=True)
    ai_confidence = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    ai_source_note = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.guide} ({self.created_at:%Y-%m-%d %H:%M})'


class GuideReference(models.Model):
    version = models.ForeignKey(GuideVersion, on_delete=models.CASCADE, related_name='references')
    title = models.CharField(max_length=300)
    url = models.URLField(max_length=2048)
    publisher = models.CharField(max_length=180, blank=True)
    accessed_at = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.title


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
    downvotes = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-upvotes']

    def __str__(self):
        return self.body

    @property
    def score(self):
        return self.upvotes - self.downvotes


class StepTipVote(models.Model):
    tip = models.ForeignKey(StepTip, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='guide_tip_votes')
    value = models.SmallIntegerField(choices=[(1, 'Upvote'), (-1, 'Downvote')])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['tip', 'user'], name='unique_tip_vote_per_user')]

    def __str__(self):
        return f'{self.user} voted {self.value} on tip {self.tip_id}'


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


class GuideQuestion(models.Model):
    guide = models.ForeignKey(Guide, on_delete=models.CASCADE, related_name='questions')
    step = models.ForeignKey(Step, on_delete=models.SET_NULL, related_name='questions', null=True, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='guide_questions')
    body = models.TextField(max_length=1200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.body[:80]

    @property
    def is_answered(self):
        return self.answers.filter(is_accepted=True).exists()


class GuideAnswer(models.Model):
    question = models.ForeignKey(GuideQuestion, on_delete=models.CASCADE, related_name='answers')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='guide_answers')
    upvoters = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='upvoted_guide_answers',
    )
    upvote_count = models.PositiveIntegerField(default=0)
    body = models.TextField(max_length=2000)
    is_accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_accepted', '-upvote_count', 'created_at']

    def __str__(self):
        return f'Answer to question {self.question_id}'
