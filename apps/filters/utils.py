import calendar
import json
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from urllib.parse import urlencode
from django import forms
from django.db import models
from django.http import QueryDict
from django.utils import timezone

IGNORED_QUERY_KEYS = {
    "page",
    "per_page",
    "_",
    "hx-request",
    "hx-target",
    "hx-trigger",
    "hx-current-path",
    "hx-current-url",
}

RANGE_START_HINTS = ("_after", "_gte", "_start", "_from", "_min", "_lower")
RANGE_END_HINTS = ("_before", "_lte", "_end", "_to", "_max", "_upper")


def build_filter_badges(filterset, *, exclude=None):
    """Return badge metadata for the active fields in a FilterSet."""
    form = getattr(filterset, "form", None)
    if form is None or not form.is_bound:
        return []

    # Ensure validation so cleaned_data is available
    form.is_valid()
    excluded = set(exclude or [])
    badges = []
    for name, field in form.fields.items():
        if name in excluded:
            continue
        value = form.cleaned_data.get(name)
        if value in (None, "", [], (), {}):
            continue
        display_value = _format_field_value(field, value)
        if not display_value:
            continue
        badges.append({
            "label": field.label or name,
            "value": display_value,
            "key": name,
        })
    return badges


def determine_active_filter_name(request, saved_filters, query_params=None):
    """Return the saved-filter name that matches the current query (if any)."""
    params_source = query_params if query_params is not None else request.GET
    if isinstance(params_source, QueryDict):
        current_signature = _normalize_querydict(params_source)
    else:
        current_signature = _normalize_mapping(_ensure_mapping(params_source))
    if not current_signature:
        return None

    for saved in saved_filters or []:
        params = resolve_dynamic_params(saved.query_params)
        if not isinstance(params, dict):
            continue
        saved_signature = _normalize_mapping(params)
        if saved_signature == current_signature:
            return saved.name
    return None


def serialize_query_params(params):
    """Convert a mapping (or JSON string) of query params into a query string."""
    if not params:
        return ""
    if isinstance(params, str):
        params = params.strip()
        if not params:
            return ""
        if params.lstrip().startswith("{"):
            try:
                params = json.loads(params)
            except json.JSONDecodeError:
                return resolve_query_string(params)
        else:
            return resolve_query_string(params)

    normalized = {}
    resolved = resolve_dynamic_params(params)
    for key, value in resolved.items():
        if value is None or value == "":
            continue
        if isinstance(value, (list, tuple)):
            cleaned = [item for item in value if item not in (None, "")]
            if cleaned:
                normalized[key] = cleaned
        else:
            normalized[key] = value
    return urlencode(normalized, doseq=True)


def resolve_query_string(query_string):
    """Resolve a raw query string (possibly containing macros) into concrete params."""
    if not query_string:
        return ""
    query_string = query_string.lstrip("?")
    if not query_string:
        return ""
    qd = QueryDict(query_string, mutable=False)
    mapping = {key: (value if len(value) > 1 else value[0]) for key, value in qd.lists()}
    resolved = resolve_dynamic_params(mapping)
    return urlencode(resolved, doseq=True)


def resolve_dynamic_params(params, today=None):
    """Replace special placeholders (today/this week/etc.) inside query params."""
    mapping = _ensure_mapping(params)
    today = today or timezone.localdate()
    resolved = {}
    for key, value in mapping.items():
        resolved[key] = _resolve_dynamic_value(key, value, today)
    return resolved


def _format_field_value(field, value):
    """Convert a filter value into a short human-readable string."""
    if isinstance(value, slice):
        return _format_range_value(value.start, value.stop)

    if _looks_like_range_tuple(value):
        start, end = value
        return _format_range_value(start, end)

    if isinstance(value, (list, tuple)):
        if isinstance(field, forms.MultipleChoiceField):
            choices = dict(field.choices)
            labels = [choices.get(val, str(val)) for val in value if str(val)]
        else:
            labels = [_format_single_value(field, val) for val in value if str(val)]
        labels = [label for label in labels if label]
        return ", ".join(labels)

    return _format_single_value(field, value)


def _format_single_value(field, value):
    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")

    if isinstance(value, models.Model):
        return str(value)

    if isinstance(field, forms.ChoiceField):
        # MultipleChoiceField inherits ChoiceField, so keep order: only run when not list/tuple
        return dict(field.choices).get(value, value)

    if isinstance(value, bool):
        return "Có" if value else "Không"

    if value in (None, ""):
        return ""

    return str(value)


def _format_range_value(start, end):
    start_label = _format_single_value(None, start)
    end_label = _format_single_value(None, end)
    if start_label and end_label:
        return f"Từ {start_label} đến {end_label}"
    if start_label:
        return f"Từ {start_label}"
    if end_label:
        return f"Đến {end_label}"
    return ""


def _looks_like_range_tuple(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return False
    start, end = value
    return any(item not in (None, "") for item in (start, end))


def _ensure_mapping(params):
    if isinstance(params, QueryDict):
        return {
            key: (values if len(values) > 1 else values[0])
            for key, values in params.lists()
        }
    if isinstance(params, Mapping):
        return dict(params)
    if isinstance(params, str):
        try:
            parsed = json.loads(params)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _resolve_dynamic_value(key, value, today):
    if isinstance(value, (list, tuple)):
        return [_resolve_dynamic_value(key, item, today) for item in value]
    if not isinstance(value, str):
        return value

    token = _extract_token(value)
    if not token:
        return value

    token = token.lower()
    if token in {"today", "now"}:
        return _format_date(today)
    if token == "yesterday":
        return _format_date(today - timedelta(days=1))
    if token == "tomorrow":
        return _format_date(today + timedelta(days=1))

    if token.startswith("this_week") or token == "this_week":
        start, end = _week_bounds(today)
        return _pick_range_value(key, token, start, end)
    if token.startswith("last_week") or token == "last_week":
        start, end = _week_bounds(today - timedelta(days=7))
        return _pick_range_value(key, token, start, end)

    if token.startswith("this_month") or token == "this_month":
        start, end = _month_bounds(today.year, today.month)
        return _pick_range_value(key, token, start, end)
    if token.startswith("last_month") or token == "last_month":
        prev_month_date = (today.replace(day=1) - timedelta(days=1))
        start, end = _month_bounds(prev_month_date.year, prev_month_date.month)
        return _pick_range_value(key, token, start, end)

    return value


def _extract_token(value):
    candidate = value.strip()
    if not candidate:
        return None
    if candidate.startswith("{{") and candidate.endswith("}}"): 
        candidate = candidate[2:-2].strip()
    candidate = candidate.lstrip(":")
    return candidate.replace("-", "_") if candidate else None


def _pick_range_value(key, token, start, end):
    formatted_start = _format_date(start)
    formatted_end = _format_date(end)
    if token.endswith("_start"):
        return formatted_start
    if token.endswith("_end"):
        return formatted_end
    if key.endswith(RANGE_START_HINTS):
        return formatted_start
    if key.endswith(RANGE_END_HINTS):
        return formatted_end
    return formatted_start


def _week_bounds(anchor):
    start = anchor - timedelta(days=anchor.weekday())
    end = start + timedelta(days=6)
    return start, end


def _month_bounds(year, month):
    first = date(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    last = date(year, month, last_day)
    return first, last


def _format_date(value):
    return value.strftime("%Y-%m-%d") if isinstance(value, (date, datetime)) else value


def _normalize_querydict(querydict):
    return _normalize_pairs(list(querydict.lists()))


def _normalize_mapping(mapping):
    pairs = []
    for key, value in mapping.items():
        if isinstance(value, (list, tuple)):
            values = value
        else:
            values = [value]
        pairs.append((key, values))
    return _normalize_pairs(pairs)


def _normalize_pairs(pairs):
    normalized = []
    for key, values in pairs:
        if key in IGNORED_QUERY_KEYS:
            continue
        cleaned_values = [str(val) for val in values if str(val)]
        if cleaned_values:
            normalized.append((key, tuple(cleaned_values)))
    normalized.sort(key=lambda item: item[0])
    return tuple(normalized)
