from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Count, Q
from datetime import date

# Domain models
try:
    from apps.centers.models import Center, Room
except Exception:
    Center = None
    Room = None
try:
    from apps.classes.models import Class
except Exception:
    Class = None
# Thêm import cho ClassSession
try:
    from apps.class_sessions.models import ClassSession
except Exception:
    ClassSession = None
try:
    from apps.students.models import StudentProduct
except Exception:
    StudentProduct = None
try:
    from apps.parents.services import build_parent_children_snapshot
except Exception:
    build_parent_children_snapshot = None
   
def home(request):
    home_products = []
    home_page_obj = None
    home_paginator = None
    if StudentProduct:
        products_qs = StudentProduct.objects.select_related(
            "student",
            "session",
            "session__klass",
            "session__klass__subject",
        ).order_by("-created_at")
        from django.core.paginator import Paginator, EmptyPage

        paginator = Paginator(products_qs, 3)
        page_number = request.GET.get("products_page", 1)
        try:
            home_page_obj = paginator.page(page_number)
        except EmptyPage:
            home_page_obj = paginator.page(1)
        home_paginator = paginator
        home_products = home_page_obj.object_list

    return render(
        request,
        "home.html",
        {
            "home_products": home_products,
            "home_page_obj": home_page_obj,
            "home_paginator": home_paginator,
        },
    )




@login_required
def dashboard(request):
    User = get_user_model()

    user = request.user
    role = getattr(user, "role", "").upper()
    in_group = lambda name: user.groups.filter(name=name).exists()

    is_admin = user.is_superuser or role == "ADMIN" or in_group("Admin") or in_group("ADMIN")
    is_center_manager = role == "CENTER_MANAGER" or in_group("Center Manager") or in_group("CENTER_MANAGER")
    is_teacher = role == "TEACHER" or in_group("Teacher") or in_group("TEACHER")
    is_assistant = role == "ASSISTANT" or in_group("Assistant") or in_group("ASSISTANT")
    is_parent = role == "PARENT" or in_group("Parent") or in_group("PARENT")


    context = {"dashboard_role": "user"}

    if is_admin:
        context.update(
            {
                "dashboard_role": "admin",
                "centers_count": Center.objects.count() if Center else None,
                "rooms_count": Room.objects.count() if Room else None,
                "users_count": User.objects.count(),
                "groups_count": Group.objects.count(),
                "classes_count": Class.objects.count() if Class else None,
            }
        )
    elif is_center_manager:
        center = getattr(user, "center", None)
        # Counts scoped to manager's center (if linked)
        if center and Center and Room:
            teachers_q = Q(role="TEACHER") | Q(groups__name__in=["Teacher", "TEACHER"])
            students_q = Q(role="STUDENT") | Q(groups__name__in=["Student", "STUDENT"]) 

            context.update(
                {
                    "dashboard_role": "center_manager",
                    "center": center,
                    "cm_users_count": User.objects.filter(center=center).distinct().count(),
                    "cm_rooms_count": Room.objects.filter(center=center).count(),
                    "cm_classes_count": (Class.objects.filter(center=center).count() if Class else None),
                    "cm_teachers_count": User.objects.filter(center=center).filter(teachers_q).distinct().count(),
                    "cm_students_count": User.objects.filter(center=center).filter(students_q).distinct().count(),
                }
            )
        else:
            context.update({"dashboard_role": "center_manager"})
    
    elif is_parent and build_parent_children_snapshot:
        snapshot = build_parent_children_snapshot(user)
        context.update(
            {
                "dashboard_role": "parent",
                "parent_summary_metrics": snapshot["summary_metrics"],
                "parent_recent_updates": snapshot["recent_updates"],
                "parent_children_cards": snapshot["children_data"][:3],
                "parent_has_children": snapshot["has_children"],
            }
        )
    elif (is_teacher or is_assistant) and Class and ClassSession:
        today = date.today()
        # Lấy các buổi dạy sắp tới (planned, từ hôm nay)
        upcoming_sessions_qs = ClassSession.objects.filter(
            (Q(klass__main_teacher=user) | Q(klass__assistants=user) | Q(teacher_override=user) | Q(assistants=user)),
            date__gte=today,
            status="PLANNED"
        ).select_related('klass', 'lesson').order_by('date', 'start_time')
        
        # Lấy các lớp đang dạy (ongoing)
        teaching_classes_qs = Class.objects.filter(
            Q(main_teacher=user) | Q(assistants=user),
            status="ONGOING"
        ).distinct()

        context.update({
            "dashboard_role": "teacher_assistant",
            "teaching_classes_count": teaching_classes_qs.count(),
            "upcoming_sessions_count": upcoming_sessions_qs.count(),
            "upcoming_sessions_list": upcoming_sessions_qs[:5] # Chỉ lấy 5 buổi gần nhất
        })


    return render(request, "dashboard/index.html", context)
