from django.urls import path
from .views import conversion, vehicle_import

urlpatterns = [
    path("", conversion, name="conversion"),
    path("vehicles/", vehicle_import, name="vehicle_import"),
]