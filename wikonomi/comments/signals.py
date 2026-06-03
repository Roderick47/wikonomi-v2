from django.db.models import F
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Comment, CommentFlag, CommentLike


def _notification_targets_for_comment(comment):
    """Return Notification FK kwargs for the object a comment belongs to."""
    from core.models import Business, PriceReport, Product

    target = comment.content_object
    targets = {'product': None, 'price_report': None, 'business': None}
    if isinstance(target, PriceReport):
        targets['product'] = target.product
        targets['price_report'] = target
    elif isinstance(target, Product):
        targets['product'] = target
    elif isinstance(target, Business):
        targets['business'] = target
    return targets


def _comment_thread_owner(comment):
    """Return the user who should get new top-level comment notifications."""
    from core.models import PriceReport, Product

    target = comment.content_object
    if isinstance(target, PriceReport):
        return target.user
    if isinstance(target, Product):
        return target.created_by
    return None


def _has_muted_similar_notification(user, notification_type, targets):
    from core.models import Notification

    filters = {
        'user': user,
        'notification_type': notification_type,
        'muted': True,
        'product': targets.get('product'),
        'price_report': targets.get('price_report'),
        'business': targets.get('business'),
    }
    return Notification.objects.filter(**filters).exists()


def _create_comment_notification(user, notification_type, message, targets):
    from core.models import Notification

    if not user or _has_muted_similar_notification(user, notification_type, targets):
        return None
    return Notification.objects.create(
        user=user,
        notification_type=notification_type,
        message=message,
        **targets,
    )


@receiver(post_save, sender=Comment)
def handle_comment_created(sender, instance, created, **kwargs):
    if not created:
        return

    targets = _notification_targets_for_comment(instance)
    if instance.parent_id:
        Comment.objects.filter(pk=instance.parent_id).update(reply_count=F('reply_count') + 1)
        if instance.parent.user_id != instance.user_id:
            from core.models import Notification

            _create_comment_notification(
                user=instance.parent.user,
                notification_type=Notification.TYPE_REPLY,
                message=f'{instance.user.username} replied to your comment.',
                targets=targets,
            )
        return

    owner = _comment_thread_owner(instance)
    if owner and owner.id != instance.user_id:
        from core.models import Notification

        _create_comment_notification(
            user=owner,
            notification_type=Notification.TYPE_COMMENT,
            message=f'{instance.user.username} commented on your post.',
            targets=targets,
        )


@receiver(post_delete, sender=Comment)
def decrement_parent_reply_count(sender, instance, **kwargs):
    if instance.parent_id:
        Comment.objects.filter(pk=instance.parent_id, reply_count__gt=0).update(reply_count=F('reply_count') - 1)


@receiver(post_save, sender=CommentLike)
def handle_comment_like_created(sender, instance, created, **kwargs):
    if not created:
        return

    Comment.objects.filter(pk=instance.comment_id).update(like_count=F('like_count') + 1)
    if instance.comment.user_id == instance.user_id:
        return

    from core.models import Notification

    _create_comment_notification(
        user=instance.comment.user,
        notification_type=Notification.TYPE_COMMENT_LIKE,
        message=f'{instance.user.username} liked your comment.',
        targets=_notification_targets_for_comment(instance.comment),
    )


@receiver(post_delete, sender=CommentLike)
def decrement_like_count(sender, instance, **kwargs):
    Comment.objects.filter(pk=instance.comment_id, like_count__gt=0).update(like_count=F('like_count') - 1)


@receiver(post_save, sender=CommentFlag)
def mark_flagged(sender, instance, created, **kwargs):
    if created:
        Comment.objects.filter(pk=instance.comment_id).update(is_flagged=True)
