from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
import os

urlpatterns = [
    path("admin/", admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path("", include('autolog.urls')),
    path("conversion/", include('conversion.urls')),
]

# Serve media files in development (including when DEBUG=False for local testing)
if settings.DEBUG or os.getenv("DJANGO_ENV") != "production":
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)