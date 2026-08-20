from django.urls import path
from . import views
from . import signup_flow

urlpatterns = [
    path('signup/', signup_flow.signup, name='signup'),
    path('signup/complete/', signup_flow.signup_gateway, name='signup_gateway'),
    path('welcome/', signup_flow.welcome, name='welcome'),
    path('welcome/continue/', signup_flow.welcome_continue, name='welcome_continue'),
    path('welcome/explore/', signup_flow.welcome_explore, name='welcome_explore'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('onboarding/', views.update_onboarding, name='update_onboarding'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('profile/delete/', views.delete_account, name='delete_account'),
    path('verify-email/<uuid:token>/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification_email, name='resend_verification'),
]
