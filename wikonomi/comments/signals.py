from django.db.models import F
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Comment, CommentFlag, CommentLike


@receiver(post_save, sender=Comment)
def increment_parent_reply_count(sender, instance, created, **kwargs):
    if created and instance.parent_id:
        Comment.objects.filter(pk=instance.parent_id).update(reply_count=F('reply_count') + 1)


@receiver(post_delete, sender=Comment)
def decrement_parent_reply_count(sender, instance, **kwargs):
    if instance.parent_id:
        Comment.objects.filter(pk=instance.parent_id, reply_count__gt=0).update(reply_count=F('reply_count') - 1)


@receiver(post_save, sender=CommentLike)
def increment_like_count(sender, instance, created, **kwargs):
    if created:
        Comment.objects.filter(pk=instance.comment_id).update(like_count=F('like_count') + 1)


@receiver(post_delete, sender=CommentLike)
def decrement_like_count(sender, instance, **kwargs):
    Comment.objects.filter(pk=instance.comment_id, like_count__gt=0).update(like_count=F('like_count') - 1)


@receiver(post_save, sender=CommentFlag)
def mark_flagged(sender, instance, created, **kwargs):
    if created:
        Comment.objects.filter(pk=instance.comment_id).update(is_flagged=True)
