from __future__ import annotations

from typing import Iterable
from django import forms as dj_forms


def form_errors_as_text(form: dj_forms.Form, fallback: str | None = None) -> str:
    """Return aggregated validation errors for SweetAlert toasts."""
    parts: list[str] = []

    for field_name, error_list in form.errors.items():
        if field_name == dj_forms.forms.NON_FIELD_ERRORS:
            continue
        label = getattr(form.fields.get(field_name), "label", field_name)
        for err in error_list:
            parts.append(f"{label}: {err}")

    for err in form.non_field_errors():
        parts.append(str(err))

    unique_errors = list(dict.fromkeys(parts))
    if unique_errors:
        return "\n".join(unique_errors)
    return fallback or "Dữ liệu không hợp lệ."
