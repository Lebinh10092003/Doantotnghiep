import json
from datetime import timedelta

from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group

from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q, Count

from .models import ParentStudentRelation

User = get_user_model()


def is_htmx_request(request):
    """
    Kiểm tra request HTMX theo nhiều cách:
    - Header 'HX-Request' (modern)
    - META 'HTTP_HX_REQUEST' (fallback)
    - request.htmx nếu django-htmx được cài và middleware hoạt động
    """
    return (
        request.headers.get("HX-Request") == "true"
        or request.META.get("HTTP_HX_REQUEST") == "true"
        or bool(getattr(request, "htmx", False))
    )


@ensure_csrf_cookie
def login_view(request):
    if request.method == "POST":
        login_id = request.POST.get("phone", "").strip()
        password = request.POST.get("password", "")
        remember = request.POST.get("remember")

        # Tìm user theo phone
        user = User.objects.filter(phone=login_id).first()
        if not user:
            if is_htmx_request(request):
                resp = HttpResponse("", status=400)
                resp["HX-Trigger"] = json.dumps({
                    "modal": {"icon": "error", "title": "Số điện thoại không tồn tại"}
                })
                return resp
            return redirect("accounts:login")

        # Kiểm tra mật khẩu
        auth_user = authenticate(request, username=user.username, password=password)
        if not auth_user:
            if is_htmx_request(request):
                resp = HttpResponse("", status=400)
                resp["HX-Trigger"] = json.dumps({
                    "modal": {"icon": "error", "title": "Mật khẩu không đúng"}
                })
                return resp
            return redirect("accounts:login")

        # Đăng nhập
        login(request, auth_user)
        # Ghi nhớ đăng nhập
        if remember == "on":
            request.session.set_expiry(timedelta(days=14))  # giữ 14 ngày
        else:
            request.session.set_expiry(0)  # hết khi đóng browser

        # Nếu request HTMX: trả modal + redirect
        if is_htmx_request(request):
            resp = HttpResponse("")
            resp["HX-Trigger"] = json.dumps({
                "modal": {
                    "icon": "success",
                    "title": "Đăng nhập thành công!",
                    "redirect": "/"   # redirect sau khi modal đóng
                }
            })
            return resp

        # Nếu request thường: redirect về home
        return redirect("common:home")

    # GET: render form login
    return render(request, "login.html")


@require_POST
def logout_view(request):
    logout(request)
    if is_htmx_request(request):
        resp = HttpResponse("")
        resp["HX-Trigger"] = json.dumps({
            "modal": {
                "icon": "success",
                "title": "Đăng xuất thành công!",
                "redirect": "/"
            }
        })
        return resp
    return redirect("common:home")


def is_admin(user):
    return user.is_superuser or getattr(user, "role", None) == "ADMIN"


@login_required
def manage_accounts(request):
    """
    Search / filter / group / paginate users.
    Trả partial template khi HTMX request.
    """
    qs = User.objects.all().select_related()  # sửa select_related nếu cần FK cụ thể

    # params
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    role = request.GET.get("role", "")
    group_by = request.GET.get("group_by", "")
    try:
        per_page = int(request.GET.get("per_page", 10))
    except (TypeError, ValueError):
        per_page = 10
    try:
        page = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page = 1

    # Search (name, email, phone)
    if q:
        qs = qs.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(email__icontains=q) |
            Q(phone__icontains=q)
        )

    # Filter example: status (active/inactive)
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)

    # Filter by role if you store role on user or via groups
    if role:
        qs = qs.filter(groups__name=role)

    # Group by handling: for UI grouping we order by the field and later render headers
    if group_by == "role":
        qs = qs.annotate(role_count=Count("groups__name")).order_by("groups__name", "first_name")
    elif group_by == "center":
        # Thay profile__center__name bằng trường thực tế nếu khác
        qs = qs.order_by("profile__center__name", "first_name")
    else:
        qs = qs.order_by("first_name")

    paginator = Paginator(qs, per_page)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(1)

    relations = ParentStudentRelation.objects.select_related("parent", "student").all()

    # Lấy danh sách role từ Group để đổ vào select
    groups_list = list(Group.objects.values_list("name", flat=True))

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "status": status,
        "role": role,
        "group_by": group_by,
        "per_page": per_page,
        "relations": relations,
        "groups_list": groups_list,
    }

    # Nếu HTMX request trả partial only bảng
    if is_htmx_request(request):
        # partial template path thường là "accounts/_accounts_table.html"
        return render(request, "_accounts_table.html", context)

    return render(request, "manage_accounts.html", context)
