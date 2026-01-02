from django import forms
from .models import Vehicle


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = [
            'year', 'make', 'model', 'color', 'fuel_type',
            'vin_number', 'license_plate_number', 'registration_number', 'state',
            'purchased_date', 'purchased_price', 'purchased_odometer', 'dealer_name',
            'sold_date', 'sold_price', 'sold_odometer',
        ]
        widgets = {
            'year': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Year'}),
            'make': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Make'}),
            'model': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Model'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Color'}),
            'fuel_type': forms.Select(attrs={'class': 'form-select'}),
            'vin_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'VIN Number'}),
            'license_plate_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'License Plate'}),
            'registration_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Registration Number'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'State', 'maxlength': '2'}),
            'purchased_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'purchased_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Purchase Price', 'step': '0.01'}),
            'purchased_odometer': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Odometer at Purchase'}),
            'dealer_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dealer/Seller Name'}),
            'sold_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'sold_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Sale Price', 'step': '0.01'}),
            'sold_odometer': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Odometer at Sale'}),
        }
