from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
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
                print(f"DEBUG: User created successfully: {user.username}")
                
                profile, created = Profile.objects.get_or_create(user=user)
                print(f"DEBUG: Profile {'created' if created else 'retrieved'} for user: {user.username}")
                
                # Send verification email - DISABLED
                if False and settings.ACCOUNT_VERIFICATION_REQUIRED:
                    try:
                        print(f"DEBUG: Attempting to send verification email to {user.email}")
                        print(f"DEBUG: Email settings - Host: {settings.EMAIL_HOST}, User: {settings.EMAIL_HOST_USER}")
                        
                        email_sent = send_verification_email(request, user, profile)
                        print(f"DEBUG: Email sending result: {email_sent}")
                        
                        if email_sent:
                            messages.info(request, 'Account created successfully! Please check your email to verify your account.')
                        else:
                            messages.warning(request, 'Account created but we couldn\'t send a verification email. Please contact support.')
                    except Exception as e:
                        print(f"DEBUG: Email sending failed with error: {str(e)}")
                        import traceback
                        traceback.print_exc()
                        messages.error(request, f'Account created but email sending failed: {str(e)}')
                else:
                    messages.success(request, 'Account created successfully!')
                
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                return redirect('home')
                
            except Exception as e:
                print(f"DEBUG: User creation failed: {str(e)}")
                import traceback
                traceback.print_exc()
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
            return redirect('home')
    else:
        form = AuthenticationForm()
    return render(request, 'users/login.html', {'form': form})

@login_required
def profile(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    return render(request, 'users/profile.html', {'profile': profile})

@login_required
def edit_profile(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Handle profile picture upload
        if 'profile_picture' in request.FILES:
            profile.profile_picture = request.FILES['profile_picture']
            profile.save()
            messages.success(request, 'Profile picture updated successfully!')
        
        # Update user profile information
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.save()
        
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
