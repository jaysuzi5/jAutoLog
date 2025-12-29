## Open Telemetry Setup
The following setup assumes that a collector is already in place.

1. Add the OTEL Libraries:
```bash
uv add "opentelemetry-distro>=0.60b1"
uv add "opentelemetry-exporter-otlp>=1.39b1"
uv add "opentelemetry-instrumentation-django>=0.60b1"
uv add "opentelemetry-instrumentation-logging>=0.60b1"
uv add "opentelemetry-instrumentation-requests>=0.60b1"
uv add "opentelemetry-instrumentation-sqlalchemy>=0.60b1"
```

2. Define basic setup at the project level: otel_config.py  Steps 2-3 are required for Django as it will not fully auto-instrument
```bash
import os
import logging
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggingHandler

def setup_opentelemetry():
    logger = logging.getLogger()

    log_level_str = os.environ.get("OTEL_LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    logger_provider = get_logger_provider()
    handler = LoggingHandler(level=log_level, logger_provider=logger_provider)
    logger.addHandler(handler)
    logger.setLevel(log_level)

    logger.info("jautolog: OpenTelemetry logging is configured.")
```


3. Add reference to this in wsgi.py
```bash
try:
    from config.otel_config import initialize_otel
    initialize_otel()
except Exception as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Failed to setup OpenTelemetry: {e}", exc_info=True)
```


4.  Ensure that the K8s deployment has defined the following environment variables:
```bash
          env:
            - name: LOG_LEVEL
              value: DEBUG
            - name: OTEL_EXPORTER_OTLP_ENDPOINT
              value: "http://otel-collector-collector.monitoring.svc.cluster.local:4317"
            - name: OTEL_SERVICE_NAME
              value: "jautolog"
            - name: OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED
              value: "true"   
```

5.  Adjust the Dockerfile.  Setup can be a bit more challenging under UV, but the following should work

```bash
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN pip install --upgrade pip && pip install "poetry-core>=1.8" && \
    pip install --no-cache-dir .

COPY . .

EXPOSE 8000

CMD [\
  "opentelemetry-instrument",\
  "--traces_exporter", "otlp",\
  "--metrics_exporter", "otlp",\
  "--logs_exporter", "otlp",\
  "--",\
  "gunicorn",\
  "config.wsgi:application",\
  "--bind", "0.0.0.0:8000",\
  "--workers", "4",\
  "--timeout", "120"\
]
```



6. Build & Push Multi-Architecture Docker Image

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t jaysuzi5/jautolog:latest --push .
```

7. Apply the updated deployment

```bash
k apply -f deployment.yaml
```


## Optional Additional Improvements:
### Middleware to capture Request and Response
The following also will also format the data in JSON

1. Create middelware.py
```bash
import logging
import time
import datetime
import socket
import json
import traceback
from uuid import uuid4

logger = logging.getLogger('jautolog')

class RequestLoggingMiddleware:
    """
    Django middleware to log HTTP requests and responses in JSON format.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()

        # Skip logging for static files and health checks
        if request.path.startswith('/static/') or request.path.startswith('/health/'):
            return self.get_response(request)

        transaction_id = request.headers.get("X-Transaction-ID") or str(uuid4())
        request.transaction_id = transaction_id

        request_body = self._get_request_body(request)
        method = request.method
        path = request.path
        query_params = dict(request.GET)

        # Log request
        logger.info(json.dumps({
            "level": "INFO",
            "event": "Request",
            "method": method,
            "service": "django-app",
            "path": path,
            "remote_addr": self._get_client_ip(request),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "hostname": socket.gethostname(),
            "transaction_id": transaction_id,
            "request_body": request_body,
            "query_params": query_params
        }))

        try:
            response = self.get_response(request)
            status_code = response.status_code
            response_body = self._get_response_body(response)
        except Exception as e:
            # Log exception
            stack_trace = traceback.format_exc()
            logger.error(json.dumps({
                "level": "ERROR",
                "event": "Unhandled Exception",
                "method": method,
                "service": "django-app",
                "path": path,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "exception": str(e),
                "stack_trace": stack_trace,
                "transaction_id": transaction_id,
                "request_body": request_body
            }))
            raise

        # Log response
        elapsed_time = time.time() - start_time
        logger.info(json.dumps({
            "level": "INFO",
            "event": "Response",
            "method": method,
            "service": "django-app",
            "path": path,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "duration_seconds": round(elapsed_time, 4),
            "status": status_code,
            "transaction_id": transaction_id,
            "response_body": response_body
        }))

        return response

    def _get_request_body(self, request):
        try:
            if request.body:
                return json.loads(request.body.decode('utf-8'))
        except Exception:
            return str(request.body)
        return None

    def _get_response_body(self, response):
        try:
            if hasattr(response, 'content') and response.content:
                return json.loads(response.content.decode('utf-8'))
        except Exception:
            return str(getattr(response, 'content', None))
        return None

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

```

2. Add to settings:
```bash
MIDDLEWARE = [
    ...
    'config.middleware.RequestLoggingMiddleware',
]
```

### Handler for other logging to log in JSON format
1. Define logging_utils.py
```bash
# config/logging_utils.py

import logging
import json
import datetime
import socket

logger = logging.getLogger("jautolog")

def _get_view_name(request):
    """
    Returns fully-qualified view name: module.function
    """
    if hasattr(request, "resolver_match") and request.resolver_match:
        func = request.resolver_match.func
        return f"{func.__module__}.{func.__name__}"
    return None


def log_event(
    *,
    request,
    event,
    level="INFO",
    service="django-app",
    **fields,
):
    log_record = {
        "level": level,
        "event": event,
        "service": service,
        "method": request.method,
        "path": request.path,
        "view": _get_view_name(request),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "transaction_id": getattr(request, "transaction_id", None),
    }

    log_record.update(fields)

    message = json.dumps(log_record)

    if level == "ERROR":
        logger.error(message)
    elif level == "WARNING":
        logger.warning(message)
    elif level == "DEBUG":
        logger.debug(message)        
    else:
        logger.info(message)
```

2. Example Usage:
```bash
from django.shortcuts import render
from config.logging_utils import log_event


def home(request):
    log_event(
        request=request,
        event="Home view was accessed in jautolog",
        level="DEBUG"
    )
    return render(request, "autolog/home.html")
```