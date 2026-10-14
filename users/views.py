from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login as auth_login, logout as auth_logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User

from .forms import RegistrationForm, PasswordResetRequestForm, PasswordResetConfirmForm
from .models import PasswordResetToken


@require_http_methods(["GET", "POST"])
def register_view(request):
    """
    User registration view.
    GET: Display registration form
    POST: Process registration, create user and profile
    """
    if request.user.is_authenticated:
        return redirect('content:list')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, 'Registration successful! Please log in.')
            return redirect('users:login')
    else:
        form = RegistrationForm()

    return render(request, 'users/register.html', {'form': form})


@require_http_methods(["GET", "POST"])
def login_view(request):
    """
    User login view using Django session authentication.
    GET: Display login form
    POST: Authenticate and create session
    """
    if request.user.is_authenticated:
        return redirect('content:list')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        if email and password:
            # Authenticate using email as username
            user = authenticate(request, username=email, password=password)

            if user is not None:
                auth_login(request, user)
                messages.success(request, f'Welcome back, {user.email}!')

                # Redirect to next parameter or content list
                next_url = request.GET.get('next', 'content:list')
                return redirect(next_url)
            else:
                messages.error(request, 'Invalid email or password.')
        else:
            messages.error(request, 'Please provide both email and password.')

    return render(request, 'users/login.html')


@require_http_methods(["POST"])
@login_required
def logout_view(request):
    """
    User logout view.
    POST only to prevent CSRF logout attacks.
    """
    auth_logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('users:login')


@require_http_methods(["GET", "POST"])
def password_reset_request_view(request):
    """
    Password reset request view.
    Generate token and send email with reset link.
    """
    if request.user.is_authenticated:
        return redirect('content:list')

    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']

            # Look up user by email (timing-safe)
            try:
                user = User.objects.get(email__iexact=email)

                # Generate password reset token
                token_obj = PasswordResetToken.generate_token(user)

                # Send reset email (console backend in development)
                reset_url = request.build_absolute_uri(
                    reverse('users:password_reset_confirm', kwargs={'token': token_obj.token})
                )

                send_mail(
                    subject='Password Reset Request - AI Content Automater',
                    message=f'Click the link below to reset your password:\n\n{reset_url}\n\nThis link expires in 30 minutes.',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )

                messages.success(request, 'Password reset instructions have been sent to your email.')
                return redirect('users:login')

            except User.DoesNotExist:
                # Timing-safe: same message for existing/non-existing users
                messages.success(request, 'If an account exists with this email, password reset instructions have been sent.')
                return redirect('users:login')
    else:
        form = PasswordResetRequestForm()

    return render(request, 'users/password_reset.html', {'form': form})


@require_http_methods(["GET", "POST"])
def password_reset_confirm_view(request, token):
    """
    Password reset confirmation view.
    Validate token and allow user to set new password.
    """
    # Use constant-time comparison via get_object_or_404 (Django does this internally)
    token_obj = get_object_or_404(PasswordResetToken, token=token)

    # Validate token
    if not token_obj.is_valid():
        messages.error(request, 'This password reset link is invalid or has expired.')
        return redirect('users:password_reset')

    if request.method == 'POST':
        form = PasswordResetConfirmForm(request.POST)
        if form.is_valid():
            # Set new password
            user = token_obj.user
            new_password = form.cleaned_data['password1']
            user.set_password(new_password)
            user.save()

            # Mark token as used
            token_obj.mark_as_used()

            messages.success(request, 'Your password has been reset successfully. Please log in.')
            return redirect('users:login')
    else:
        form = PasswordResetConfirmForm()

    return render(request, 'users/password_reset_confirm.html', {
        'form': form,
        'token': token
    })
