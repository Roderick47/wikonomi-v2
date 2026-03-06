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
    try:
        print(f"DEBUG: Starting email verification process for {user.email}")
        
        token = profile.generate_verification_token()
        print(f"DEBUG: Generated token: {token}")
        
        # Build verification URL
        domain = 'www.wikonomi.com'  # Hardcode for production
        verification_url = f"https://{domain}{reverse('verify_email', kwargs={'token': str(token)})}"
        print(f"DEBUG: Verification URL: {verification_url}")
        
        # Render email template
        subject = 'Verify Your Email Address - Wikonomi'
        message = render_to_string('users/email_verification.html', {
            'user': user,
            'verification_url': verification_url,
        })
        print(f"DEBUG: Email template rendered successfully")
        
        # Send email
        print(f"DEBUG: Attempting to send email via {settings.EMAIL_HOST}:{settings.EMAIL_PORT}")
        print(f"DEBUG: From: {settings.DEFAULT_FROM_EMAIL}, To: {user.email}")
        print(f"DEBUG: TLS enabled: {settings.EMAIL_USE_TLS}")
        print(f"DEBUG: Email user: {settings.EMAIL_HOST_USER}")
        print(f"DEBUG: Has password: {'Yes' if settings.EMAIL_HOST_PASSWORD else 'No'}")
        
        try:
            result = send_mail(
                subject=subject,
                message='',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=message,
                fail_silently=False,  # Change to False to see actual errors
            )
            print(f"DEBUG: send_mail returned: {result}")
            return result > 0  # Return True if email was sent successfully
        except Exception as e:
            print(f"DEBUG: SMTP Exception: {str(e)}")
            print(f"DEBUG: Exception type: {type(e).__name__}")
            return False
        
    except Exception as e:
        print(f"DEBUG: Exception in send_verification_email: {str(e)}")
        import traceback
        traceback.print_exc()
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
