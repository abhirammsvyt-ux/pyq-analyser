"""User authentication forms using Bootstrap 5 classes."""
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-dark',
            'placeholder': 'your@email.com',
            'autocomplete': 'email',
        })
    )
    full_name = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-dark',
            'placeholder': 'John Doe',
        })
    )
    institution = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-dark',
            'placeholder': 'University / College name',
        })
    )

    class Meta:
        model = User
        fields = ('email', 'username', 'full_name', 'institution', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control form-control-dark', 'placeholder': 'username123',
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control form-control-dark', 'placeholder': 'Enter password',
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control form-control-dark', 'placeholder': 'Confirm password',
        })
        self.fields['username'].help_text = None
        self.fields['password1'].help_text = None
        self.fields['password2'].help_text = None


class CustomLoginForm(AuthenticationForm):
    username = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-dark',
            'placeholder': 'Enter your email',
            'autocomplete': 'email',
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-dark',
            'placeholder': 'Enter your password',
            'autocomplete': 'current-password',
        })
    )


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('full_name', 'institution', 'avatar')
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control form-control-dark', 'placeholder': 'Your full name',
            }),
            'institution': forms.TextInput(attrs={
                'class': 'form-control form-control-dark', 'placeholder': 'Your institution',
            }),
        }
