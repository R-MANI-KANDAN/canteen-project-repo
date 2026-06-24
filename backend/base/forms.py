# Description: User creation and profile update forms for user authentication and management.
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Profile

class CustomUserCreationForm(UserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove default help texts
        self.fields['email'].help_text = None
        self.fields['password1'].help_text = None
        self.fields['password2'].help_text = None

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('email', 'password1', 'password2')


class ProfileUpdateForm(forms.ModelForm):
    # Additional fields from the User model
    first_name = forms.CharField(max_length=30, required=False, label='First Name')
    last_name = forms.CharField(max_length=30, required=False, label='Last Name')
    email = forms.EmailField(label='Email Address')
    remove_picture = forms.BooleanField(
        required=False,
        label='Remove current profile picture'
    )
    class Meta:
        model = Profile
        fields = ['profile_picture', 'phone_number']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Populate User model fields if profile is linked to a user
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user

        # Update user fields
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        
        if self.cleaned_data.get('remove_picture'):
            profile.remove_profile_picture()
        
        
        
        if commit:
            user.save()
            profile.save()
        return profile
