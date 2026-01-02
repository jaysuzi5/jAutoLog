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
        user_context = self._get_user_context(request)

        # Log request
        logger.info(json.dumps({
            "level": "INFO",
            "event": "Request",
            "method": method,
            "service": "django-app",
            "path": path,
            "user": user_context,
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
                "user": user_context,
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
            "user": user_context,
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

    def _get_user_context(self, request):
        user = getattr(request, "user", None)

        if user and user.is_authenticated:
            return {
                "user_id": user.id,
                "username": user.get_username(),
                "is_authenticated": True,
            }

        return {
            "user_id": None,
            "username": None,
            "is_authenticated": False,
        }
