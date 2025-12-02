import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.billing.filters import BillingEnrollmentFilter
from apps.billing.forms import BillingPurchaseForm, DiscountForm
from apps.billing.models import BillingEntry, Discount
from apps.centers.models import Center
from apps.enrollments.models import Enrollment
from apps.enrollments.services import sessions_remaining
from apps.filters.models import SavedFilter
from apps.filters.utils import (
    build_filter_badges,
    determine_active_filter_name,
)
from apps.common.utils.forms import form_errors_as_text
from apps.common.utils.http import is_htmx_request


@login_required
def billing_home(request):
    base_qs = Enrollment.objects.select_related(
        "student", "klass", "klass__center"
    ).order_by("-joined_at")
    enrollment_filter = BillingEnrollmentFilter(request.GET, queryset=base_qs)
    qs = enrollment_filter.qs
    total = qs.count()

    active_filter_badges = build_filter_badges(enrollment_filter)

    saved_filters = SavedFilter.objects.filter(model_name="BillingEnrollment").filter(
        Q(user=request.user) | Q(is_public=True)
    )
    active_filter_name = determine_active_filter_name(request, saved_filters)

    try:
        per_page = int(request.GET.get("per_page", 10))
    except (TypeError, ValueError):
        per_page = 10
    if per_page <= 0:
        per_page = 10

    paginator = Paginator(qs, per_page)
    try:
        page = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(1)

    query_params_no_page = request.GET.copy()
    query_params_no_page._mutable = True
    query_params_no_page.pop("page", None)

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "filter": enrollment_filter,
        "total": total,
        "per_page": per_page,
        "current_query_params": query_params_no_page.urlencode(),
        "active_filter_name": active_filter_name,
        "active_filter_badges": active_filter_badges,
        "model_name": "BillingEnrollment",
    }
    if is_htmx_request(request):
        return render(request, "_billing_filterable_content.html", context)
    return render(request, "billing_home.html", context)


@login_required
def billing_entries(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, pk=enrollment_id)
    entries = enrollment.billing_entries.order_by("-created_at")
    remaining = sessions_remaining(enrollment)
    context = {
        "enrollment": enrollment,
        "entries": entries,
        "remaining": remaining,
    }
    return render(request, "billing_entries.html", context)


@login_required
def billing_purchase(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, pk=enrollment_id)
    if not request.user.is_staff:
        messages.error(request, "Ban khong co quyen tao phieu thu.")
        return redirect("billing:entries", enrollment_id=enrollment_id)

    if request.method == "POST":
        form = BillingPurchaseForm(request.POST, enrollment=enrollment)
        if form.is_valid():
            form.save()
            messages.success(request, "Da tao phieu thu/buoi cho ghi danh.")
            return redirect("billing:entries", enrollment_id=enrollment_id)
    else:
        form = BillingPurchaseForm(
            enrollment=enrollment,
            initial={
                "sessions": enrollment.sessions_purchased or 1,
                "unit_price": enrollment.fee_per_session,
            },
        )
    context = {
        "form": form,
        "enrollment": enrollment,
    }
    return render(request, "billing_purchase_form.html", context)


@login_required
def discount_list(request):
    if not request.user.is_staff:
        messages.error(request, "Ban khong co quyen xem giam gia.")
        return redirect("billing:home")
    discounts = Discount.objects.order_by("-active", "code")
    return render(request, "discount_list.html", {"discounts": discounts})


@login_required
def discount_create(request):
    if not request.user.is_staff:
        messages.error(request, "Ban khong co quyen tao giam gia.")
        return redirect("billing:home")
    if request.method == "GET" and not is_htmx_request(request):
        # Luon hien trong modal, chuyen ve danh sach neu truy cap truc tiep
        return redirect("billing:discount_list")
    if request.method == "POST":
        form = DiscountForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Da tao ma giam gia.")
            if is_htmx_request(request):
                response = HttpResponse(status=204)
                response["HX-Redirect"] = reverse("billing:discount_list")
                return response
            return redirect("billing:discount_list")
    else:
        form = DiscountForm()
    context = {
        "form": form,
        "action_url": reverse("billing:discount_create"),
    }
    status_code = 422 if request.method == "POST" and is_htmx_request(request) else 200
    response = render(request, "_discount_form.html", context, status=status_code)
    if request.method == "POST" and is_htmx_request(request) and not form.is_valid():
        response["HX-Trigger"] = json.dumps({
            "show-sweet-alert": {
                "icon": "error",
                "title": "Không thể tạo mã giảm giá",
                "text": form_errors_as_text(form),
            }
        })
    return response


@login_required
def discount_update(request, pk):
    if not request.user.is_staff:
        messages.error(request, "Ban khong co quyen sua giam gia.")
        return redirect("billing:home")
    discount = get_object_or_404(Discount, pk=pk)
    if request.method == "GET" and not is_htmx_request(request):
        return redirect("billing:discount_list")
    if request.method == "POST":
        form = DiscountForm(request.POST, instance=discount)
        if form.is_valid():
            form.save()
            messages.success(request, "Da cap nhat ma giam gia.")
            if is_htmx_request(request):
                response = HttpResponse(status=204)
                response["HX-Redirect"] = reverse("billing:discount_list")
                return response
            return redirect("billing:discount_list")
    else:
        form = DiscountForm(instance=discount)
    context = {
        "form": form,
        "action_url": reverse("billing:discount_update", args=[discount.pk]),
    }
    status_code = 422 if request.method == "POST" and is_htmx_request(request) else 200
    response = render(request, "_discount_form.html", context, status=status_code)
    if request.method == "POST" and is_htmx_request(request) and not form.is_valid():
        response["HX-Trigger"] = json.dumps({
            "show-sweet-alert": {
                "icon": "error",
                "title": "Không thể cập nhật mã giảm giá",
                "text": form_errors_as_text(form),
            }
        })
    return response


@login_required
def discount_delete(request, pk):
    if not request.user.is_staff:
        messages.error(request, "Ban khong co quyen xoa giam gia.")
        return redirect("billing:home")
    if request.method != "POST":
        return redirect("billing:discount_list")
    discount = get_object_or_404(Discount, pk=pk)
    discount_name = discount.code or str(discount)
    discount.delete()
    messages.success(request, f"Da xoa ma giam gia {discount_name}.")
    if is_htmx_request(request):
        response = HttpResponse(status=204)
        response["HX-Redirect"] = reverse("billing:discount_list")
        return response
    return redirect("billing:discount_list")
