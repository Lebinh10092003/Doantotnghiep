import json
from datetime import date, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.http import require_POST
from django_filters.views import FilterView
from django.db.models import Q
from django.http import HttpResponse, JsonResponse

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
    # Dùng .qs để lấy queryset đã lọc, sau đó sắp xếp
    qs = class_filter.qs.order_by("-start_date", "name")

    # 3. Phân trang
    try:
        # Lấy paginate_by = 10 từ CBV cũ
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

    # 4. Xây dựng Context
    model_name = "Class"
    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "filter": class_filter, # Truyền filterset (giống như accounts)
        "model_name": model_name,
        "current_query_params": request.GET.urlencode(),
    }

    # Lấy quick_filters từ CBV cũ
    context["quick_filters"] = [
        {"name": "Đang diễn ra", "params": "status=ONGOING"},
        {"name": "Đã lên kế hoạch", "params": "status=PLANNED"},
        {"name": "Đã hoàn thành", "params": "status=COMPLETED"},
    ]
    
    # Lấy saved_filters từ CBV cũ
    if request.user.is_authenticated:
        saved = SavedFilter.objects.filter(model_name=model_name).filter(
            Q(user=request.user) | Q(is_public=True)
        ).distinct()
        context["my_filters"] = saved.filter(user=request.user)
        context["public_filters"] = saved.filter(is_public=True).exclude(user=request.user)

    # 5. Render
    if is_htmx_request(request):
        return render(request, "_classes_table.html", context)
    
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
            
            response = HttpResponse(status=200)
            response["HX-Trigger"] = json.dumps({
                "reload-classes-table": True,
                "closeClassModal": True,
                "show-sweet-alert": {"icon": "success", "title": f"Đã tạo lớp '{klass.name}'!"}
            })
            return response
        else:
            context = {"form": form, "formset": formset}
            return render(request, "_class_form.html", context, status=422)
    
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

            response = HttpResponse(status=200)
            response["HX-Trigger"] = json.dumps({
                "reload-classes-table": True,
                "closeClassModal": True,
                "show-sweet-alert": {
                    "icon": "success",
                    "title": f"Đã cập nhật lớp '{klass.name}'!"
                }
            })
            return response
        else:
            context = {"form": form, "formset": formset, "klass": klass}
            return render(request, "_class_form.html", context, status=422)
    
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