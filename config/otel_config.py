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
