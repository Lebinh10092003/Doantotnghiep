# apps/classes/views.py

import json
from datetime import date, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.http import require_POST
from django_filters.views import FilterView
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.http import QueryDict
from django import forms
from apps.centers.models import Center
from apps.curriculum.models import Subject
from apps.accounts.models import User
from .models import Class
from .filters import ClassFilter
from .forms import ClassForm, ClassScheduleFormSet
from apps.filters.models import SavedFilter
from django.core.paginator import Paginator, EmptyPage


def is_htmx_request(request):
    return request.headers.get("HX-Request") == "true"

@login_required
@permission_required("classes.view_class", raise_exception=True)
def manage_classes(request):
    
    # 1. Lọc
    base_qs = Class.objects.select_related(
        "center", "subject", "main_teacher"
    )
    class_filter = ClassFilter(request.GET, queryset=base_qs)
    
    # 2. Sắp xếp
    qs = class_filter.qs.order_by("-start_date", "name")

    # +++ THÊM LOGIC TẠO BADGE LỌC +++
    active_filter_badges = []
    # Kiểm tra xem form có dữ liệu không (ví dụ: có request.GET)
    if class_filter.form.is_bound:
        # Lặp qua dữ liệu đã được làm sạch và xác thực
        for name, value in class_filter.form.cleaned_data.items():
            # Chỉ xử lý nếu trường có giá trị VÀ trường đó có trong form
            if value and name in class_filter.form.fields: 
                field_label = class_filter.form.fields[name].label or name
                display_value = ""

                # Xử lý giá trị là model instance (FK, ModelChoice)
                if isinstance(value, (Center, Subject, User)):
                    display_value = str(value)
                # Xử lý giá trị là ChoiceField (lấy tên hiển thị)
                elif isinstance(class_filter.form.fields[name], forms.ChoiceField):
                    display_value = dict(class_filter.form.fields[name].choices).get(value) if value else None
                # Xử lý giá trị là DateFromToRangeFilter (kiểu slice)
                elif isinstance(value, slice): 
                    start, end = value.start, value.stop
                    if start and end:
                        display_value = f"từ {start.strftime('%d/%m/%Y')} đến {end.strftime('%d/%m/%Y')}"
                    elif start:
                        display_value = f"từ {start.strftime('%d/%m/%Y')}"
                    elif end:
                        display_value = f"đến {end.strftime('%d/%m/%Y')}"
                # Xử lý giá trị là chuỗi (CharFilter)
                elif isinstance(value, str) and value:
                    display_value = value
                
                # Nếu có giá trị hiển thị, thêm vào danh sách
                if display_value:
                    active_filter_badges.append({
                        "label": field_label,
                        "value": display_value,
                        "key": name, 
                    })
    # 3. Phân trang
    try:
        per_page = int(request.GET.get("per_page", 10)) 
    except (TypeError, ValueError):
        per_page = 10
    try:
        page_number = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page_number = 1
    
    paginator = Paginator(qs, per_page)
    try:
        page_obj = paginator.page(page_number)
    except EmptyPage:
        page_obj = paginator.page(1)

    # Lấy quick_filters 
    quick_filters = [
        {"name": "Đang diễn ra", "params": "status=ONGOING"},
        {"name": "Đã lên kế hoạch", "params": "status=PLANNED"},
        {"name": "Đã hoàn thành", "params": "status=COMPLETED"},
    ]
    
    # Lấy saved_filters
    saved_filters = SavedFilter.objects.filter(model_name="Class").filter(
        Q(user=request.user) | Q(is_public=True)
    ).distinct()

    # Tìm tên bộ lọc đang hoạt động
    active_filter_name = None
    current_params_dict = {k: v_list for k, v_list in request.GET.lists() if k != 'page'}

    if current_params_dict:
        # Kiểm tra quick filters
        for qf in quick_filters:
            qf_dict = {k: v_list for k, v_list in QueryDict(qf['params']).lists()}
            if qf_dict == current_params_dict:
                active_filter_name = qf['name']
                break
        # Nếu không phải quick filter, kiểm tra saved filters
        if not active_filter_name:
            for sf in saved_filters:
                try:
                    # Chú ý: Dựa trên file 'filters/views.py' của bạn, 
                    # query_params được lưu dưới dạng JSONField (dict)
                    sf_dict = sf.query_params
                    if sf_dict == current_params_dict:
                        active_filter_name = sf.name
                        break
                except (json.JSONDecodeError, TypeError):
                    continue

    # 4. Xây dựng Context
    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "filter": class_filter,
        "model_name": "Class",
        "current_query_params": request.GET.urlencode(),
        "quick_filters": quick_filters,
        "active_filter_name": active_filter_name,
        "active_filter_badges": active_filter_badges, # <-- Thêm dòng này
    }

    # 5. Render
    if is_htmx_request(request):
        # Nếu là yêu cầu HTMX (lọc, phân trang, xóa lọc), chỉ trả về phần nội dung có thể lọc
        return render(request, "_class_filterable_content.html", context)
    
    # Nếu là yêu cầu thông thường, tải trang đầy đủ
    return render(request, "manage_classes.html", context)

@login_required
@permission_required("classes.add_class", raise_exception=True)
def class_create_view(request):
    if request.method == "POST":
        form = ClassForm(request.POST, request.FILES)
        formset = ClassScheduleFormSet(request.POST, prefix='schedules')
        if form.is_valid() and formset.is_valid():
            klass = form.save()
            formset.instance = klass
            formset.save()
            
            response = HttpResponse(status=204)
            response["HX-Trigger"] = json.dumps({
                "reload-classes-table": True,
                "closeClassModal": True,
                "show-sweet-alert": {"icon": "success", "title": f"Đã tạo lớp '{klass.name}'!"}
            })
            return response
        else:
            context = {"form": form, "formset": formset}
            return render(request, "_class_form.html", context, status=400)
    
    form = ClassForm()
    formset = ClassScheduleFormSet(prefix='schedules')
    context = {"form": form, "formset": formset, "is_create": True}
    return render(request, "_class_form.html", context)


@login_required
@permission_required("classes.change_class", raise_exception=True)
def class_edit_view(request, pk):
    klass = get_object_or_404(Class.objects.prefetch_related('weekly_schedules'), pk=pk)
    if request.method == "POST":
        form = ClassForm(request.POST, request.FILES, instance=klass)
        formset = ClassScheduleFormSet(request.POST, instance=klass, prefix='schedules')
        
        if form.is_valid() and formset.is_valid():
            klass = form.save()
            formset.save()

            # Kiểm tra xem lịch học có thay đổi không
            if formset.has_changed():
                # Nếu có, xóa các buổi học 'PLANNED' cũ để người dùng có thể tạo lại
                from apps.class_sessions.models import ClassSession
                deleted_count, _ = ClassSession.objects.filter(klass=klass, status='PLANNED').delete()
                if deleted_count > 0:
                    pass

            response = HttpResponse(status=204)
            response["HX-Trigger"] = json.dumps({
                "reload-classes-table": True,
                "closeClassModal": True,
                "show-sweet-alert": {
                    "icon": "success",
                    "title": "Thành công",
                    "text": f"Đã cập nhật lớp '{klass.name}'!"
                }
            })
            return response
        else:
            context = {"form": form, "formset": formset, "klass": klass}
            return render(request, "_class_form.html", context, status=400)
    
    form = ClassForm(instance=klass)
    formset = ClassScheduleFormSet(instance=klass, prefix='schedules')
    context = {"form": form, "formset": formset, "klass": klass}
    return render(request, "_class_form.html", context)


@login_required
@permission_required("classes.view_class", raise_exception=True)
def class_detail_view(request, pk):
    klass = get_object_or_404(
        Class.objects.select_related("center", "subject", "main_teacher", "room").prefetch_related("assistants", "sessions", "weekly_schedules"),
        pk=pk
    )
    context = {"klass": klass}
    response = render(request, "_class_detail.html", context)
    return response


@require_POST
@login_required
@permission_required("classes.delete_class", raise_exception=True)
def class_delete_view(request, pk):
    klass = get_object_or_404(Class, pk=pk)
    klass_name = klass.name
    
    # Kiểm tra ràng buộc
    if klass.sessions.exists():
        response = HttpResponse(status=400) # Bad Request
        response["HX-Trigger"] = json.dumps({
            "show-sweet-alert": {
                "icon": "error",
                "title": "Không thể xóa",
                "text": f"Lớp '{klass_name}' vẫn còn các buổi học. Vui lòng xóa các buổi học trước."
            }
        })
        return response

    klass.delete()
    response = HttpResponse(status=200)
    response["HX-Trigger"] = json.dumps({
        "reload-classes-table": True,
        "closeClassModal": True,
        "show-sweet-alert": {
            "icon": "success",
            "title": f"Đã xóa lớp '{klass_name}'!"
        }
    })
    return response

@require_POST
@login_required
@permission_required("class_sessions.add_classsession", raise_exception=True)
def generate_sessions_view(request, pk):
    klass = get_object_or_404(
        Class.objects.prefetch_related("weekly_schedules"), 
        pk=pk
    )
    
    schedules = klass.weekly_schedules.all()
    start_date = klass.start_date
    end_date = klass.end_date

    # --- Validation ---
    if not schedules.exists():
        return JsonResponse({"error": "Lớp học chưa có lịch học hàng tuần."}, status=400)
    if not start_date or not end_date:
        return JsonResponse({"error": "Vui lòng đặt Ngày bắt đầu và Ngày kết thúc cho lớp học."}, status=400)
    if start_date > end_date:
        return JsonResponse({"error": "Ngày bắt đầu không được sau Ngày kết thúc."}, status=400)

    # Xóa các buổi học cũ ở trạng thái "PLANNED" trước khi tạo mới
    from apps.class_sessions.models import ClassSession
    ClassSession.objects.filter(klass=klass, status='PLANNED').delete()

    # --- Logic tạo buổi học ---
    from apps.class_sessions.models import ClassSession
    
    sessions_to_create = []
    current_date = start_date
    
    while current_date <= end_date:
        # Lấy lịch học cho ngày hiện tại (0=Thứ 2, 1=Thứ 3,...)
        day_schedules = schedules.filter(day_of_week=current_date.weekday())
        
        for schedule in day_schedules:
            sessions_to_create.append(
                ClassSession(
                    klass=klass,
                    date=current_date,
                    start_time=schedule.start_time,
                    end_time=schedule.end_time,
                    # index sẽ được gán sau
                )
            )
        current_date += timedelta(days=1)

    if not sessions_to_create:
        alert = {
            "icon": "info",
            "title": "Không có buổi học nào được tạo",
            "text": "Vui lòng kiểm tra lại lịch học và khoảng thời gian của lớp."
        }
        response = HttpResponse(status=200)
        response["HX-Trigger"] = json.dumps({"show-sweet-alert": alert})
        return response

    # Sắp xếp và gán `index`
    sessions_to_create.sort(key=lambda s: (s.date, s.start_time))
    for i, session in enumerate(sessions_to_create, 1):
        session.index = i

    # Tạo hàng loạt. `ignore_conflicts` không cần thiết vì đã xóa các buổi PLANNED
    created_sessions = ClassSession.objects.bulk_create(sessions_to_create)

    alert = {
        "icon": "success",
        "title": "Thành công!",
        "text": f"Đã tạo thành công {len(created_sessions)} buổi học cho lớp '{klass.name}'."
    }
    response = HttpResponse(status=204) # No content, chỉ trigger event
    response["HX-Trigger"] = json.dumps({
        "show-sweet-alert": alert,
        "reload-sessions-table": True, # Trigger để reload bảng buổi học nếu có
    })
    return response