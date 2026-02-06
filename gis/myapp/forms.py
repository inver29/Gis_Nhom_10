from django import forms
from django.contrib.auth.models import User
from .models import Order

class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['full_name', 'phone', 'address_text', 'note']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Họ và tên người nhận'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Số điện thoại liên hệ'}),
            'address_text': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Số nhà, tên đường...'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ghi chú cho shipper (VD: Gọi trước khi đến...)'}),
        }

class RegisterForm(forms.ModelForm):
    password = forms.CharField(label="Mật khẩu", widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}))
    confirm_password = forms.CharField(label="Nhập lại mật khẩu", widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}))

    class Meta:
        model = User
        fields = ['username', 'email', 'password']
        labels = {'username': 'Tên đăng nhập', 'email': 'Email'}
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password") != cleaned_data.get("confirm_password"):
            raise forms.ValidationError("Mật khẩu không khớp")
        return cleaned_data

class LoginForm(forms.Form):
    username = forms.CharField(label="Tên đăng nhập", widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}))
    password = forms.CharField(label="Mật khẩu", widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}))