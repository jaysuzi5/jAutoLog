from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from PIL import Image
from io import BytesIO


class Vehicle(models.Model):
    FUEL_CHOICES = [
        ('gasoline', 'Gasoline'),
        ('diesel', 'Diesel'),
        ('electric', 'Electric'),
        ('hybrid', 'Hybrid'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='vehicles')
    year = models.PositiveIntegerField()
    make = models.CharField(max_length=50)
    model = models.CharField(max_length=50)
    color = models.CharField(max_length=30, blank=True)
    vin_number = models.CharField(max_length=17, blank=True)
    license_plate_number = models.CharField(max_length=15, blank=True)
    registration_number = models.CharField(max_length=50, blank=True)
    state = models.CharField(max_length=2, blank=True)
    purchased_date = models.DateField(null=True, blank=True)
    purchased_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    purchased_odometer = models.PositiveIntegerField(null=True, blank=True)
    dealer_name = models.CharField(max_length=100, blank=True)
    sold_date = models.DateField(null=True, blank=True)
    sold_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sold_odometer = models.PositiveIntegerField(null=True, blank=True)
    current_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Current estimated value (for unsold vehicles)")
    current_value_date = models.DateField(null=True, blank=True, help_text="Date of current value estimate")
    fuel_type = models.CharField(max_length=10, choices=FUEL_CHOICES, default='gasoline')

    # Financing information
    FINANCING_CHOICES = [
        ('none', 'None'),
        ('loan', 'Loan'),
        ('lease', 'Lease'),
    ]
    financing_type = models.CharField(max_length=10, choices=FINANCING_CHOICES, default='none')
    down_payment = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Down payment amount")

    # Loan-specific fields
    loan_start_date = models.DateField(null=True, blank=True)
    loan_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Amount financed (after down payment)")
    loan_interest_rate = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True, help_text="Annual interest rate as percentage (e.g., 5.75 for 5.75%)")
    loan_term_months = models.PositiveIntegerField(null=True, blank=True, help_text="Total number of months for the loan")
    loan_payment_day = models.PositiveIntegerField(null=True, blank=True, help_text="Day of month payment is due (1-31)")
    loan_auto_payment = models.BooleanField(default=False, help_text="Automatically generate monthly payment entries")

    # Lease-specific fields
    lease_start_date = models.DateField(null=True, blank=True)
    lease_payment_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Monthly lease payment amount")
    lease_term_months = models.PositiveIntegerField(null=True, blank=True, help_text="Total number of months for the lease")
    lease_payment_day = models.PositiveIntegerField(null=True, blank=True, help_text="Day of month payment is due (1-31)")
    lease_auto_payment = models.BooleanField(default=False, help_text="Automatically generate monthly payment entries")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year', 'make', 'model']

    def __str__(self):
        return f"{self.year} {self.make} {self.model}"

    @property
    def is_sold(self):
        return self.sold_date is not None

    def calculate_monthly_payment(self):
        """Calculate the monthly loan payment using amortization formula"""
        if not all([self.loan_amount, self.loan_interest_rate, self.loan_term_months]):
            return None

        principal = float(self.loan_amount)
        annual_rate = float(self.loan_interest_rate) / 100  # Convert percentage to decimal
        monthly_rate = annual_rate / 12
        num_payments = self.loan_term_months

        if monthly_rate == 0:
            # No interest loan
            return principal / num_payments

        # Amortization formula: M = P * [r(1+r)^n] / [(1+r)^n - 1]
        monthly_payment = principal * (monthly_rate * (1 + monthly_rate)**num_payments) / ((1 + monthly_rate)**num_payments - 1)
        return round(monthly_payment, 2)

    def get_loan_payments_made(self):
        """Get count of loan payments made (vehicle payments with loan notes)"""
        return self.other_expenses.filter(
            expense_type='vehicle_payment',
            notes__icontains='loan payment'
        ).count()

    def get_loan_payments_remaining(self):
        """Calculate remaining loan payments"""
        if not self.loan_term_months:
            return None
        payments_made = self.get_loan_payments_made()
        return max(0, self.loan_term_months - payments_made)

    def get_lease_payments_made(self):
        """Get count of lease payments made (vehicle payments with lease notes)"""
        return self.other_expenses.filter(
            expense_type='vehicle_payment',
            notes__icontains='lease payment'
        ).count()

    def get_lease_payments_remaining(self):
        """Calculate remaining lease payments"""
        if not self.lease_term_months:
            return None
        payments_made = self.get_lease_payments_made()
        return max(0, self.lease_term_months - payments_made)

    def get_total_loan_interest(self):
        """Calculate expected total interest over life of loan"""
        monthly_payment = self.calculate_monthly_payment()
        if not monthly_payment or not self.loan_term_months or not self.loan_amount:
            return None

        total_paid = monthly_payment * self.loan_term_months
        total_interest = total_paid - float(self.loan_amount)
        return round(total_interest, 2)

    def get_interest_paid_to_date(self):
        """Calculate actual interest paid on loan payments made so far using amortization schedule"""
        if not all([self.loan_amount, self.loan_interest_rate, self.loan_term_months]):
            return None

        payments_made = self.get_loan_payments_made()
        if payments_made == 0:
            return 0

        monthly_payment = self.calculate_monthly_payment()
        if not monthly_payment:
            return None

        principal = float(self.loan_amount)
        annual_rate = float(self.loan_interest_rate) / 100
        monthly_rate = annual_rate / 12

        if monthly_rate == 0:
            # No interest loan
            return 0

        # Calculate interest paid using amortization schedule
        remaining_principal = principal
        total_interest_paid = 0

        for payment_num in range(1, payments_made + 1):
            # Interest portion of this payment
            interest_payment = remaining_principal * monthly_rate
            # Principal portion of this payment
            principal_payment = monthly_payment - interest_payment
            # Update remaining principal
            remaining_principal -= principal_payment
            # Accumulate interest paid
            total_interest_paid += interest_payment

        return round(total_interest_paid, 2)


class FuelEntry(models.Model):
    # Relationships
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='fuel_entries'
    )

    # Common fields for all fuel types
    date = models.DateField()
    odometer = models.PositiveIntegerField()
    cost = models.DecimalField(max_digits=6, decimal_places=2)  # Max $9999.99

    # Gasoline/Diesel/Hybrid specific fields
    gallons = models.DecimalField(
        max_digits=5,
        decimal_places=3,  # Support precision like 10.255 gallons
        null=True,
        blank=True
    )
    mpg = models.DecimalField(
        max_digits=5,
        decimal_places=2,  # e.g., 45.67 MPG
        null=True,
        blank=True
    )

    # Electric vehicle specific fields
    kwh_per_mile = models.DecimalField(
        max_digits=4,
        decimal_places=3,  # e.g., 0.300
        null=True,
        blank=True
    )
    cost_per_kwh = models.DecimalField(
        max_digits=5,
        decimal_places=3,  # e.g., 0.125
        null=True,
        blank=True
    )
    cost_per_gallon_reference = models.DecimalField(
        max_digits=5,
        decimal_places=2,  # e.g., 4.50
        null=True,
        blank=True,
        help_text="Reference gas price for MPGe calculation"
    )
    mpge = models.DecimalField(
        max_digits=5,
        decimal_places=1,  # e.g., 110.5 MPGe
        null=True,
        blank=True
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name_plural = "Fuel entries"

    def __str__(self):
        if self.mpg:
            return f"{self.vehicle} - {self.date} ({self.mpg} MPG)"
        else:
            return f"{self.vehicle} - {self.date} ({self.mpge} MPGe)"

    @property
    def is_electric(self):
        return self.vehicle.fuel_type == 'electric'


class MaintenanceEntry(models.Model):
    CATEGORY_CHOICES = [
        ('oil', 'Oil Change'),
        ('repairs', 'Repairs'),
        ('tires', 'Tires'),
        ('wash', 'Wash'),
        ('accessories', 'Accessories'),
    ]

    # Relationships
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='maintenance_entries'
    )

    # Core fields
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    date = models.DateField()
    odometer = models.PositiveIntegerField()
    cost = models.DecimalField(max_digits=8, decimal_places=2)  # Max $999,999.99
    notes = models.TextField(blank=True, default='')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name_plural = "Maintenance entries"

    def __str__(self):
        return f"{self.vehicle} - {self.get_category_display()} - {self.date}"


class OtherExpense(models.Model):
    EXPENSE_TYPE_CHOICES = [
        ('insurance', 'Insurance'),
        ('registration', 'Registration'),
        ('vehicle_payment', 'Vehicle Payment'),
    ]

    # Relationships
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='other_expenses'
    )

    # Core fields
    expense_type = models.CharField(max_length=20, choices=EXPENSE_TYPE_CHOICES)
    date = models.DateField()
    cost = models.DecimalField(max_digits=8, decimal_places=2)  # Max $999,999.99
    notes = models.TextField(blank=True, default='')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name_plural = "Other expenses"

    def __str__(self):
        return f"{self.vehicle} - {self.get_expense_type_display()} - {self.date}"


def vehicle_image_upload_path(instance, filename):
    """
    Generate hierarchical upload path for vehicle images.
    Returns: vehicles/user_{user_id}/vehicle_{vehicle_id}/{filename}
    """
    return f'vehicles/user_{instance.vehicle.user.id}/vehicle_{instance.vehicle.id}/{filename}'


class VehicleImage(models.Model):
    """Model for storing vehicle images with automatic resizing"""
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to=vehicle_image_upload_path)
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_primary = models.BooleanField(default=False, help_text="Primary image shown first")

    class Meta:
        ordering = ['-is_primary', '-uploaded_at']

    def __str__(self):
        return f"{self.vehicle} - Image {self.id}"

    def save(self, *args, **kwargs):
        """Override save to resize image if needed - works with local and S3 storage"""
        # Process image BEFORE saving to storage
        if self.image:
            # Open the uploaded image file
            img = Image.open(self.image)

            # Get max resolution from settings
            max_size = settings.MAX_IMAGE_RESOLUTION

            # Check if image needs resizing
            if img.width > max_size or img.height > max_size:
                # Calculate new dimensions maintaining aspect ratio
                if img.width > img.height:
                    new_width = max_size
                    new_height = int((max_size / img.width) * img.height)
                else:
                    new_height = max_size
                    new_width = int((max_size / img.height) * img.width)

                # Resize image
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Save resized image to BytesIO
                output = BytesIO()

                # Preserve format (JPEG, PNG, etc.)
                img_format = img.format or 'JPEG'
                img.save(output, format=img_format, optimize=True, quality=85)
                output.seek(0)

                # Replace the image field with resized version
                from django.core.files import File
                self.image.save(
                    self.image.name,
                    File(output),
                    save=False
                )

        # Now save to storage (local or S3)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Override delete to remove image file - works with local and S3 storage"""
        if self.image:
            # Delete file from storage backend (local or S3)
            self.image.delete(save=False)
        super().delete(*args, **kwargs)
