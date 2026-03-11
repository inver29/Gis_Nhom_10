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

    def clean_full_name(self):
        full_name = self.cleaned_data['full_name'].strip()
        if len(full_name) < 2:
            raise forms.ValidationError('Họ tên quá ngắn.')
        return full_name

    def clean_phone(self):
        phone = self.cleaned_data['phone'].strip()
        digits_only = ''.join(ch for ch in phone if ch.isdigit())
        if len(digits_only) < 9 or len(digits_only) > 11:
            raise forms.ValidationError('Số điện thoại không hợp lệ.')
        return digits_only

    def clean_address_text(self):
        address_text = self.cleaned_data['address_text'].strip()
        if len(address_text) < 5:
            raise forms.ValidationError('Địa chỉ giao hàng quá ngắn.')
        return address_text


class RegisterForm(forms.ModelForm):
    password = forms.CharField(
        label="Mật khẩu",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )
    confirm_password = forms.CharField(
        label="Nhập lại mật khẩu",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password']
        labels = {'username': 'Tên đăng nhập', 'email': 'Email'}
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Tên đăng nhập đã tồn tại.')
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError('Mật khẩu không khớp.')
        return cleaned_data


class LoginForm(forms.Form):
    username = forms.CharField(
        label="Tên đăng nhập",
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
    )
    password = forms.CharField(
        label="Mật khẩu",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'current-password'}),
    )