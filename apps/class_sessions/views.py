import json
from datetime import date, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from apps.filters.utils import (
    determine_active_filter_name,
)
from django.views.decorators.http import require_POST
from django_filters.views import FilterView
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest
from django.urls import reverse
from django import forms 
from django.template.loader import render_to_string
from collections import defaultdict 
from django.core.exceptions import PermissionDenied
from apps.accounts.models import User, ParentStudentRelation
from apps.enrollments.models import Enrollment
from apps.attendance.models import Attendance
from apps.assessments.models import Assessment
from apps.attendance.forms import AttendanceForm
from apps.assessments.forms import AssessmentForm
from .models import ClassSession , ClassSessionPhoto
from .filters import ClassSessionFilter
from .forms import ClassSessionForm 
from apps.filters.models import SavedFilter
from django.core.paginator import Paginator, EmptyPage
from apps.centers.models import Center
from apps.curriculum.models import Subject, Lesson


def _session_teacher_label(session):
    teacher = session.teacher_override or session.klass.main_teacher
    if not teacher:
        return "Chưa có giáo viên"
    if hasattr(teacher, "display_name_with_email") and teacher.display_name_with_email:
        return teacher.display_name_with_email
    full_name = teacher.get_full_name()
    return full_name or teacher.username


def _session_timeslot_label(session):
    start = session.start_time.strftime("%H:%M") if session.start_time else "--"
    end = session.end_time.strftime("%H:%M") if session.end_time else "--"
    return f"{start} - {end}"


def _session_group_label(session, group_by):
    if group_by == "subject":
        return session.klass.subject.name if session.klass and session.klass.subject else "Chưa có môn"
    if group_by == "center":
        return session.klass.center.name if session.klass and session.klass.center else "Chưa có cơ sở"
    if group_by == "teacher":
        return _session_teacher_label(session)
    if group_by == "status":
        return session.get_status_display()
    if group_by == "timeslot":
        return _session_timeslot_label(session)
    if group_by == "date":
        return session.date.strftime("%d/%m/%Y") if session.date else "Chưa có ngày"
    return ""


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
    if session_filter.form.is_bound:
        session_filter.form.is_valid()
    group_by = getattr(session_filter.form, "cleaned_data", {}).get("group_by", "") or ""
    qs = session_filter.qs
    
    # 2. Sắp xếp
    if group_by == "subject":
        qs = qs.order_by("klass__subject__name", "klass__name", "index")
    elif group_by == "center":
        qs = qs.order_by("klass__center__name", "klass__name", "index")
    elif group_by == "teacher":
        qs = qs.order_by(
            "teacher_override__last_name",
            "teacher_override__first_name",
            "klass__main_teacher__last_name",
            "klass__main_teacher__first_name",
            "klass__name",
            "index",
        )
    elif group_by == "status":
        qs = qs.order_by("status", "klass__name", "index")
    elif group_by == "timeslot":
        qs = qs.order_by("start_time", "end_time", "klass__name", "index")
    elif group_by == "date":
        qs = qs.order_by("date", "start_time", "klass__name", "index")
    else:
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

    for session in page_obj.object_list:
        session.group_label = _session_group_label(session, group_by)

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
        "group_by": group_by,
    }

    saved = SavedFilter.objects.filter(model_name=model_name).filter(
        Q(user=request.user) | Q(is_public=True)
    ).distinct()

    if not is_htmx_request(request):
        context["my_filters"] = saved.filter(user=request.user)
        context["public_filters"] = saved.filter(is_public=True).exclude(user=request.user)

    context["active_filter_name"] = determine_active_filter_name(request, saved)

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
def session_detail_view(request, pk):
    session = get_object_or_404(
        ClassSession.objects.select_related(
            "klass", "klass__center", "lesson", "lesson__lecture", "lesson__exercise",
            "teacher_override", "room_override", "klass__main_teacher"
        ).prefetch_related("assistants"),
        pk=pk
    )
    viewer = request.user
    is_my_session = (
        viewer == session.klass.main_teacher
        or viewer == session.teacher_override
        or session.assistants.filter(id=viewer.id).exists()
        or session.klass.assistants.filter(id=viewer.id).exists()
    )
    if not (viewer.has_perm("class_sessions.view_classsession") or is_my_session):
        raise PermissionDenied
    can_edit_session_records = (
        viewer.has_perm("attendance.change_attendance")
        or viewer.has_perm("assessments.change_assessment")
        or is_my_session
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
        "can_edit_session_records": can_edit_session_records,
        "photos": ClassSessionPhoto.objects.filter(session=session).select_related("uploaded_by").order_by("-created_at"),
    }
    
    if is_htmx_request(request):
        context["as_page"] = request.GET.get("as_page", "false") == "true"
        return render(request, "_session_detail.html", context)
    
    context["as_page"] = True
    return render(request, "session_detail.html", context)


@login_required
def session_photos_upload(request, pk):
    session = get_object_or_404(ClassSession, pk=pk)
    viewer = request.user
    is_my_session = (
        viewer == session.klass.main_teacher
        or viewer == session.teacher_override
        or session.assistants.filter(id=viewer.id).exists()
        or session.klass.assistants.filter(id=viewer.id).exists()
    )
    if not (viewer.has_perm("class_sessions.change_classsession") or is_my_session):
        raise PermissionDenied
    if request.method != "POST":
        return HttpResponseBadRequest("Phương thức không hợp lệ")

    files = request.FILES.getlist("images")
    if not files:
        return HttpResponseBadRequest("Vui lòng chọn ảnh.")

    for f in files:
        ClassSessionPhoto.objects.create(session=session, image=f, uploaded_by=viewer)

    redirect_url = reverse("class_sessions:session_detail", args=[pk])
    if request.GET:
        redirect_url = f"{redirect_url}?{request.GET.urlencode()}"

    if is_htmx_request(request):
        resp = HttpResponse(status=204)
        resp["HX-Redirect"] = redirect_url
        resp["HX-Trigger"] = json.dumps({
            "show-sweet-alert": {
                "icon": "success",
                "title": "Đã tải ảnh buổi học"
            }
        })
        return resp
    return redirect(redirect_url)


@login_required
@require_POST
def session_photo_delete(request, session_pk, photo_pk):
    session = get_object_or_404(ClassSession, pk=session_pk)
    photo = get_object_or_404(ClassSessionPhoto, pk=photo_pk, session=session)
    viewer = request.user
    is_my_session = (
        viewer == session.klass.main_teacher
        or viewer == session.teacher_override
        or session.assistants.filter(id=viewer.id).exists()
        or session.klass.assistants.filter(id=viewer.id).exists()
    )
    if not (viewer.has_perm("class_sessions.change_classsession") or is_my_session):
        raise PermissionDenied

    try:
        # Xóa file trên storage trước khi xóa record
        if photo.image:
            photo.image.delete(save=False)
    finally:
        photo.delete()
    redirect_url = reverse("class_sessions:session_detail", args=[session_pk])
    if request.GET:
        redirect_url = f"{redirect_url}?{request.GET.urlencode()}"

    if is_htmx_request(request):
        resp = HttpResponse(status=204)
        resp["HX-Redirect"] = redirect_url
        resp["HX-Trigger"] = json.dumps({
            "show-sweet-alert": {
                "icon": "success",
                "title": "Đã xóa ảnh"
            }
        })
        return resp
    return redirect(redirect_url)


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

    filter_applied = bool(request.GET.get("date")) or (teacher_id and viewer.has_perm("class_sessions.view_classsession"))
    filter_enabled = bool(teachers)

    context = {
        "sessions": sessions,
        "date": selected_date,
        "start": start_of_week,
        "end": end_of_week,
        "teacher": teacher,
        "teachers": teachers,
        "today": today,
        "filter_applied": filter_applied,
        "filter_enabled": filter_enabled,
    }
    if is_htmx_request(request):
        return render(request, "_schedule_table.html", context)
    return render(request, "teaching_schedule.html", context)


@login_required
def teaching_schedule_my_view(request):
    """
    View dành cho giáo viên/trợ giảng: chỉ xem lịch của mình, không bộ lọc giáo viên.
    """
    today = date.today()
    try:
        selected_date = date.fromisoformat(request.GET.get("date")) if request.GET.get("date") else today
    except ValueError:
        selected_date = today
    start_of_week = selected_date - timedelta(days=selected_date.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    viewer = request.user
    base = ClassSession.objects.select_related(
        "klass", "klass__subject", "klass__center", "klass__main_teacher", "lesson"
    ).prefetch_related("assistants").filter(date__isnull=False, date__range=(start_of_week, end_of_week))

    sessions = base.filter(
        Q(teacher_override=viewer)
        | Q(klass__main_teacher=viewer)
        | Q(assistants=viewer)
        | Q(klass__assistants=viewer)
    ).order_by("date", "start_time", "klass__name").distinct()

    context = {
        "sessions": sessions,
        "date": selected_date,
        "start": start_of_week,
        "end": end_of_week,
        "teacher": viewer,
        "teachers": None,
        "today": today,
        "filter_applied": False,
        "filter_enabled": False,
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

    filter_applied = bool(teacher_id)

    context = {
        "classes": qs,
        "teacher": teacher,
        "teachers": teachers,
        "filter_applied": filter_applied,
    }
    if is_htmx_request(request):
        return render(request, "_teaching_classes_table.html", context)
    return render(request, "teaching_classes.html", context)


@login_required
def teaching_classes_my_view(request):
    """
    View dành riêng cho giáo viên/trợ giảng: chỉ thấy lớp của chính mình,
    không cho chọn giáo viên khác.
    """
    from apps.classes.models import Class

    viewer = request.user
    qs = (
        Class.objects.select_related("center", "subject", "main_teacher")
        .prefetch_related("assistants")
        .filter(
            Q(main_teacher=viewer) | Q(assistants=viewer),
            status__in=["PLANNED", "ONGOING"],
        )
        .order_by("center__name", "name")
        .distinct()
    )

    context = {
        "classes": qs,
        "teacher": viewer,
        "teachers": None,
        "filter_applied": False,
    }
    if is_htmx_request(request):
        return render(request, "_teaching_classes_table.html", context)
    return render(request, "teaching_classes.html", context)
