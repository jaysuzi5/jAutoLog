FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN pip install --upgrade pip && pip install "poetry-core>=1.8" && \
    pip install --no-cache-dir .

COPY . .

RUN python manage.py collectstatic --noinput

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