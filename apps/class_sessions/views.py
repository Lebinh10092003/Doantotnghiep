# apps/class_sessions/views.py

import json
from datetime import date, timedelta
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.http import require_POST
from django_filters.views import FilterView
from django.db.models import Q
from django.http import HttpResponse

from .models import ClassSession
from .filters import ClassSessionFilter
from .forms import ClassSessionForm 
from apps.filters.models import SavedFilter
from django.core.paginator import Paginator, EmptyPage

def is_htmx_request(request):
    return request.headers.get("HX-Request") == "true"

@login_required
@permission_required("class_sessions.view_classsession", raise_exception=True)
def manage_class_sessions(request):
    
    # 1. Lọc (Sử dụng ClassSessionFilter đã định nghĩa)
    # Queryset cơ sở
    base_qs = ClassSession.objects.select_related(
        "klass__center", "klass__subject", "lesson", "teacher_override", "klass__main_teacher"
    )
    # Áp dụng filter
    session_filter = ClassSessionFilter(request.GET, queryset=base_qs)
    qs = session_filter.qs
    # 2. Sắp xếp (Giống logic của accounts/centers)
    qs = qs.order_by("-date", "-start_time", "klass__name")
    # 3. Phân trang (Giống logic của accounts/centers)
    try:
        per_page = int(request.GET.get("per_page", 25))
    except (TypeError, ValueError):
        per_page = 25
    try:
        page_number = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page_number = 1
    
    paginator = Paginator(qs, per_page)
    try:
        page_obj = paginator.page(page_number)
    except EmptyPage:
        page_obj = paginator.page(1)

    # 4. Xây dựng Context (Giống logic của accounts/centers)
    model_name = "ClassSession"
    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "filter": session_filter, # Truyền filterset vào context
        "model_name": model_name,
        "current_query_params": request.GET.urlencode(),
    }
    
    # Thêm các bộ lọc nhanh và đã lưu
    context["quick_filters"] = [
        {"name": "Đã diễn ra", "params": "status=DONE"},
        {"name": "Đã lên kế hoạch", "params": "status=PLANNED"},
        {"name": "Đã hủy", "params": "status=CANCELLED"},
    ]
    
    if request.user.is_authenticated:
        saved = SavedFilter.objects.filter(model_name=model_name).filter(
            Q(user=request.user) | Q(is_public=True)
        ).distinct()
        context["my_filters"] = saved.filter(user=request.user)
        context["public_filters"] = saved.filter(is_public=True).exclude(user=request.user)

    # 5. Render (Giống logic của accounts/centers)
    if is_htmx_request(request):
        return render(request, "_class_sessions_table.html", context)
    
    return render(request, "manage_class_sessions.html", context)

@login_required
@permission_required("class_sessions.add_classsession", raise_exception=True)
def session_create_view(request):
    if request.method == "POST":
        form = ClassSessionForm(request.POST)
        if form.is_valid():
            session = form.save()
            response = HttpResponse(status=200)
            response["HX-Trigger"] = json.dumps({
                "reload-sessions-table": True,
                "closeSessionModal": True,
                "show-sweet-alert": {
                    "icon": "success",
                    "title": f"Đã tạo Buổi {session.index} cho lớp '{session.klass.name}'!"
                }
            })
            return response
        else:
            context = {"form": form}
            return render(request, "_session_form.html", context, status=422)
    
    form = ClassSessionForm()
    context = {"form": form, "is_create": True}
    return render(request, "_session_form.html", context)


@login_required
@permission_required("class_sessions.change_classsession", raise_exception=True)
def session_edit_view(request, pk):
    session = get_object_or_404(ClassSession, pk=pk)
    if request.method == "POST":
        form = ClassSessionForm(request.POST, instance=session)
        if form.is_valid():
            session = form.save()
            response = HttpResponse(status=200)
            response["HX-Trigger"] = json.dumps({
                "reload-sessions-table": True,
                "closeSessionModal": True,
                "show-sweet-alert": {
                    "icon": "success",
                    "title": f"Đã cập nhật Buổi {session.index}!"
                }
            })
            return response
        else:
            context = {"form": form, "session": session}
            return render(request, "_session_form.html", context, status=422)
    
    form = ClassSessionForm(instance=session)
    context = {"form": form, "session": session}
    return render(request, "_session_form.html", context)


@login_required
@permission_required("class_sessions.view_classsession", raise_exception=True)
def session_detail_view(request, pk):
    session = get_object_or_404(
        ClassSession.objects.select_related(
            "klass", "klass__center", "lesson", "teacher_override", "room_override", "klass__main_teacher"
        ).prefetch_related("assistants"),
        pk=pk
    )
    context = {"session": session}
    response = render(request, "_session_detail.html", context)
    return response


@require_POST
@login_required
@permission_required("class_sessions.delete_classsession", raise_exception=True)
def session_delete_view(request, pk):
    session = get_object_or_404(ClassSession, pk=pk)
    session_name = f"Buổi {session.index} của lớp {session.klass.name}"
    
    session.delete()
    response = HttpResponse(status=200)
    response["HX-Trigger"] = json.dumps({
        "reload-sessions-table": True,
        "closeSessionModal": True,
        "show-sweet-alert": {
            "icon": "success",
            "title": f"Đã xóa '{session_name}'!"
        }
    })
    return response