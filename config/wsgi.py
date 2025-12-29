"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()

try:
    from config.otel_config import setup_opentelemetry
    print('before initialize_otel')
    setup_opentelemetry()
    print('after initialize_otel')
except Exception as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Failed to setup OpenTelemetry: {e}", exc_info=True)