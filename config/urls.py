from django.contrib import admin
from django.urls import path
from autolog.views import home
from conversion.views import conversion

urlpatterns = [
    path("", home, name="home"),
    path("conversion/", conversion, name="conversion"),
    path("admin/", admin.site.urls),
]