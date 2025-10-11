import json
from datetime import timedelta
from django.utils.dateparse import parse_date
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group

from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q, Count
from apps.centers.models import Center
from .models import ParentStudentRelation

User = get_user_model()


def is_htmx_request(request):
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
    qs = User.objects.all().select_related("center").prefetch_related("groups")
    groups_for_dropdown = list(Group.objects.values_list("name", "name"))
    # params
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    role_choice = request.GET.get("role", "")      
    group_name = request.GET.get("group", "")    
    center_id = request.GET.get("center", "")
    is_staff = request.GET.get("is_staff", "")
    is_superuser = request.GET.get("is_superuser", "")
    date_from = request.GET.get("date_joined_from", "")
    date_to = request.GET.get("date_joined_to", "")
    last_login_from = request.GET.get("last_login_from", "")
    last_login_to = request.GET.get("last_login_to", "")
    group_by = request.GET.get("group_by", "")
    try:
        per_page = int(request.GET.get("per_page", 10))
    except (TypeError, ValueError):
        per_page = 10
    try:
        page = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page = 1

    # Search
    if q:
        tokens = [t for t in q.split() if t]
        for t in tokens:
            qs = qs.filter(
                Q(first_name__icontains=t) |
                Q(last_name__icontains=t) |
                Q(email__icontains=t) |
                Q(phone__icontains=t) |
                Q(username__icontains=t)
            )

    # Status
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)

    # Filter by role (choice field on User)
    if role_choice:
        qs = qs.filter(groups__name=role_choice).distinct()

    # Filter by Django Group (accept name or id)
    if group_name:
        if group_name.isdigit():
            qs = qs.filter(groups__id=int(group_name))
        else:
            qs = qs.filter(groups__name=group_name)
        qs = qs.distinct()

    # Center filter
    if center_id:
        try:
            cid = int(center_id)
            qs = qs.filter(center_id=cid)
        except (ValueError, TypeError):
            pass

    # staff / superuser filters
    if isinstance(is_staff, str) and is_staff:
        v = is_staff.lower()
        if v in ("1", "true", "yes", "on"):
            qs = qs.filter(is_staff=True)
        elif v in ("0", "false", "no"):
            qs = qs.filter(is_staff=False)

    if isinstance(is_superuser, str) and is_superuser:
        v = is_superuser.lower()
        if v in ("1", "true", "yes", "on"):
            qs = qs.filter(is_superuser=True)
        elif v in ("0", "false", "no"):
            qs = qs.filter(is_superuser=False)

    # Date range filters
    def apply_date_range(qs_in, field, start_str, end_str):
        qs_out = qs_in
        if start_str:
            d = parse_date(start_str)
            if d:
                qs_out = qs_out.filter(**{f"{field}__date__gte": d})
        if end_str:
            d = parse_date(end_str)
            if d:
                qs_out = qs_out.filter(**{f"{field}__date__lte": d})
        return qs_out

    qs = apply_date_range(qs, "date_joined", date_from, date_to)
    qs = apply_date_range(qs, "last_login", last_login_from, last_login_to)

    # Ordering / grouping
    if group_by == "role":
        qs = qs.order_by("role", "last_name", "first_name")
    elif group_by == "group":
        qs = qs.order_by("groups__name", "last_name", "first_name")
    elif group_by == "center":
        qs = qs.order_by("center__name", "last_name", "first_name")
    else:
        qs = qs.order_by("last_name", "first_name")

    qs = qs.distinct()

    # Pagination
    paginator = Paginator(qs, per_page)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(1)

    relations = ParentStudentRelation.objects.select_related("parent", "student").all()
    groups_list = list(Group.objects.values_list("name", flat=True))
    centers_list = list(Center.objects.values("id", "name").order_by("name"))

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "status": status,
        "role": role_choice,
        "group_list": groups_for_dropdown,
        "group": group_name,
        "groups_list": groups_list,
        "center": center_id,
        "centers_list": centers_list,
        "is_staff": is_staff,
        "is_superuser": is_superuser,
        "date_joined_from": date_from,
        "date_joined_to": date_to,
        "last_login_from": last_login_from,
        "last_login_to": last_login_to,
        "group_by": group_by,
        "per_page": per_page,
        "relations": relations,
    }

    if is_htmx_request(request):
        return render(request, "_accounts_table.html", context)

    return render(request, "manage_accounts.html", context)