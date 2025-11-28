from __future__ import annotations

from typing import Any
from django.http import HttpRequest


def is_htmx_request(request: HttpRequest) -> bool:
    """Detect HTMX (or django-htmx) requests in a resilient way."""
    header_value: Any = None
    if hasattr(request, "headers"):
        header_value = request.headers.get("HX-Request")
    if isinstance(header_value, str) and header_value.lower() == "true":
        return True

    meta_value = request.META.get("HTTP_HX_REQUEST")
    if isinstance(meta_value, str) and meta_value.lower() == "true":
        return True

    htmx_attr = getattr(request, "htmx", None)
    if isinstance(htmx_attr, bool):
        return htmx_attr
    return bool(htmx_attr)
