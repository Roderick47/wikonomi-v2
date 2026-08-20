from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import CustomUserCreationForm
from .models import Profile


POST_SIGNUP_RETURN_URL_SESSION_KEY = 'post_signup_return_url'
WELCOME_PENDING_SESSION_KEY = 'welcome_after_signup_pending'
SOCIAL_SIGNUP_CREATED_SESSION_KEY = 'social_signup_created'


def _safe_next_url(request, value):
    if value and url_has_allowed_host_and_scheme(
        value,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return value
    return ''


def _signup_context(request, form, next_url):
    gateway = reverse('signup_gateway')
    if next_url:
        gateway = f'{gateway}?{urlencode({"return_to": next_url})}'
    return {
        'form': form,
        'next': next_url,
        'google_signup_next': gateway,
    }


def signup(request):
    """Create an email account, then show the one-time Wikonomi welcome page."""
    next_url = _safe_next_url(
        request,
        request.POST.get('next') if request.method == 'POST' else request.GET.get('next'),
    )

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                Profile.objects.get_or_create(user=user)

                # Existing email verification delivery is currently disabled in v2.
                messages.success(request, 'Account created successfully!')
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')

                if next_url:
                    request.session[POST_SIGNUP_RETURN_URL_SESSION_KEY] = next_url
                else:
                    request.session.pop(POST_SIGNUP_RETURN_URL_SESSION_KEY, None)
                request.session[WELCOME_PENDING_SESSION_KEY] = True

                return redirect('welcome')
            except Exception as exc:
                import logging

                logging.getLogger(__name__).error('User creation failed: %s', exc)
                messages.error(request, f'Account creation failed: {exc}')
        return render(request, 'users/signup.html', _signup_context(request, form, next_url))

    form = CustomUserCreationForm()
    return render(request, 'users/signup.html', _signup_context(request, form, next_url))


@login_required
def signup_gateway(request):
    """Finish Google auth without showing welcome to an existing Google user."""
    return_to = _safe_next_url(request, request.GET.get('return_to'))
    created = request.session.pop(SOCIAL_SIGNUP_CREATED_SESSION_KEY, False)

    if not created:
        return redirect(return_to or 'home')

    if return_to:
        request.session[POST_SIGNUP_RETURN_URL_SESSION_KEY] = return_to
    else:
        request.session.pop(POST_SIGNUP_RETURN_URL_SESSION_KEY, None)
    request.session[WELCOME_PENDING_SESSION_KEY] = True
    return redirect('welcome')


@login_required
def welcome(request):
    if not request.session.get(WELCOME_PENDING_SESSION_KEY):
        return redirect('home')

    return render(
        request,
        'users/welcome.html',
        {
            'has_return_destination': bool(
                request.session.get(POST_SIGNUP_RETURN_URL_SESSION_KEY)
            )
        },
    )


@login_required
def welcome_continue(request):
    destination = _safe_next_url(
        request,
        request.session.pop(POST_SIGNUP_RETURN_URL_SESSION_KEY, ''),
    )
    request.session.pop(WELCOME_PENDING_SESSION_KEY, None)
    return redirect(destination or 'home')


@login_required
def welcome_explore(request):
    request.session.pop(POST_SIGNUP_RETURN_URL_SESSION_KEY, None)
    request.session.pop(WELCOME_PENDING_SESSION_KEY, None)
    return redirect('home')
