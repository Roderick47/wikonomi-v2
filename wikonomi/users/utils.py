from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from django.utils import timezone


def send_verification_email(request, user, profile):
    """
    Send email verification email to user
    """
    token = profile.generate_verification_token()
    
    # Build verification URL
    domain = get_current_site(request).domain
    verification_url = f"https://{domain}{reverse('verify_email', kwargs={'token': str(token)})}"
    
    # Render email template
    subject = 'Verify Your Email Address - Wikonomi'
    message = render_to_string('users/email_verification.html', {
        'user': user,
        'verification_url': verification_url,
    })
    
    # Send email
    try:
        send_mail(
            subject=subject,
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending verification email: {e}")
        return False


def send_password_change_notification(request, user):
    """
    Send password change notification email to user
    """
    # Get client IP address
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip_address = x_forwarded_for.split(',')[0]
    else:
        ip_address = request.META.get('REMOTE_ADDR', 'Unknown')
    
    # Render email template
    subject = 'Your Password Has Been Changed - Wikonomi'
    message = render_to_string('users/password_change_notification.html', {
        'user': user,
        'change_time': timezone.now(),
        'ip_address': ip_address,
    })
    
    # Send email
    try:
        send_mail(
            subject=subject,
            message='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending password change notification: {e}")
        return False
