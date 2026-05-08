import time
import uuid
import logging

_mw_logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    def __init__(self, get_response):
        from config.otel_config import setup_otel
        setup_otel()
        self.get_response = get_response

    def __call__(self, request):
        from config.otel_config import (
            _SKIP_PREFIXES, _endpoint_from_path,
            log_request, log_response, _tracer, _page_visits,
        )

        transaction_id = str(uuid.uuid4())
        request.transaction_id = transaction_id

        if any(request.path.startswith(p) for p in _SKIP_PREFIXES):
            return self.get_response(request)

        endpoint = _endpoint_from_path(request.path)
        log_request(request, transaction_id, endpoint)

        span = None
        if _tracer is not None:
            from opentelemetry import trace as otel_trace
            span = _tracer.start_span(
                endpoint,
                kind=otel_trace.SpanKind.SERVER,
                attributes={
                    "http.method": request.method,
                    "http.path": request.path,
                    "transaction_id": transaction_id,
                },
            )

        start = time.monotonic()
        try:
            response = self.get_response(request)
        except Exception:
            if span is not None:
                try:
                    span.end()
                except Exception:
                    pass
            raise

        duration = time.monotonic() - start
        trace_id = span_id = None
        if span is not None:
            try:
                span.set_attribute("http.status_code", response.status_code)
                ctx = span.get_span_context()
                if ctx and ctx.is_valid:
                    trace_id = format(ctx.trace_id, "032x")
                    span_id = format(ctx.span_id, "016x")
                span.end()
            except Exception:
                pass

        summary = getattr(request, "otel_page_summary", None)
        log_response(request, transaction_id, endpoint, response.status_code, duration, summary, trace_id, span_id)

        if _page_visits is not None:
            _page_visits.add(1, {
                "endpoint": endpoint,
                "method": request.method,
                "status": str(response.status_code),
            })

        return response
