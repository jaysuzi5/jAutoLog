from django.urls import path
from .views import home, vehicle_list, vehicle_create, vehicle_detail, vehicle_edit

urlpatterns = [
    path("", home, name="home"),
    path("vehicles/", vehicle_list, name="vehicle_list"),
    path("vehicles/new/", vehicle_create, name="vehicle_create"),
    path("vehicles/<int:pk>/", vehicle_detail, name="vehicle_detail"),
    path("vehicles/<int:pk>/edit/", vehicle_edit, name="vehicle_edit"),
]