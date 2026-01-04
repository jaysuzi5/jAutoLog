from django import forms
from .models import Vehicle, FuelEntry


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


def get_previous_odometer(vehicle):
    """Get the previous odometer reading for a vehicle"""
    latest_entry = vehicle.fuel_entries.order_by('-date').first()
    if latest_entry:
        return latest_entry.odometer
    elif vehicle.purchased_odometer:
        return vehicle.purchased_odometer
    else:
        return 0


class GasolineFuelForm(forms.ModelForm):
    class Meta:
        model = FuelEntry
        fields = ['date', 'odometer', 'gallons', 'cost']
        widgets = {
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'odometer': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Current odometer reading'
            }),
            'gallons': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Gallons',
                'step': '0.001',
                'min': '0.1',
                'max': '100'
            }),
            'cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Total cost',
                'step': '0.01',
                'min': '0.01',
                'max': '500'
            }),
        }

    def __init__(self, *args, vehicle=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.vehicle = vehicle

        if vehicle:
            prev_odometer = get_previous_odometer(vehicle)
            self.fields['odometer'].widget.attrs['placeholder'] = (
                f"Previous: {prev_odometer:,} miles"
            )
            self.previous_odometer = prev_odometer

    def clean_odometer(self):
        odometer = self.cleaned_data.get('odometer')

        if not hasattr(self, 'previous_odometer'):
            return odometer

        if odometer <= self.previous_odometer:
            raise forms.ValidationError(
                f"Odometer must be greater than {self.previous_odometer:,} miles"
            )

        if odometer > self.previous_odometer + 1000:
            raise forms.ValidationError(
                f"Odometer cannot be more than 1,000 miles greater than "
                f"previous reading ({self.previous_odometer:,} miles)"
            )

        return odometer

    def clean_gallons(self):
        gallons = self.cleaned_data.get('gallons')

        if gallons and gallons > 100:
            raise forms.ValidationError("Gallons cannot exceed 100")

        return gallons

    def clean_cost(self):
        cost = self.cleaned_data.get('cost')

        if cost and cost > 500:
            raise forms.ValidationError("Cost cannot exceed $500")

        return cost

    def clean(self):
        cleaned_data = super().clean()
        odometer = cleaned_data.get('odometer')
        gallons = cleaned_data.get('gallons')

        if odometer and gallons and hasattr(self, 'previous_odometer'):
            miles_driven = odometer - self.previous_odometer
            mpg = miles_driven / float(gallons)

            if mpg < 4.0:
                raise forms.ValidationError(
                    f"Calculated MPG ({mpg:.2f}) is too low. "
                    f"Please verify odometer and gallons."
                )

            if mpg > 100.0:
                raise forms.ValidationError(
                    f"Calculated MPG ({mpg:.2f}) is too high. "
                    f"Please verify odometer and gallons."
                )

            # Store calculated MPG for view to save
            cleaned_data['mpg'] = round(mpg, 2)

        return cleaned_data


class ElectricFuelForm(forms.ModelForm):
    class Meta:
        model = FuelEntry
        fields = ['date', 'odometer', 'kwh_per_mile', 'cost_per_kwh',
                  'cost_per_gallon_reference']
        widgets = {
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'odometer': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Current odometer reading'
            }),
            'kwh_per_mile': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 0.300',
                'step': '0.001',
                'min': '0.100',
                'max': '0.500'
            }),
            'cost_per_kwh': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., 0.125',
                'step': '0.001',
                'min': '0.050',
                'max': '0.500'
            }),
            'cost_per_gallon_reference': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Reference gas price for MPGe',
                'step': '0.01',
                'min': '0.50',
                'max': '20.00'
            }),
        }
        labels = {
            'kwh_per_mile': 'KWH per Mile',
            'cost_per_kwh': 'Cost per KWH',
            'cost_per_gallon_reference': 'Reference Gas Price ($/gal)',
        }

    def __init__(self, *args, vehicle=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.vehicle = vehicle

        if vehicle:
            prev_odometer = get_previous_odometer(vehicle)
            self.fields['odometer'].widget.attrs['placeholder'] = (
                f"Previous: {prev_odometer:,} miles"
            )
            self.previous_odometer = prev_odometer

    def clean_odometer(self):
        odometer = self.cleaned_data.get('odometer')

        if not hasattr(self, 'previous_odometer'):
            return odometer

        if odometer <= self.previous_odometer:
            raise forms.ValidationError(
                f"Odometer must be greater than {self.previous_odometer:,} miles"
            )

        if odometer > self.previous_odometer + 10000:
            raise forms.ValidationError(
                f"Odometer cannot be more than 10,000 miles greater than "
                f"previous reading ({self.previous_odometer:,} miles)"
            )

        return odometer

    def clean_kwh_per_mile(self):
        kwh = self.cleaned_data.get('kwh_per_mile')

        if kwh and (kwh < 0.100 or kwh > 0.500):
            raise forms.ValidationError(
                "KWH per mile must be between 0.100 and 0.500"
            )

        return kwh

    def clean_cost_per_kwh(self):
        cost = self.cleaned_data.get('cost_per_kwh')

        if cost and (cost < 0.050 or cost > 0.500):
            raise forms.ValidationError(
                "Cost per KWH must be between $0.050 and $0.500"
            )

        return cost

    def clean_cost_per_gallon_reference(self):
        cost = self.cleaned_data.get('cost_per_gallon_reference')

        if cost and (cost < 0.50 or cost > 20.00):
            raise forms.ValidationError(
                "Reference gas price must be between $0.50 and $20.00"
            )

        return cost

    def clean(self):
        cleaned_data = super().clean()
        kwh_per_mile = cleaned_data.get('kwh_per_mile')
        cost_per_kwh = cleaned_data.get('cost_per_kwh')
        cost_per_gallon = cleaned_data.get('cost_per_gallon_reference')

        if kwh_per_mile and cost_per_kwh and cost_per_gallon:
            # MPGe = cost_per_gallon / (kwh_per_mile * cost_per_kwh)
            mpge = float(cost_per_gallon) / (
                float(kwh_per_mile) * float(cost_per_kwh)
            )

            # Store calculated MPGe for view to save
            cleaned_data['mpge'] = round(mpge, 1)

            # Calculate total cost
            odometer = cleaned_data.get('odometer')
            if odometer and hasattr(self, 'previous_odometer'):
                miles_driven = odometer - self.previous_odometer
                total_cost = miles_driven * float(kwh_per_mile) * float(cost_per_kwh)
                cleaned_data['cost'] = round(total_cost, 2)

        return cleaned_data
