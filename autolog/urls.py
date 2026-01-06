from django.urls import path
from .views import (
    home, vehicle_list, vehicle_comparison, vehicle_create, vehicle_detail, vehicle_edit,
    fuel_entry_list, fuel_entry_create, fuel_entry_detail, fuel_entry_edit, fuel_entry_delete,
    maintenance_entry_list, maintenance_entry_create, maintenance_entry_edit, maintenance_entry_delete,
    other_expense_list, other_expense_create, other_expense_edit, other_expense_delete,
    vehicle_images, vehicle_image_delete, vehicle_image_set_primary, vehicle_image_update_caption
)

urlpatterns = [
    path("", home, name="home"),
    path("vehicles/", vehicle_list, name="vehicle_list"),
    path("vehicles/compare/", vehicle_comparison, name="vehicle_comparison"),
    path("vehicles/new/", vehicle_create, name="vehicle_create"),
    path("vehicles/<int:pk>/", vehicle_detail, name="vehicle_detail"),
    path("vehicles/<int:pk>/edit/", vehicle_edit, name="vehicle_edit"),

    # Fuel entry URLs
    path("vehicles/<int:vehicle_pk>/fuel/", fuel_entry_list, name="fuel_entry_list"),
    path("vehicles/<int:vehicle_pk>/fuel/add/", fuel_entry_create, name="fuel_entry_create"),
    path("fuel/<int:pk>/", fuel_entry_detail, name="fuel_entry_detail"),
    path("fuel/<int:pk>/edit/", fuel_entry_edit, name="fuel_entry_edit"),
    path("fuel/<int:pk>/delete/", fuel_entry_delete, name="fuel_entry_delete"),

    # Maintenance entry URLs
    path("vehicles/<int:vehicle_pk>/maintenance/", maintenance_entry_list, name="maintenance_entry_list"),
    path("vehicles/<int:vehicle_pk>/maintenance/add/", maintenance_entry_create, name="maintenance_entry_create"),
    path("maintenance/<int:pk>/edit/", maintenance_entry_edit, name="maintenance_entry_edit"),
    path("maintenance/<int:pk>/delete/", maintenance_entry_delete, name="maintenance_entry_delete"),

    # Other expense URLs (insurance, registration)
    path("vehicles/<int:vehicle_pk>/expenses/", other_expense_list, name="other_expense_list"),
    path("vehicles/<int:vehicle_pk>/expenses/add/", other_expense_create, name="other_expense_create"),
    path("expenses/<int:pk>/edit/", other_expense_edit, name="other_expense_edit"),
    path("expenses/<int:pk>/delete/", other_expense_delete, name="other_expense_delete"),

    # Vehicle image URLs
    path("vehicles/<int:vehicle_pk>/images/", vehicle_images, name="vehicle_images"),
    path("images/<int:pk>/delete/", vehicle_image_delete, name="vehicle_image_delete"),
    path("images/<int:pk>/set-primary/", vehicle_image_set_primary, name="vehicle_image_set_primary"),
    path("images/<int:pk>/update-caption/", vehicle_image_update_caption, name="vehicle_image_update_caption"),
]