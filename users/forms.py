from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


class RegistrationForm(forms.Form):
    """
    User registration form with email and password.
    Email is used as username for authentication.
    """
    email = forms.EmailField(
        max_length=254,
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email address',
            'autofocus': True
        })
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password'
        }),
        help_text='Minimum 8 characters, not entirely numeric'
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password'
        })
    )

    def clean_email(self):
        """Validate email uniqueness."""
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('A user with this email already exists.')
        return email

    def clean_password2(self):
        """Validate password confirmation match and strength."""
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')

        if password1 and password2:
            if password1 != password2:
                raise ValidationError('Passwords do not match.')

            # Validate password strength using Django's validators
            validate_password(password1)

        return password2

    def save(self):
        """Create new user with email as username and hashed password."""
        email = self.cleaned_data['email']
        password = self.cleaned_data['password1']

        # Create user with email as username
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password
        )

        # UserProfile will be created via signal (to be added)
        # For now, create it directly
        from .models import UserProfile
        UserProfile.objects.create(user=user, role='user')

        return user


class PasswordResetRequestForm(forms.Form):
    """Form for requesting a password reset token."""
    email = forms.EmailField(
        max_length=254,
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email address',
            'autofocus': True
        })
    )

    def clean_email(self):
        """Normalize email (case-insensitive)."""
        return self.cleaned_data.get('email', '').strip().lower()


class PasswordResetConfirmForm(forms.Form):
    """Form for confirming password reset with new password."""
    password1 = forms.CharField(
        label='New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'New password',
            'autofocus': True
        }),
        help_text='Minimum 8 characters, not entirely numeric'
    )
    password2 = forms.CharField(
        label='Confirm New Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        })
    )

    def clean_password2(self):
        """Validate password confirmation match and strength."""
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')

        if password1 and password2:
            if password1 != password2:
                raise ValidationError('Passwords do not match.')

            # Validate password strength
            validate_password(password1)

        return password2
