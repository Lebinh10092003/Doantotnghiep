import json
from datetime import date, timedelta
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.views.decorators.http import require_POST
from django_filters.views import FilterView
from django.db.models import Q
from django.http import HttpResponse, QueryDict, HttpResponseBadRequest
from django import forms 
from django.template.loader import render_to_string
from collections import defaultdict 
from apps.accounts.models import User, ParentStudentRelation
from apps.enrollments.models import Enrollment
from apps.attendance.models import Attendance
from apps.assessments.models import Assessment
from apps.attendance.forms import AttendanceForm
from apps.assessments.forms import AssessmentForm
from .models import ClassSession
from .filters import ClassSessionFilter
from .forms import ClassSessionForm 
from apps.filters.models import SavedFilter
from django.core.paginator import Paginator, EmptyPage
from apps.centers.models import Center
from apps.curriculum.models import Subject, Lesson


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
    for key in ["page", "per_page"]:
        if key in query_params_for_pagination:
            del query_params_for_pagination[key]

    # 4. Xây dựng Context
    model_name = "ClassSession"
    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
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
        return render(request, "_session_filterable_content.html", context)
    
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
            "klass", "klass__center", "lesson", "lesson__lecture", "lesson__exercise",
            "teacher_override", "room_override", "klass__main_teacher"
        ).prefetch_related("assistants"),
        pk=pk
    )
    
    # 1. Lấy danh sách học sinh đã đăng ký (active)
    enrollments = Enrollment.objects.filter(
        klass=session.klass, active=True
    ).select_related('student')
    student_ids = [e.student_id for e in enrollments] # Lấy ID học sinh

    # 2. Lấy tất cả bản ghi điểm danh & đánh giá cho buổi này
    attendance_records = {
        att.student_id: att for att in Attendance.objects.filter(session=session, student_id__in=student_ids)
    }
    assessment_records = {
        asm.student_id: asm for asm in Assessment.objects.filter(session=session, student_id__in=student_ids)
    }
    
    # 3. Lấy thông tin phụ huynh
    parent_relations = ParentStudentRelation.objects.filter(
        student_id__in=student_ids
    ).select_related('parent')
    
    # Tạo map: {student_id: [parent1, parent2, ...]}
    parents_map = defaultdict(list)
    for rel in parent_relations:
        parents_map[rel.student_id].append(rel.parent)

    # 4. Chuẩn bị dữ liệu cho template
    student_data_list = []
    for enrollment in enrollments:
        student = enrollment.student
        student_data_list.append({
            "student": student,
            "enrollment": enrollment,
            "attendance": attendance_records.get(student.id), 
            "assessment": assessment_records.get(student.id),
            "parents": parents_map.get(student.id, []), # Thêm phụ huynh vào data
        })

    context = {
        "session": session,
        "student_data_list": student_data_list, 
    }
    
    if is_htmx_request(request):
        context["as_page"] = request.GET.get("as_page", "false") == "true"
        return render(request, "_session_detail.html", context)
    
    context["as_page"] = True
    return render(request, "session_detail.html", context)


@login_required
@permission_required("class_sessions.view_classsession", raise_exception=True)
def student_attendance_assessment_modal(request, session_id, student_id):
    """
    Modal hiển thị form Điểm danh & Đánh giá cho một học sinh trong một buổi học,
    sử dụng lại các view & template của apps attendance và assessments.
    """
    session = get_object_or_404(
        ClassSession.objects.select_related(
            "klass", "klass__center", "lesson", "teacher_override", "room_override", "klass__main_teacher"
        ),
        pk=session_id,
    )
    student = get_object_or_404(User, pk=student_id)

    attendance = Attendance.objects.filter(session=session, student=student).first()
    assessment = Assessment.objects.filter(session=session, student=student).first()

    context = {
        "session": session,
        "student": student,
        "attendance": attendance,
        "assessment": assessment,
    }
    # Template này nằm trực tiếp dưới apps/class_sessions/templates/
    return render(request, "_student_attendance_assessment_modal.html", context)


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

#
# === VIEW MỚI ĐỂ XỬ LÝ LƯU THEO HÀNG ===
#
@require_POST
@login_required
@permission_required("attendance.change_attendance")
@permission_required("assessments.change_assessment")
def update_student_session_status(request, session_id, student_id):
    """
    Xử lý một request HTMX POST để cập nhật đồng thời
    Attendance và Assessment cho một học sinh.
    """
    session = get_object_or_404(ClassSession, pk=session_id)
    student = get_object_or_404(User, pk=student_id)
    
    # 1. Lấy hoặc tạo các đối tượng
    attendance, _ = Attendance.objects.get_or_create(session=session, student=student)
    assessment, _ = Assessment.objects.get_or_create(session=session, student=student)
    
    # 2. Tạo form từ dữ liệu POST
    attendance_form = AttendanceForm(request.POST, instance=attendance)
    assessment_form = AssessmentForm(request.POST, instance=assessment)

    # 3. Validate và Lưu
    if attendance_form.is_valid() and assessment_form.is_valid():
        attendance_form.save()
        assessment_form.save()
        
        # 4. Chuẩn bị context và trả về fragment
        enrollment = Enrollment.objects.filter(klass=session.klass, student=student).first()
        
        # Lấy lại thông tin phụ huynh cho hàng <tr>
        parents = list(ParentStudentRelation.objects.filter(student=student).select_related('parent'))

        student_data = {
            "student": student,
            "enrollment": enrollment,
            "attendance": attendance,
            "assessment": assessment,
            "parents": [rel.parent for rel in parents], # Truyền phụ huynh
        }
        
        # Render lại chỉ cái hàng <tr> đó
        html = render_to_string(
            "_session_student_row.html",
            {"data": student_data, "session": session, "request": request, "success": True},
            request=request,
        )
        response = HttpResponse(html)
        # Gửi trigger để hiển thị thông báo và đóng modal
        response["HX-Trigger"] = json.dumps({
            "show-sweet-alert": {
                "icon": "success",
                "title": "Đã lưu điểm danh & đánh giá!",
                "timer": 1500,
            },
            "closeAttendanceModal": True,
        })
        return response

    return HttpResponseBadRequest("Dữ liệu không hợp lệ")


@login_required
def my_schedule_view(request):
    today = date.today()
    try:
        start = date.fromisoformat(request.GET.get("start")) if request.GET.get("start") else today - timedelta(days=today.weekday())
    except ValueError:
        start = today - timedelta(days=today.weekday())
    try:
        end = date.fromisoformat(request.GET.get("end")) if request.GET.get("end") else start + timedelta(days=6)
    except ValueError:
        end = start + timedelta(days=6)

    user = request.user
    sessions_qs = ClassSession.objects.select_related(
        "klass", "klass__subject", "klass__center", "klass__main_teacher", "lesson"
    ).prefetch_related("assistants").filter(date__isnull=False, date__range=(start, end))

    selected_student_id = request.GET.get("student")
    user_role = (user.role or "").upper()

    if user_role == "PARENT":
        children_ids = list(
            ParentStudentRelation.objects.filter(parent=user).values_list("student_id", flat=True)
        )
        if selected_student_id:
            try:
                sid = int(selected_student_id)
                if sid in children_ids:
                    children_ids = [sid]
            except (TypeError, ValueError):
                pass
        sessions_qs = sessions_qs.filter(klass__enrollments__student_id__in=children_ids, klass__enrollments__active=True)
        children = User.objects.filter(id__in=children_ids)
    elif user_role == "STUDENT":
        sessions_qs = sessions_qs.filter(klass__enrollments__student=user, klass__enrollments__active=True)
        children = None
    else:
        sessions_qs = sessions_qs.filter(klass__enrollments__student=user, klass__enrollments__active=True)
        children = None

    sessions = sessions_qs.order_by("date", "start_time", "klass__name").distinct()

    context = {
        "sessions": sessions,
        "start": start,
        "end": end,
        "is_parent": user_role == "PARENT",
        "children": children,
        "selected_student": selected_student_id,
        "today": today,
    }
    if is_htmx_request(request):
        return render(request, "_schedule_table.html", context)
    return render(request, "my_schedule.html", context)


@login_required
def teaching_schedule_view(request):
    today = date.today()
    try:
        selected_date = date.fromisoformat(request.GET.get("date")) if request.GET.get("date") else today
    except ValueError:
        selected_date = today
    start_of_week = selected_date - timedelta(days=selected_date.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    viewer = request.user
    teacher_id = request.GET.get("teacher")

    teacher = viewer
    if teacher_id and viewer.has_perm("class_sessions.view_classsession"):
        try:
            teacher = User.objects.get(pk=int(teacher_id))
        except (User.DoesNotExist, ValueError, TypeError):
            teacher = viewer

    base = ClassSession.objects.select_related(
        "klass", "klass__subject", "klass__center", "klass__main_teacher", "lesson"
    ).prefetch_related("assistants").filter(date__isnull=False, date__range=(start_of_week, end_of_week))

    sessions = base.filter(
        Q(teacher_override=teacher) |
        Q(klass__main_teacher=teacher) |
        Q(assistants=teacher) |
        Q(klass__assistants=teacher)
    ).order_by("date", "start_time", "klass__name").distinct()

    teachers = None
    if viewer.has_perm("class_sessions.view_classsession"):
        teachers = User.objects.filter(Q(groups__name__in=["Teacher", "TEACHER"]) | Q(role__iexact="TEACHER")).distinct()

    context = {
        "sessions": sessions,
        "date": selected_date,
        "start": start_of_week,
        "end": end_of_week,
        "teacher": teacher,
        "teachers": teachers,
        "today": today,
    }
    if is_htmx_request(request):
        return render(request, "_schedule_table.html", context)
    return render(request, "teaching_schedule.html", context)


@login_required
def teaching_classes_view(request):
    from apps.classes.models import Class

    viewer = request.user
    teacher_id = request.GET.get("teacher")
    teacher = viewer
    if teacher_id and viewer.has_perm("classes.view_class"):
        try:
            teacher = User.objects.get(pk=int(teacher_id))
        except (User.DoesNotExist, ValueError, TypeError):
            teacher = viewer

    qs = Class.objects.select_related("center", "subject", "main_teacher") \
        .prefetch_related("assistants") \
        .filter(
            Q(main_teacher=teacher) | Q(assistants=teacher),
            status__in=["PLANNED", "ONGOING"]
        ) \
        .order_by("center__name", "name") \
        .distinct()

    teachers = None
    if viewer.has_perm("classes.view_class"):
        teachers = User.objects.filter(Q(groups__name__in=["Teacher", "TEACHER"]) | Q(role__iexact="TEACHER")).distinct()

    context = {
        "classes": qs,
        "teacher": teacher,
        "teachers": teachers,
    }
    if is_htmx_request(request):
        return render(request, "_teaching_classes_table.html", context)
    return render(request, "teaching_classes.html", context)
