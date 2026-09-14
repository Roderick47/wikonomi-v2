import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone


logger = logging.getLogger(__name__)


def send_verification_email(request, user, profile):
    """Send an email-verification link to a Wikonomi user."""
    if not user or not profile or not getattr(user, 'email', ''):
        return False

    try:
        token = profile.generate_verification_token()
        verification_path = reverse('verify_email', kwargs={'token': token})
        verification_url = request.build_absolute_uri(verification_path)
        expiry_hours = max(
            1,
            int(getattr(settings, 'ACCOUNT_VERIFICATION_TOKEN_EXPIRE_MINUTES', 1440) / 60),
        )

        subject = 'Verify your Wikonomi email address'
        text_message = (
            f'Hi {user.username},\n\n'
            'Thanks for joining Wikonomi. Verify your email address by opening this link:\n\n'
            f'{verification_url}\n\n'
            f'This link expires in {expiry_hours} hours.\n\n'
            'If you did not create a Wikonomi account, you can ignore this email.\n\n'
            '— Wikonomi\n'
        )
        html_message = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;color:#1f2937;line-height:1.6">
          <h2 style="margin-bottom:8px">Verify your Wikonomi email</h2>
          <p>Hi {user.username},</p>
          <p>Thanks for joining Wikonomi. Confirm your email address to finish setting up your account.</p>
          <p style="margin:28px 0">
            <a href="{verification_url}" style="background:#6d28d9;color:white;text-decoration:none;padding:12px 20px;border-radius:8px;display:inline-block">
              Verify email address
            </a>
          </p>
          <p>This link expires in {expiry_hours} hours.</p>
          <p style="color:#6b7280;font-size:14px">If you did not create a Wikonomi account, you can ignore this email.</p>
          <p>— Wikonomi</p>
        </div>
        """

        sent_count = send_mail(
            subject=subject,
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
            html_message=html_message,
        )
        return sent_count == 1
    except Exception:
        logger.exception('Failed to send verification email for user_id=%s', getattr(user, 'pk', None))
        return False


def send_password_change_notification(request, user):
    """Notify a Wikonomi user after their password is changed."""
    if not user or not getattr(user, 'email', ''):
        return False

    try:
        changed_at = timezone.now().strftime('%Y-%m-%d %H:%M UTC')
        subject = 'Your Wikonomi password was changed'
        text_message = (
            f'Hi {user.username},\n\n'
            f'Your Wikonomi password was changed on {changed_at}.\n\n'
            'If you made this change, no action is needed. If you did not make this change, '
            'please change your password immediately.\n\n'
            '— Wikonomi\n'
        )
        html_message = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;color:#1f2937;line-height:1.6">
          <h2 style="margin-bottom:8px">Your Wikonomi password was changed</h2>
          <p>Hi {user.username},</p>
          <p>Your Wikonomi password was changed on <strong>{changed_at}</strong>.</p>
          <p>If you made this change, no action is needed. If you did not, please change your password immediately.</p>
          <p>— Wikonomi</p>
        </div>
        """

        sent_count = send_mail(
            subject=subject,
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
            html_message=html_message,
        )
        return sent_count == 1
    except Exception:
        logger.exception('Failed to send password-change notification for user_id=%s', getattr(user, 'pk', None))
        return False
