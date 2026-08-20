from allauth.account.signals import user_signed_up
from django.dispatch import receiver

from .signup_flow import SOCIAL_SIGNUP_CREATED_SESSION_KEY


@receiver(user_signed_up)
def mark_social_signup_created(request, user, **kwargs):
    if request is not None and kwargs.get('sociallogin') is not None:
        request.session[SOCIAL_SIGNUP_CREATED_SESSION_KEY] = True
