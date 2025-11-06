from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db.models import Count, Q

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
   
def home(request):
    return render(request, "home.html")




@login_required
def dashboard(request):
    User = get_user_model()

    user = request.user
    role = getattr(user, "role", "").upper()
    in_group = lambda name: user.groups.filter(name=name).exists()

    is_admin = user.is_superuser or role == "ADMIN" or in_group("Admin") or in_group("ADMIN")
    is_center_manager = role == "CENTER_MANAGER" or in_group("Center Manager") or in_group("CENTER_MANAGER")

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

    return render(request, "dashboard/index.html", context)
