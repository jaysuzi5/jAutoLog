from django.urls import path
from .views import conversion, vehicle_import, fuel_entry_import, maintenance_entry_import

urlpatterns = [
    path("", conversion, name="conversion"),
    path("vehicles/", vehicle_import, name="vehicle_import"),
    path("fuel/<int:vehicle_pk>/", fuel_entry_import, name="fuel_entry_import"),
    path("maintenance/<int:vehicle_pk>/", maintenance_entry_import, name="maintenance_entry_import"),
]