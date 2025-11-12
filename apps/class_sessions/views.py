import json
from datetime import date, timedelta
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.http import require_POST
from django_filters.views import FilterView
from django.db.models import Q
from django.http import HttpResponse, QueryDict
from django import forms 

from .models import ClassSession
from .filters import ClassSessionFilter
from .forms import ClassSessionForm 
from apps.filters.models import SavedFilter
from django.core.paginator import Paginator, EmptyPage

# IMPORT CHO LOGIC BADGE
from apps.centers.models import Center
from apps.curriculum.models import Subject, Lesson
from apps.accounts.models import User


def is_htmx_request(request):
    return request.headers.get("HX-Request") == "true"

@login_required
@permission_required("class_sessions.view_classsession", raise_exception=True)
def manage_class_sessions(request):
    
    # 1. Lọc
    base_qs = ClassSession.objects.select_related(
        "klass__center", "klass__subject", "lesson", "teacher_override", "klass__main_teacher"
    )
    session_filter = ClassSessionFilter(request.GET, queryset=base_qs)
    qs = session_filter.qs
    
    # 2. Sắp xếp
    qs = qs.order_by("-date", "-start_time", "klass__name")

    # Logic tạo Badge lọc
    active_filter_badges = []
    if session_filter.form.is_bound:
        for name, value in session_filter.form.cleaned_data.items():
            if value and name in session_filter.form.fields:
                field_label = session_filter.form.fields[name].label or name
                display_value = ""

                if isinstance(value, (User, Center, Subject, Lesson)):
                    display_value = str(value)
                elif isinstance(session_filter.form.fields[name], forms.ChoiceField):
                    # Đã sửa: Thêm kiểm tra 'if value else None'
                    display_value = dict(session_filter.form.fields[name].choices).get(value) if value else None
                elif isinstance(value, slice): 
                    start, end = value.start, value.stop
                    if start and end:
                        display_value = f"từ {start.strftime('%d/%m/%Y')} đến {end.strftime('%d/%m/%Y')}"
                    elif start:
                        display_value = f"từ {start.strftime('%d/%m/%Y')}"
                    elif end:
                        display_value = f"đến {end.strftime('%d/%m/%Y')}"
                elif isinstance(value, str) and value:
                    display_value = value
                
                if display_value:
                    active_filter_badges.append({
                        "label": field_label,
                        "value": display_value,
                        "key": name,
                    })

    # 3. Phân trang
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

    # Tạo query params cho phân trang, loại bỏ 'page' để tránh lặp lại
    query_params_for_pagination = request.GET.copy()
    if 'page' in query_params_for_pagination:
        del query_params_for_pagination['page']

    # 4. Xây dựng Context
    model_name = "ClassSession"
    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "filter": session_filter, 
        "model_name": model_name,
        "current_query_params": query_params_for_pagination.urlencode(),
        "active_filter_badges": active_filter_badges,
    }
    
    # Quick filters và Saved filters
    context["quick_filters"] = [
        {"name": "Đã diễn ra", "params": "status=DONE"},
        {"name": "Đã lên kế hoạch", "params": "status=PLANNED"},
        {"name": "Đã hủy", "params": "status=CANCELLED"},
    ]
    
    active_filter_name = None 
    if request.user.is_authenticated:
        saved = SavedFilter.objects.filter(model_name=model_name).filter(
            Q(user=request.user) | Q(is_public=True)
        ).distinct()
        
        if not is_htmx_request(request):
            context["my_filters"] = saved.filter(user=request.user)
            context["public_filters"] = saved.filter(is_public=True).exclude(user=request.user)
        
        current_params_dict = {k: v_list for k, v_list in request.GET.lists() if k != 'page'}
        if current_params_dict:
            for qf in context["quick_filters"]:
                qf_dict = {k: v_list for k, v_list in QueryDict(qf['params']).lists()}
                if qf_dict == current_params_dict:
                    active_filter_name = qf['name']
                    break
            if not active_filter_name:
                for sf in saved: 
                    try:
                        sf_dict = sf.query_params
                        if sf_dict == current_params_dict:
                            active_filter_name = sf.name
                            break
                    except (json.JSONDecodeError, TypeError):
                        continue
                        
    context["active_filter_name"] = active_filter_name

    # 5. Render
    if is_htmx_request(request):
        # SỬA LỖI: Chỉ dùng tên tệp tương đối
        return render(request, "_session_filterable_content.html", context)
    
    # Tải trang đầy đủ
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