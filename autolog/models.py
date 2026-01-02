from django.db import models
from django.contrib.auth.models import User


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
    fuel_type = models.CharField(max_length=10, choices=FUEL_CHOICES, default='gasoline')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year', 'make', 'model']

    def __str__(self):
        return f"{self.year} {self.make} {self.model}"

    @property
    def is_sold(self):
        return self.sold_date is not None
