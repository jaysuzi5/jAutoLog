from django.urls import path
from .views import conversion

urlpatterns = [
    path("", conversion, name="conversion"),
]