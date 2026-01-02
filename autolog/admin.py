from django.contrib import admin
from .models import Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('year', 'make', 'model', 'user', 'fuel_type', 'is_sold')
    list_filter = ('fuel_type', 'make', 'year')
    search_fields = ('make', 'model', 'vin_number', 'license_plate_number')
    ordering = ('-year', 'make', 'model')
