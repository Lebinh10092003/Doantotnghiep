import json
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q
from .models import Center
from .forms import CenterForm
# Create your views here.
def is_htmx_request(request):
    return (
        request.headers.get("HX-Request") == "true"
        or request.META.get("HTTP_HX_REQUEST") == "true"
        or bool(getattr(request, "htmx", False))
    )
def _filter_centers_queryset(request):
    qs = Center.objects.all()
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")

    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(code__icontains=q) |
            Q(address__icontains=q)
        )
    
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)

    return qs
# Quanr lý trung tâm 
@login_required
@permission_required("centers.view_center", raise_exception=True)
def centers_manage(request):
    qs = _filter_centers_queryset(request)
    
    # Params for sorting and pagination
    sort_by = request.GET.get("sort_by", "code")
    try:
        per_page = int(request.GET.get("per_page", 10))
    except (TypeError, ValueError):
        per_page = 10
    try:
        page = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page = 1

    # Ordering
    valid_sort_fields = ["name", "-name", "code", "-code"]
    if sort_by in valid_sort_fields:
        qs = qs.order_by(sort_by)
    else:
        qs = qs.order_by("code")

    # Pagination
    paginator = Paginator(qs, per_page)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(1)

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "q": request.GET.get("q", "").strip(),
        "status": request.GET.get("status", ""),
        "per_page": per_page,
        "sort_by": sort_by,
    }

    if is_htmx_request(request):
        return render(request, "_centers_table.html", context)

    return render(request, "manage_centers.html", context)

# Create Center
@login_required
@permission_required("centers.add_center", raise_exception=True)
def center_create_view(request):
    if request.method == 'POST':
        form = CenterForm(request.POST, request.FILES)
        if form.is_valid():
            center = form.save()
            response = HttpResponse(status=200)
            response['HX-Trigger'] = json.dumps({
                "reloadCentersTable": True,
                "closeCenterModal": True,
                "show-sweet-alert": {
                    "icon": "success",
                    "title": f"Tạo Trung tâm '{center.name}' thành công!"
                }
            })
            return response
        else:
            # Nếu form không hợp lệ, render lại form với lỗi
            return render(request, '_center_form.html', {'form': form, 'is_create': True}, status=422)
    else:
        form = CenterForm()

    context = {
        'form': form,
        'is_create': True
    }
    return render(request, '_center_form.html', context)

# 
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
                "reloadCentersTable": True,
                "closeCenterModal": True,
                "show-sweet-alert": {
                    "icon": "success",
                    "title": f"Cập nhật Trung tâm '{center.name}' thành công!"
                }
            })
            return response
        else:
            # Nếu form không hợp lệ, render lại form với lỗi
            return render(request, '_center_form.html', {'form': form, 'center': center}, status=422)
    else:
        form = CenterForm(instance=center)

    context = {
        'form': form,
        'center': center,
        'is_create': False
    }
    return render(request, '_center_form.html', context)

# Delete Center
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
                centers_to_delete_qs.delete()

            if deleted_count > 0:
                if deleted_count == 1:
                    alert = {"icon": "success", "title": f"Đã xóa Trung tâm '{deleted_names[0]}' thành công."}
                else:
                    deleted_list_str = ", ".join([f"'{name}'" for name in deleted_names])
                    alert = {
                        "icon": "success", 
                        "title": f"Đã xóa {deleted_count} Trung tâm thành công.",
                        "text": f"Các trung tâm đã xóa: {deleted_list_str}"
                    }
            else:
                alert = {"icon": "info", "title": "Không có Trung tâm nào được xóa."}

        except Exception as e:
            alert = {"icon": "error", "title": "Lỗi máy chủ", "text": str(e)}

    response = HttpResponse(status=200)
    response['HX-Trigger'] = json.dumps({
        "reloadCentersTable": True,
        "closeCenterModal": True, 
        "show-sweet-alert": alert
    })
    return response