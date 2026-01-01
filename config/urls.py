from django.contrib import admin
from django.urls import path, include
from autolog.views import home
from conversion.views import conversion

urlpatterns = [
    path("admin/", admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path("", home, name="home"),
    path("conversion/", conversion, name="conversion"),
]