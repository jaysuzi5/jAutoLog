from django.urls import path
from .views import (
    home, vehicle_list, vehicle_create, vehicle_detail, vehicle_edit,
    fuel_entry_create, fuel_entry_detail, fuel_entry_edit, fuel_entry_delete,
    maintenance_entry_list, maintenance_entry_create, maintenance_entry_edit, maintenance_entry_delete
)

urlpatterns = [
    path("", home, name="home"),
    path("vehicles/", vehicle_list, name="vehicle_list"),
    path("vehicles/new/", vehicle_create, name="vehicle_create"),
    path("vehicles/<int:pk>/", vehicle_detail, name="vehicle_detail"),
    path("vehicles/<int:pk>/edit/", vehicle_edit, name="vehicle_edit"),

    # Fuel entry URLs
    path("vehicles/<int:vehicle_pk>/fuel/add/", fuel_entry_create, name="fuel_entry_create"),
    path("fuel/<int:pk>/", fuel_entry_detail, name="fuel_entry_detail"),
    path("fuel/<int:pk>/edit/", fuel_entry_edit, name="fuel_entry_edit"),
    path("fuel/<int:pk>/delete/", fuel_entry_delete, name="fuel_entry_delete"),

    # Maintenance entry URLs
    path("vehicles/<int:vehicle_pk>/maintenance/", maintenance_entry_list, name="maintenance_entry_list"),
    path("vehicles/<int:vehicle_pk>/maintenance/add/", maintenance_entry_create, name="maintenance_entry_create"),
    path("maintenance/<int:pk>/edit/", maintenance_entry_edit, name="maintenance_entry_edit"),
    path("maintenance/<int:pk>/delete/", maintenance_entry_delete, name="maintenance_entry_delete"),
]