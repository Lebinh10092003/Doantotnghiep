import json
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q
from apps.filters.models import SavedFilter
from apps.filters.utils import (
    build_filter_badges,
    determine_active_filter_name,
)
from .models import Center, Room
from .forms import CenterForm, RoomForm
from .filters import CenterFilter
from apps.common.utils.forms import form_errors_as_text
from apps.common.utils.http import is_htmx_request

# Lọc queryset phòng học dựa trên tham số truy vấn
def _filter_rooms_queryset(request):
    qs = Room.objects.select_related("center").all()
    q = request.GET.get("q", "").strip()
    center_id = request.GET.get("center", "").strip()

    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(note__icontains=q)
            | Q(center__name__icontains=q)
            | Q(center__code__icontains=q)
        )
    if center_id:
        try:
            qs = qs.filter(center_id=int(center_id))
        except (TypeError, ValueError):
            pass

# Quản lý Trung tâm
@login_required
@permission_required("centers.view_center", raise_exception=True)
def centers_manage(request):
    center_filter = CenterFilter(request.GET, queryset=Center.objects.all())
    qs = center_filter.qs

    if center_filter.form.is_bound:
        center_filter.form.is_valid()
        group_by = center_filter.form.cleaned_data.get("group_by", "") or ""
    else:
        group_by = request.GET.get("group_by", "") or ""

    sort_by = request.GET.get("sort_by", "code")
    valid_sort_fields = ["name", "-name", "code", "-code"]
    if sort_by in valid_sort_fields:
        qs = qs.order_by(sort_by)
    else:
        qs = qs.order_by("code")

    if group_by == "status":
        qs = qs.order_by("-is_active", "name")

    try:
        per_page = int(request.GET.get("per_page", 10))
    except (TypeError, ValueError):
        per_page = 10
    try:
        page = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page = 1

    paginator = Paginator(qs, per_page)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(1)

    saved_filters = SavedFilter.objects.filter(model_name="Center").filter(
        Q(user=request.user) | Q(is_public=True)
    ).distinct()

    active_filter_name = determine_active_filter_name(request, saved_filters)
    active_filter_badges = build_filter_badges(center_filter)

    query_params = request.GET.copy()
    query_params._mutable = True
    query_params.pop("page", None)

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
        "sort_by": sort_by,
        "filter": center_filter,
        "model_name": "Center",
        "active_filter_name": active_filter_name,
        "active_filter_badges": active_filter_badges,
        "current_query_params": query_params.urlencode(),
        "group_by": group_by,
    }

    if is_htmx_request(request):
        return render(request, "_center_filterable_content.html", context)

    return render(request, "manage_centers.html", context)

# Chi tiết Trung tâm
@login_required
@permission_required("centers.view_center", raise_exception=True)
def center_detail_view(request, center_id: int):
    center = get_object_or_404(Center, id=center_id)

    qs = center.rooms.all()
    q = request.GET.get("q", "").strip()
    sort_by = request.GET.get("sort_by", "name")
    try:
        per_page = int(request.GET.get("per_page", 10))
    except (TypeError, ValueError):
        per_page = 10
    try:
        page = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page = 1

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(note__icontains=q))

    valid_sort_fields = ["name", "-name"]
    if sort_by in valid_sort_fields:
        qs = qs.order_by(sort_by)
    else:
        qs = qs.order_by("name")

    paginator = Paginator(qs, per_page)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(1)

    context = {
        "center": center,
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "per_page": per_page,
        "sort_by": sort_by,
    }

    if is_htmx_request(request):
        # If requesting rooms table fragment (from detail page filters/pagination)
        if request.GET.get("fragment") == "rooms_table":
            return render(request, "_center_rooms_table.html", context)
        # Default for HTMX is the modal content, even if 'as' param is missing
        return render(request, "_center_detail_modal.html", context)

    return render(request, "center_detail.html", context)


# Quản lý Phòng học
@login_required
@permission_required("centers.view_room", raise_exception=True)
def rooms_manage(request):
    qs = _filter_rooms_queryset(request)

    sort_by = request.GET.get("sort_by", "center__name")
    try:
        per_page = int(request.GET.get("per_page", 10))
    except (TypeError, ValueError):
        per_page = 10
    try:
        page = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page = 1

    valid_sort_fields = [
        "name",
        "-name",
        "center__name",
        "-center__name",
        "center__code",
        "-center__code",
    ]
    if sort_by in valid_sort_fields:
        qs = qs.order_by(sort_by)
    else:
        qs = qs.order_by("center__name", "name")

    paginator = Paginator(qs, per_page)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(1)

    centers = Center.objects.order_by("name").all()

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "q": request.GET.get("q", "").strip(),
        "per_page": per_page,
        "sort_by": sort_by,
        "centers": centers,
        "selected_center": request.GET.get("center", ""),
    }

    if is_htmx_request(request):
        return render(request, "_rooms_table.html", context)

    return render(request, "manage_rooms.html", context)

# Tạo Phòng học
@login_required
@permission_required("centers.add_room", raise_exception=True)
def room_create_view(request):
    if request.method == "POST":
        form = RoomForm(request.POST)
        if form.is_valid():
            room = form.save()
            response = HttpResponse(status=204)
            response["HX-Trigger"] = json.dumps(
                {
                    "reload-rooms-table": True,
                    "reload-centers-table": True,
                    "closeRoomModal": True,
                    "show-sweet-alert": {
                        "icon": "success",
                        "title": f"Tạo Phòng học '{room.name}' thành công!",
                    },
                }
            )
            return response
        response = render(
            request,
            "_room_form.html",
            {"form": form, "is_create": True},
            status=422,
        )
        if is_htmx_request(request):
            response["HX-Trigger"] = json.dumps({
                "show-sweet-alert": {
                    "icon": "error",
                    "title": "Không thể tạo Phòng học",
                    "text": form_errors_as_text(form),
                }
            })
        return response
    else:
        initial = {}
        center_id = request.GET.get("center")
        if center_id:
            try:
                initial["center"] = int(center_id)
            except (TypeError, ValueError):
                pass
        form = RoomForm(initial=initial)

    return render(request, "_room_form.html", {"form": form, "is_create": True})

# Chỉnh sửa Phòng học
@login_required
@permission_required("centers.change_room", raise_exception=True)
def room_edit_view(request, room_id: int):
    room = get_object_or_404(Room, id=room_id)
    if request.method == "POST":
        form = RoomForm(request.POST, instance=room)
        if form.is_valid():
            room = form.save()
            # Áp dụng Pattern 1: Đóng modal và tải lại bảng
            response = HttpResponse(status=204)
            response["HX-Trigger"] = json.dumps(
                {
                    "closeRoomModal": True, # Lệnh đóng modal đang mở
                    "reload-rooms-table": True, # Lệnh tải lại bảng phòng học (trên trang chi tiết trung tâm)
                    "show-sweet-alert": {
                        "icon": "success",
                        "title": f"Cập nhật Phòng học '{room.name}' thành công!",
                    },
                }
            )
            return response
        response = render(
            request, "_room_form.html", {"form": form, "room": room}, status=422
        )
        if is_htmx_request(request):
            response["HX-Trigger"] = json.dumps({
                "show-sweet-alert": {
                    "icon": "error",
                    "title": "Không thể cập nhật Phòng học",
                    "text": form_errors_as_text(form),
                }
            })
        return response
    else:
        form = RoomForm(instance=room)

    return render(request, "_room_form.html", {"form": form, "room": room})

# Xóa Phòng học
@require_POST
@login_required
@permission_required("centers.delete_room", raise_exception=True)
def room_delete_view(request):
    room_ids = request.POST.getlist("room_ids[]") or request.POST.getlist("room_ids")
    unique_ids = list(set(room_ids))
    alert = {}

    if not unique_ids:
        alert = {"icon": "info", "title": "Không có Phòng học nào được chọn."}
    else:
        try:
            ids_int = [int(rid) for rid in unique_ids]
            qs = Room.objects.filter(id__in=ids_int)
            deleted_names = [str(r) for r in qs]
            deleted_count = len(deleted_names)

            if deleted_count > 0:
                qs.delete()

            if deleted_count > 0:
                if deleted_count == 1:
                    alert = {
                        "icon": "success",
                        "title": f"Đã xóa Phòng học '{deleted_names[0]}' thành công.",
                    }
                else:
                    deleted_list_str = ", ".join([f"'{name}'" for name in deleted_names])
                    alert = {
                        "icon": "success",
                        "title": f"Đã xóa {deleted_count} Phòng học thành công.",
                        "text": f"Các phòng đã xóa: {deleted_list_str}",
                    }
            else:
                alert = {"icon": "info", "title": "Không có Phòng học nào bị xóa."}
        except Exception as e:
            alert = {"icon": "error", "title": "Lỗi hệ thống", "text": str(e)}

    response = HttpResponse(status=200)
    response["HX-Trigger"] = json.dumps(
        {"reload-rooms-table": True, "closeRoomModal": True, "show-sweet-alert": alert}
    )
    return response

# Tạo Trung tâm
@login_required
@permission_required("centers.add_center", raise_exception=True)
def center_create_view(request):
    if request.method == 'POST':
        form = CenterForm(request.POST, request.FILES)
        if form.is_valid():
            center = form.save()
            response = HttpResponse(status=200)
            response['HX-Trigger'] = json.dumps({
                "reload-centers-table": True,
                "closeCenterModal": True,
                "show-sweet-alert": {
                    "icon": "success",
                    "title": f"Tạo Trung tâm '{center.name}' thành công!"
                }
            })
            return response
        else:
            response = render(request, '_center_form.html', {'form': form, 'is_create': True}, status=422)
            if is_htmx_request(request):
                response['HX-Trigger'] = json.dumps({
                    "show-sweet-alert": {
                        "icon": "error",
                        "title": "Không thể tạo Trung tâm",
                        "text": form_errors_as_text(form),
                    }
                })
            return response
    else:
        form = CenterForm()

    context = {
        'form': form,
        'is_create': True
    }
    return render(request, '_center_form.html', context)

# Chỉnh sửa Trung tâm
@login_required
@permission_required("centers.change_center", raise_exception=True)
def center_edit_view(request, center_id):
    center = get_object_or_404(Center, id=center_id)
    if request.method == 'POST':
        form = CenterForm(request.POST, request.FILES, instance=center)
        if form.is_valid():
            center = form.save()
            response = HttpResponse(status=200)
            response['HX-Trigger'] = json.dumps({
                "reload-centers-table": True,
                "closeCenterModal": True,
                "show-sweet-alert": {
                    "icon": "success",
                    "title": f"Cập nhật Trung tâm '{center.name}' thành công!"
                }
            })
            return response
        else:
            response = render(request, '_center_form.html', {'form': form, 'center': center, 'is_create': False}, status=422)
            if is_htmx_request(request):
                response['HX-Trigger'] = json.dumps({
                    "show-sweet-alert": {
                        "icon": "error",
                        "title": "Không thể cập nhật Trung tâm",
                        "text": form_errors_as_text(form),
                    }
                })
            return response
    else:
        form = CenterForm(instance=center)

    context = {
        'form': form,
        'center': center,
        'is_create': False
    }
    return render(request, '_center_form.html', context)

# Xóa Trung tâm
@require_POST
@login_required
@permission_required("centers.delete_center", raise_exception=True)
def center_delete_view(request):
    center_ids = request.POST.getlist('center_ids[]') or request.POST.getlist('center_ids')
    unique_center_ids = list(set(center_ids))
    alert = {} 

    if not unique_center_ids:
        alert = {"icon": "info", "title": "Không có Trung tâm nào được chọn."}
    else:
        try:
            center_ids_int = [int(gid) for gid in unique_center_ids]
            centers_to_delete_qs = Center.objects.filter(id__in=center_ids_int)
            deleted_names = [center.name for center in centers_to_delete_qs]
            deleted_count = len(deleted_names)

            if deleted_count > 0:
                centers_to_delete_qs.update(is_active=False)

            if deleted_count > 0:
                if deleted_count == 1:
                    alert = {"icon": "success", "title": f"Đã vô hiệu hóa Trung tâm '{deleted_names[0]}' thành công."}
                else:
                    deleted_list_str = ", ".join([f"'{name}'" for name in deleted_names])
                    alert = {
                        "icon": "success", 
                        "title": f"Đã vô hiệu hóa {deleted_count} Trung tâm thành công.",
                        "text": f"Các trung tâm đã vô hiệu hóa: {deleted_list_str}"
                    }
            else:
                alert = {"icon": "info", "title": "Không có Trung tâm nào được xóa."}

        except Exception as e:
            alert = {"icon": "error", "title": "Lỗi máy chủ", "text": str(e)}

    response = HttpResponse(status=200)
    response['HX-Trigger'] = json.dumps({
        "reload-centers-table": True,
        "closeCenterModal": True, 
        "show-sweet-alert": alert
    })
    return response
