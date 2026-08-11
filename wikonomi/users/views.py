from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.generic import RedirectView
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.exceptions import ValidationError
from PIL import Image
import io
import os
from .forms import CustomUserCreationForm, ProfileUpdateForm
from .models import Profile
from .utils import send_verification_email, send_password_change_notification
from django.conf import settings

def signup(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                
                profile, created = Profile.objects.get_or_create(user=user)
                
                # Send verification email - DISABLED
                if False and settings.ACCOUNT_VERIFICATION_REQUIRED:
                    try:
                        email_sent = send_verification_email(request, user, profile)
                        
                        if email_sent:
                            messages.info(request, 'Account created successfully! Please check your email to verify your account.')
                        else:
                            messages.warning(request, 'Account created but we couldn\'t send a verification email. Please contact support.')
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f'Email sending failed: {str(e)}')
                        messages.error(request, f'Account created but email sending failed: {str(e)}')
                else:
                    messages.success(request, 'Account created successfully!')
                
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                
                # Handle redirect to next URL if provided
                next_url = request.POST.get('next')
                if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=[request.get_host()], require_https=request.is_secure()):
                    return redirect(next_url)
                return redirect('home')
                
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f'User creation failed: {str(e)}')
                messages.error(request, f'Account creation failed: {str(e)}')
                return render(request, 'users/signup.html', {'form': form})
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/signup.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, 'Welcome back!')
            
            # Handle redirect to next URL if provided
            next_url = request.POST.get('next')
            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=[request.get_host()], require_https=request.is_secure()):
                return redirect(next_url)
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'users/login.html', {'form': form})

def get_analytics_dashboard_url(user):
    """Return the analytics dashboard URL name available to this user, if any."""
    if user.is_superuser:
        return 'analytics:dashboard'

    access = getattr(user, 'dashboard_access', None)
    if not access or not access.is_active:
        return None

    role_url_names = {
        'founder': 'analytics:dashboard',
        'team': 'analytics:users',
        'investor': 'analytics:investor',
    }
    return role_url_names.get(access.role)


@login_required
def profile(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    analytics_dashboard_url = get_analytics_dashboard_url(request.user)
    return render(request, 'users/profile.html', {
        'profile': profile,
        'analytics_dashboard_url': analytics_dashboard_url,
    })


@login_required
@require_POST
def update_onboarding(request):
    """Persist whether a user completed or dismissed the introductory tour."""
    action = request.POST.get('action')
    if action not in {'complete', 'dismiss'}:
        return JsonResponse({'error': 'Invalid onboarding action.'}, status=400)

    profile, _ = Profile.objects.get_or_create(user=request.user)
    now = timezone.now()

    if action == 'complete':
        profile.onboarding_completed_at = now
        profile.onboarding_dismissed_at = None
        profile.save(update_fields=['onboarding_completed_at', 'onboarding_dismissed_at'])
    elif not profile.onboarding_completed_at:
        profile.onboarding_dismissed_at = now
        profile.save(update_fields=['onboarding_dismissed_at'])

    return JsonResponse({
        'ok': True,
        'action': action,
    })


@login_required
def edit_profile(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Handle profile picture upload with validation
        if 'profile_picture' in request.FILES:
            uploaded_file = request.FILES['profile_picture']
            
            # Validate file size (max 5MB)
            max_size = 5 * 1024 * 1024  # 5MB
            if uploaded_file.size > max_size:
                messages.error(request, 'Profile picture must be smaller than 5MB.')
                return render(request, 'users/edit_profile.html', {'profile': profile})
            
            # Validate file type
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if uploaded_file.content_type not in allowed_types:
                messages.error(request, 'Profile picture must be a valid image file (JPEG, PNG, GIF, or WebP).')
                return render(request, 'users/edit_profile.html', {'profile': profile})
            
            # Validate image content
            try:
                # Open and validate the image
                image = Image.open(uploaded_file)
                
                # Verify it's actually an image
                image.verify()
                
                # Re-open after verify (verify() closes the file)
                image = Image.open(uploaded_file)
                
                # Convert to RGB if necessary (for JPEG compatibility)
                if image.mode in ('RGBA', 'LA', 'P'):
                    image = image.convert('RGB')
                
                # Resize if too large (max 800x800)
                max_dimension = 800
                if image.width > max_dimension or image.height > max_dimension:
                    image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
                
                # Save to memory buffer
                buffer = io.BytesIO()
                image.save(buffer, format='JPEG', quality=85, optimize=True)
                buffer.seek(0)
                
                # Create new InMemoryUploadedFile with processed image
                processed_file = InMemoryUploadedFile(
                    buffer,
                    'profile_picture',
                    f'{uploaded_file.name.split(".")[0]}.jpg',
                    'image/jpeg',
                    buffer.tell(),
                    None
                )
                
                profile.profile_picture = processed_file
                profile.save()
                messages.success(request, 'Profile picture updated successfully!')
                
            except (IOError, ValidationError, Image.UnidentifiedImageError) as e:
                messages.error(request, 'Invalid image file. Please upload a valid image.')
                return render(request, 'users/edit_profile.html', {'profile': profile})
            except Exception as e:
                messages.error(request, f'Error processing image: {str(e)}')
                return render(request, 'users/edit_profile.html', {'profile': profile})
        
        # Update user profile information
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.save()
        profile.deletion_notifications_enabled = request.POST.get('deletion_notifications_enabled') == 'on'
        profile.save(update_fields=['deletion_notifications_enabled'])
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('profile')
    
    return render(request, 'users/edit_profile.html', {'profile': profile})

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            
            # Send password change notification - DISABLED
            # send_password_change_notification(request, user)
            
            messages.success(request, 'Password changed successfully!')
            return redirect('profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'users/change_password.html', {'form': form})

def user_logout(request):
    # Clear all session data to prevent freezing
    request.session.flush()
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('home')


def verify_email(request, token):
    """
    Verify user's email address using the token sent to their email
    """
    try:
        # Find profile with matching token
        profile = get_object_or_404(Profile, email_verification_token=token)
        
        # Check if token is still valid
        if profile.is_verification_token_valid(token):
            profile.email_verified = True
            profile.email_verification_token = None
            profile.email_verification_sent_at = None
            profile.save()
            
            messages.success(request, 'Your email has been verified successfully! Thank you.')
        else:
            messages.error(request, 'This verification link has expired. Please request a new verification email.')
            
    except Exception as e:
        messages.error(request, 'Invalid verification link.')
    
    return redirect('profile')


@login_required
def delete_account(request):
    """
    Delete user account with confirmation
    """
    if request.method == 'POST':
        # Verify password for security
        password = request.POST.get('password')
        if request.user.check_password(password):
            user = request.user
            logout(request)
            user.delete()
            messages.success(request, 'Your account has been deleted successfully. We\'re sorry to see you go!')
            return redirect('home')
        else:
            messages.error(request, 'Incorrect password. Account deletion cancelled.')
    
    return render(request, 'users/delete_account.html')


@login_required
def resend_verification_email(request):
    """
    Resend verification email to logged-in user
    EMAIL FUNCTIONALITY DISABLED
    """
    messages.info(request, 'Email verification is currently disabled. Your account is fully active.')
    return redirect('profile')


# Redirect views for django-allauth URLs
def allauth_login_redirect(request):
    """
    Redirect django-allauth login URLs to custom login template
    """
    next_url = request.GET.get('next', '')
    if next_url:
        return redirect(f'/users/login/?next={next_url}')
    return redirect('login')


def allauth_signup_redirect(request):
    """
    Redirect django-allauth signup URLs to custom signup template
    """
    next_url = request.GET.get('next', '')
    if next_url:
        return redirect(f'/users/signup/?next={next_url}')
    return redirect('signup')


def allauth_logout_redirect(request):
    """
    Redirect django-allauth logout URLs to custom logout template
    """
    return redirect('logout')
