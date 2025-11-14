import json
from datetime import date, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.http import require_POST
from django_filters.views import FilterView
from django.db.models import Q
from django.http import HttpResponse
from django.http import QueryDict
from django import forms
from apps.centers.models import Center
from django.utils import timezone
from apps.curriculum.models import Subject
from apps.accounts.models import User
from .models import Class
from .filters import ClassFilter
from .forms import ClassForm, ClassScheduleFormSet
from apps.filters.models import SavedFilter
from django.core.paginator import Paginator, EmptyPage
from apps.class_sessions.models import ClassSession
from apps.class_sessions.utils import recalculate_session_indices
from django.db import transaction
from apps.curriculum.models import Lesson



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
        Class.objects
            .select_related("center", "subject", "main_teacher", "room")
            .prefetch_related(
                "assistants",
                "sessions",
                "weekly_schedules",
                "enrollments",
                "enrollments__student",
            ),
        pk=pk,
    )
    # Lấy danh sách học sinh của lớp (Cả đang học và đã nghỉ)
    try:
        active_enrollments = [e for e in klass.enrollments.all()]
    except Exception:
        active_enrollments = []
    context = {"klass": klass, "active_enrollments": active_enrollments}
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


PLANNED_STATUS = "PLANNED"
@require_POST
@login_required
@permission_required("class_sessions.change_classsession", raise_exception=True)
def generate_sessions(request, pk):
    """
    Tạo hoặc cập nhật các buổi học cho một lớp, tự động gán Lesson.
    - Cập nhật thời gian nếu lịch học thay đổi.
    - Gán Lesson cho các buổi học mới, hoặc các buổi học cũ nhưng chưa có Lesson.
    """
    
    with transaction.atomic():
        klass = get_object_or_404(Class, pk=pk)
        schedules = klass.weekly_schedules.all()
        # 1. TRUY VẤN VÀ LẬP BẢN ĐỒ LESSONS
        # Lấy tất cả Lesson của môn học, sắp xếp theo thứ tự Module và Lesson
        all_lessons = []
        if klass.subject:
             all_lessons = list(
                Lesson.objects
                    .filter(module__subject=klass.subject)
                    .select_related('module')
                    .order_by('module__order', 'order') # Sắp xếp theo Học phần (module) rồi đến Bài học (order)
            )
        lessons_count = len(all_lessons)

        # 2. Thiết lập ngày bắt đầu và lấy sessions hiện có
        today = timezone.now().date()
        start_date_for_generation = max(klass.start_date, today)
        
        existing_sessions = {
            s.date: s for s in ClassSession.objects.filter(
                klass=klass, 
                status=PLANNED_STATUS, 
                date__gte=today 
            )
        }

        # Bộ đếm index tạm thời 
        temp_index_counter = 999999 
        sessions_to_create = []
        sessions_to_update = []
        
        # Xác định index LOGIC bắt đầu để biết Lesson nào cần được gán tiếp theo
        last_session = ClassSession.objects.filter(klass=klass).order_by('index').last()
        current_session_index = last_session.index if last_session and last_session.index else 0
        
        # 3. Lặp qua các ngày để gen sessions
        current_date = start_date_for_generation
        
        while current_date <= klass.end_date:
            for schedule in schedules:
                if current_date.weekday() == schedule.day_of_week:
                    
                    # Tăng index logic cho buổi học tiềm năng này
                    current_session_index += 1
                    
                    lesson_to_assign = None
                    # Gán Lesson nếu có sẵn
                    if lessons_count > 0 and current_session_index <= lessons_count:
                        lesson_to_assign = all_lessons[current_session_index - 1] 
                    
                    
                    if current_date in existing_sessions:
                        session_to_check = existing_sessions[current_date]
                        
                        fields_to_update = []
                        is_time_changed = (session_to_check.start_time != schedule.start_time or 
                                           session_to_check.end_time != schedule.end_time)
                        
                        # Chỉ gán Lesson nếu nó đang NULL
                        is_lesson_changed = (session_to_check.lesson is None and lesson_to_assign)
                        
                        if is_time_changed:
                            session_to_check.start_time = schedule.start_time
                            session_to_check.end_time = schedule.end_time
                            fields_to_update.extend(['start_time', 'end_time'])
                        
                        if is_lesson_changed:
                            session_to_check.lesson = lesson_to_assign
                            fields_to_update.append('lesson')
                            
                        # Chỉ thêm vào danh sách cập nhật nếu có trường cần cập nhật
                        if fields_to_update:
                            sessions_to_update.append(session_to_check)

                    else:
                        # Tạo buổi học mới
                        sessions_to_create.append(
                            ClassSession(
                                klass=klass, 
                                date=current_date, 
                                start_time=schedule.start_time, 
                                end_time=schedule.end_time, 
                                status=PLANNED_STATUS,
                                lesson=lesson_to_assign,
                                index=temp_index_counter 
                            )
                        )
                        temp_index_counter -= 1 
                        
            current_date += timedelta(days=1)

        # 4. Thực hiện Bulk Operations
        if sessions_to_create:
            ClassSession.objects.bulk_create(sessions_to_create) 
        
        if sessions_to_update:
            # Cập nhật tất cả các trường có thể thay đổi (thời gian + Lesson)
            ClassSession.objects.bulk_update(sessions_to_update, ['start_time', 'end_time', 'lesson'])

        # 5. Đánh số lại index cho toàn bộ các buổi học (sửa chữa index tạm thời)
        updated_count = recalculate_session_indices(klass.pk) 

    # 6. Trả về phản hồi HTMX
    response = HttpResponse(status=200)
    response["HX-Trigger"] = json.dumps({
        "show-sweet-alert": {
            "icon": "success",
            "title": "Thành công!",
            "text": f"Đã tạo {len(sessions_to_create)} và cập nhật {len(sessions_to_update)} buổi học. Đã đánh số lại {updated_count} index."
        },
        "reload-sessions-table": True,
        "closeClassModal": True,
    })
    return response
