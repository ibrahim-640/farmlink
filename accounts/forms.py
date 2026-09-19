from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import TransporterRating, Profile
from django.contrib.auth.models import User
from .models import Product

class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)

class FarmerRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

class BuyerRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

class TransporterRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        exclude = ("farmer",)  # set by the view
        widgets = {
            "category": forms.Select(),}


class TransporterRatingForm(forms.ModelForm):
    class Meta:
        model = TransporterRating
        fields = ['rating', 'comment']
        widgets = {
            'rating': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'comment': forms.Textarea(attrs={'rows': 3}),
           }

class TransporterProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['phone', 'id_number', 'location', 'profile_picture']
        widgets = {
            'phone': forms.TextInput(attrs={
                'placeholder': 'e.g. 0712345678',
                'class': 'form-control'
            }),
            'id_number': forms.TextInput(attrs={
                'placeholder': 'Enter your National ID number',
                'class': 'form-control'
            }),
            'location': forms.TextInput(attrs={
                'placeholder': 'e.g. Nairobi, Kenya',
                'class': 'form-control'
            }),
            'profile_picture': forms.FileInput(attrs={
                'class': 'form-control'
            }),
        }






