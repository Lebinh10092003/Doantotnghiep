import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import EmptyPage, Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.common.utils.forms import form_errors_as_text
from apps.common.utils.http import is_htmx_request
from apps.rewards import services
from apps.rewards.forms import AwardPointsForm, RedemptionRequestForm, RewardItemForm
from apps.rewards.models import (
    PointAccount,
    RedemptionRequest,
    RedemptionStatus,
    RewardItem,
    RewardTransaction,
    SessionPointEventType,
)

# Xác định vai trò người dùng
def _role_flags(user):
    role = (getattr(user, "role", "") or "").upper()
    in_group = lambda name: user.groups.filter(name=name).exists()
    is_teacher = role == "TEACHER" or in_group("Teacher") or in_group("TEACHER")
    is_assistant = role == "ASSISTANT" or in_group("Assistant") or in_group("ASSISTANT")
    is_parent = role == "PARENT" or in_group("Parent") or in_group("PARENT")
    is_student = role == "STUDENT" or in_group("Student") or in_group("STUDENT")
    is_admin = user.is_superuser or role == "ADMIN" or in_group("Admin") or in_group("ADMIN")
    return {
        "is_teacher": is_teacher,
        "is_assistant": is_assistant,
        "is_parent": is_parent,
        "is_student": is_student,
        "is_admin": is_admin,
    }

# Tổng quan tài khoản điểm thưởng
@login_required
def account_summary(request):
    try:
        account = PointAccount.objects.filter(student=request.user).first()
        if not account:
            account = PointAccount.objects.create(student=request.user, balance=0)
    except Exception:
        account = PointAccount.get_or_create_for_student(request.user)
    try:
        per_page = int(request.GET.get("per_page", 10))
        if per_page <= 0:
            per_page = 10
    except (TypeError, ValueError):
        per_page = 10

    transactions_qs = (
        RewardTransaction.objects.filter(student=request.user)
        .select_related("item")
        .order_by("-created_at", "-id")
    )
    paginator = Paginator(transactions_qs, per_page)

    try:
        page_number = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page_number = 1

    if paginator.count:
        try:
            page_obj = paginator.page(page_number)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)
        transactions = page_obj.object_list
    else:
        page_obj = None
        transactions = []

    requests = (
        RedemptionRequest.objects.filter(student=request.user)
        .select_related("item")
        .order_by("-created_at")[:10]
    )

    query_params_no_page = request.GET.copy()
    query_params_no_page.pop("page", None)
    query_params_no_page_str = query_params_no_page.urlencode()
    page_query_prefix = f"{query_params_no_page_str}&" if query_params_no_page_str else ""
    preserved_query_params = [
        {"name": key, "value": value}
        for key, value in request.GET.items()
        if key not in {"page", "per_page"}
    ]

    return render(
        request,
        "account_summary.html",
        {
            "account": account,
            "transactions": transactions,
            "requests": requests,
            "paginator": paginator,
            "page_obj": page_obj,
            "per_page": per_page,
            "query_params_no_page": query_params_no_page_str,
            "page_query_prefix": page_query_prefix,
            "preserved_query_params": preserved_query_params,
            "transactions_total": paginator.count,
        },
    )

# Danh mục phần quà
@login_required
def catalog(request):
    account = PointAccount.get_or_create_for_student(request.user)
    items = RewardItem.objects.filter(is_active=True, stock__gt=0).order_by("-stock", "cost")
    form = RedemptionRequestForm()
    return render(request, "catalog.html", {"items": items, "account": account, "form": form})

# Gửi yêu cầu đổi quà
@login_required
@require_POST
def submit_request(request):
    form = RedemptionRequestForm(request.POST)
    if form.is_valid():
        try:
            services.submit_redemption_request(
                student=request.user,
                item=form.cleaned_data["item"],
                quantity=form.cleaned_data["quantity"],
                note=form.cleaned_data.get("note", ""),
            )
            messages.success(request, "Đã gửi yêu cầu đổi quà.")
        except ValidationError as e:
            messages.error(request, e.message)
    else:
        messages.error(request, "Dữ liệu không hợp lệ.")
    return redirect("rewards:catalog")

# Xem các yêu cầu đổi quà của tôi
@login_required
def my_requests(request):
    qs = RedemptionRequest.objects.filter(student=request.user).select_related("item").order_by("-created_at")
    return render(request, "my_requests.html", {"requests": qs})

# Cộng điểm cho học viên
@login_required
def award_points(request):
    flags = _role_flags(request.user)
    allowed = flags["is_admin"] or flags["is_teacher"] or flags["is_assistant"] or request.user.has_perm(
        "rewards.add_rewardtransaction"
    )
    if not allowed:
        raise PermissionDenied
    if request.method == "POST":
        form = AwardPointsForm(request.POST)
        if form.is_valid():
            try:
                student = form.cleaned_data["student"]
                delta = form.cleaned_data["delta"]
                reason = form.cleaned_data.get("reason", "")
                session = form.cleaned_data.get("session")
                if session:
                    services.award_session_point(
                        student=student,
                        session=session,
                        event_type=SessionPointEventType.MANUAL,
                        reason=reason or f"Cộng điểm buổi {getattr(session, 'index', '')}",
                        delta=delta,
                        allow_duplicate=False,
                    )
                else:
                    services.award_points(
                        student=student,
                        delta=delta,
                        reason=reason,
                        created_by=request.user,
                    )
                messages.success(request, "Đã cộng điểm cho học viên.")
                return redirect("rewards:award_points")
            except ValidationError as e:
                messages.error(request, e.message)
    else:
        form = AwardPointsForm()
    return render(request, "award_points.html", {"form": form})

# Quản lý phần quà
@login_required
def manage_items(request):
    if not request.user.has_perm("rewards.change_rewarditem"):
        raise PermissionDenied
    items = RewardItem.objects.all().order_by("-is_active", "name")
    edit_id = request.GET.get("edit")
    instance = None
    if edit_id and edit_id != "new":
        instance = get_object_or_404(RewardItem, pk=edit_id)
    if request.method == "POST":
        item_id = request.POST.get("item_id")
        instance = RewardItem.objects.filter(pk=item_id).first() if item_id else None
        form = RewardItemForm(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            if is_htmx_request(request):
                resp = HttpResponse(status=204)
                triggers = {
                    "reload-items-table": True,
                    "reload-catalog": True,
                    "closeRewardItemModal": True,
                    "show-sweet-alert": {"icon": "success", "title": "Đã lưu phần quà."},
                }
                resp["HX-Trigger"] = json.dumps(triggers)
                resp["HX-Trigger-After-Settle"] = json.dumps(triggers)
                return resp
            messages.success(request, "Đã lưu phần quà.")
            return redirect("rewards:manage_items")
        if is_htmx_request(request):
            response = render(
                request,
                "_reward_item_form.html",
                {"form": form, "instance": instance},
                status=422,
            )
            response["HX-Trigger"] = json.dumps({
                "show-sweet-alert": {
                    "icon": "error",
                    "title": "Không thể lưu phần quà",
                    "text": form_errors_as_text(form),
                }
            })
            return response
    else:
        form = RewardItemForm(instance=instance)

    if is_htmx_request(request):
        if edit_id is not None:
            return render(
                request,
                "_reward_item_form.html",
                {"form": form, "instance": instance},
            )
        return render(
            request, "_reward_items_table.html", {"items": items}
        )
    return render(request, "manage_items.html", {"items": items, "form": form, "editing": instance})

# Quản lý các yêu cầu đổi quà
@login_required
def manage_requests(request):
    if not request.user.has_perm("rewards.change_redemptionrequest"):
        raise PermissionDenied
    qs = RedemptionRequest.objects.select_related("student", "item").order_by("-created_at")
    if is_htmx_request(request):
        return render(
            request,
            "_redemption_requests_table.html",
            {"requests": qs, "status": RedemptionStatus},
        )
    return render(request, "manage_requests.html", {"requests": qs, "status": RedemptionStatus})

# Lấy yêu cầu đổi quà để quản lý
def _get_request_for_manage(request, pk) -> RedemptionRequest:
    if not request.user.has_perm("rewards.change_redemptionrequest"):
        raise PermissionDenied
    return get_object_or_404(RedemptionRequest.objects.select_related("item", "student"), pk=pk)

# Duyệt yêu cầu đổi quà
@login_required
@require_POST
def approve_request(request, pk):
    req = _get_request_for_manage(request, pk)
    try:
        services.approve_redemption_request(req=req, approver=request.user, note=request.POST.get("note", ""))
        if is_htmx_request(request):
            resp = HttpResponse(status=204)
            resp["HX-Trigger"] = json.dumps(
                {
                    "reload-requests-table": True,
                    "show-sweet-alert": {"icon": "success", "title": "Đã duyệt yêu cầu đổi quà."},
                }
            )
            return resp
        messages.success(request, "Đã duyệt yêu cầu đổi quà.")
    except ValidationError as e:
        if is_htmx_request(request):
            resp = HttpResponse("", status=400)
            resp["HX-Trigger"] = json.dumps({
                "show-sweet-alert": {
                    "icon": "error",
                    "title": "Không thể duyệt yêu cầu",
                    "text": str(e),
                }
            })
            return resp
        messages.error(request, e.message)
    return redirect("rewards:manage_requests")

# Từ chối yêu cầu đổi quà
@login_required
@require_POST
def reject_request(request, pk):
    req = _get_request_for_manage(request, pk)
    try:
        services.reject_redemption_request(req=req, approver=request.user, note=request.POST.get("note", ""))
        if is_htmx_request(request):
            resp = HttpResponse(status=204)
            resp["HX-Trigger"] = json.dumps(
                {
                    "reload-requests-table": True,
                    "show-sweet-alert": {"icon": "success", "title": "Đã từ chối yêu cầu."},
                }
            )
            return resp
        messages.success(request, "Đã từ chối yêu cầu.")
    except ValidationError as e:
        if is_htmx_request(request):
            resp = HttpResponse("", status=400)
            resp["HX-Trigger"] = json.dumps({
                "show-sweet-alert": {
                    "icon": "error",
                    "title": "Không thể từ chối",
                    "text": str(e),
                }
            })
            return resp
        messages.error(request, e.message)
    return redirect("rewards:manage_requests")

# Duyệt yêu cầu đổi quà và đánh dấu đã trao quà
@login_required
@require_POST
def fulfill_request(request, pk):
    req = _get_request_for_manage(request, pk)
    try:
        services.fulfill_redemption_request(req=req, approver=request.user, note=request.POST.get("note", ""))
        if is_htmx_request(request):
            resp = HttpResponse(status=204)
            resp["HX-Trigger"] = json.dumps(
                {
                    "reload-requests-table": True,
                    "show-sweet-alert": {"icon": "success", "title": "Đã đánh dấu đã trao quà."},
                }
            )
            return resp
        messages.success(request, "Đã đánh dấu đã trao quà.")
    except ValidationError as e:
        if is_htmx_request(request):
            resp = HttpResponse("", status=400)
            resp["HX-Trigger"] = json.dumps({
                "show-sweet-alert": {
                    "icon": "error",
                    "title": "Không thể đánh dấu đã trao",
                    "text": str(e),
                }
            })
            return resp
        messages.error(request, e.message)
    return redirect("rewards:manage_requests")

# Hủy yêu cầu đổi quà
@login_required
@require_POST
def cancel_request(request, pk):
    req = _get_request_for_manage(request, pk)
    try:
        services.cancel_redemption_request(req=req, actor=request.user, note=request.POST.get("note", ""))
        if is_htmx_request(request):
            resp = HttpResponse(status=204)
            resp["HX-Trigger"] = json.dumps(
                {
                    "reload-requests-table": True,
                    "show-sweet-alert": {"icon": "success", "title": "Đã hủy yêu cầu."},
                }
            )
            return resp
        messages.success(request, "Đã hủy yêu cầu.")
    except ValidationError as e:
        if is_htmx_request(request):
            resp = HttpResponse("", status=400)
            resp["HX-Trigger"] = json.dumps({
                "show-sweet-alert": {
                    "icon": "error",
                    "title": "Không thể hủy yêu cầu",
                    "text": str(e),
                }
            })
            return resp
        messages.error(request, e.message)
    return redirect("rewards:manage_requests")
