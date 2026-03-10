from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from django.utils import timezone


def send_verification_email(request, user, profile):
    """
    Send email verification email to user
    EMAIL FUNCTIONALITY DISABLED
    """
    print(f"DEBUG: Email verification disabled for {user.email}")
    return True  # Return True to prevent errors


def send_password_change_notification(request, user):
    """
    Send password change notification email to user
    EMAIL FUNCTIONALITY DISABLED
    """
    print(f"DEBUG: Password change notification disabled for {user.email}")
    return True  # Return True to prevent errors
