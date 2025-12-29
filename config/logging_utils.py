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
