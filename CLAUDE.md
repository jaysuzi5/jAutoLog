# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

jAutoLog is an automobile expense tracking application built with Django 6.0. It tracks expenses including gas, maintenance, car payments, insurance, and registration across multiple vehicles.

## Development Commands

```bash
# Run development server
python manage.py runserver

# Database migrations
python manage.py makemigrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Collect static files (for production)
python manage.py collectstatic

# Add Python dependencies (uses uv package manager)
uv add <package>

# Production server with OpenTelemetry instrumentation
opentelemetry-instrument gunicorn config.wsgi:application --bind 0.0.0.0:8080 --workers 4 --timeout 120
```

## Architecture

**Django Apps:**
- `autolog/` - Main application with home dashboard (login required)
- `conversion/` - Data conversion utilities
- `config/` - Project configuration, middleware, and logging

**Authentication:**
- Uses django-allauth with email-based authentication and Google OAuth
- All views require login (redirects to `/accounts/login/`)
- Google OAuth configured with PKCE

**Database:**
- PostgreSQL with credentials from environment variables (.env file)
- Required env vars: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`

**Observability:**
- OpenTelemetry instrumentation for Django, SQLAlchemy, requests, and logging
- Custom `RequestLoggingMiddleware` adds transaction ID tracking and structured JSON logging

## Structured Logging

Use the `log_event` helper for consistent JSON-formatted logs:

```python
from config.logging_utils import log_event

log_event(
    request=request,
    event="Description of event",
    level="INFO",  # DEBUG, INFO, WARNING, ERROR
    custom_field="value"
)
```

## Deployment

- Docker image: `jaysuzi5/jautolog:latest` (Python 3.12-slim)
- Kubernetes deployment in `jautolog` namespace
- Static files served via WhiteNoise
- Production domain: `jautolog.jaycurtis.org`

Build: `docker build -t jaysuzi5/jautolog:latest .`
