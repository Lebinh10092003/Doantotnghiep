import json
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from .models import SavedFilter
from .forms import SavedFilterForm
from django.utils.http import urlencode
from django.db.models import Q
from .utils import resolve_dynamic_params, serialize_query_params
from apps.common.utils.forms import form_errors_as_text
from apps.common.utils.http import is_htmx_request

@login_required
def save_filter_view(request):
    if not is_htmx_request(request):
        return HttpResponse("Yêu cầu không hợp lệ", status=400)

    if request.method == "POST":
        form = SavedFilterForm(request.POST)
        if form.is_valid():
            filter_instance = form.save(commit=False)
            filter_instance.user = request.user
            filter_instance.save()
            
            # Gửi trigger để đóng modal và thông báo
            response = HttpResponse(status=204) # 204 No Content
            response["HX-Trigger"] = json.dumps({
                "closeFilterModal": True,
                "show-sweet-alert": {
                    "icon": "success",
                    "title": f"Đã lưu bộ lọc '{filter_instance.name}'!"
                },
                # Trigger để tải lại danh sách bộ lọc
                f"reload-saved-filters-{filter_instance.model_name}": True,
            })
            return response
        
        # Form không hợp lệ, trả lại form với lỗi
        response = render(
            request, 
            "_save_filter_form.html", 
            {"form": form}, 
            status=422
        )
        response["HX-Trigger"] = json.dumps({
            "show-sweet-alert": {
                "icon": "error",
                "title": "Không thể lưu bộ lọc",
                "text": form_errors_as_text(form),
            }
        })
        return response

    # GET request: Hiển thị form
    model_name = request.GET.get("model_name", "")
    query_params = {}
    
    # === SỬA ĐỔI BẮT ĐẦU: Sử dụng .lists() để lấy query params ===
    # Lọc ra các tham số không cần thiết
    excluded_keys = ["page", "model_name", "_", "hx-request", "hx-target", "hx-current-path", "hx-trigger"]
    
    for key, value_list in request.GET.lists():
        if key not in excluded_keys:
            # Bỏ qua các list rỗng
            if value_list and any(v for v in value_list):
                # Nếu chỉ có 1 giá trị, lưu dạng string
                if len(value_list) == 1:
                    query_params[key] = value_list[0]
                # Nếu có nhiều giá trị, lưu cả list
                else:
                    query_params[key] = value_list
    # === SỬA ĐỔI KẾT THÚC ===

    form = SavedFilterForm(initial={
        "model_name": model_name,
        "query_params": json.dumps(query_params) # Lưu query params dưới dạng JSON
    })
    
    context = {
        "form": form,
        "query_params_str": urlencode(query_params, doseq=True)
    }
    return render(request, "_save_filter_form.html", context)

@login_required
@require_POST
def delete_filter_view(request, pk):
    if not is_htmx_request(request):
        return HttpResponse("Yêu cầu không hợp lệ", status=400)

    filter_instance = get_object_or_404(SavedFilter, pk=pk, user=request.user)
    model_name = filter_instance.model_name
    filter_name = filter_instance.name
    filter_instance.delete()

    response = HttpResponse(status=204) # 204 No Content
    response["HX-Trigger"] = json.dumps({
        "show-sweet-alert": {
            "icon": "success",
            "title": f"Đã xóa bộ lọc '{filter_name}'"
        },
        f"reload-saved-filters-{model_name}": True,
    })
    return response

@login_required
@require_GET # Chỉ cho phép request GET
def load_saved_filters_view(request, model_name: str):
    if not is_htmx_request(request):
        return HttpResponse("Yêu cầu không hợp lệ", status=400)
    
    # Lấy các bộ lọc giống như logic trong view 
    saved = SavedFilter.objects.filter(model_name=model_name).filter(
        Q(user=request.user) | Q(is_public=True)
    ).distinct()
    
    my_filters = list(saved.filter(user=request.user))
    public_filters = list(saved.filter(is_public=True).exclude(user=request.user))

    def _attach_resolved_metadata(filters):
        for sf in filters:
            resolved = resolve_dynamic_params(sf.query_params)
            sf.resolved_query_params = resolved
            sf.resolved_query_string = serialize_query_params(resolved)

    _attach_resolved_metadata(my_filters)
    _attach_resolved_metadata(public_filters)
    
    context = {
        "my_filters": my_filters,
        "public_filters": public_filters,
        "model_name": model_name,
        "target_id": request.GET.get("target_id"), # Lấy target_id từ request
        "origin_path": request.GET.get("origin_path", "/"), # Lấy đường dẫn gốc
    }
    # Lọc ra các tham số không cần thiết
    excluded_keys = ['target_id', 'current_query_params', 'origin_path', 'page', '_', 'hx-request', 'hx-target', 'hx-current-path', 'hx-trigger']
    
    query_dict = {}
    for key, value_list in request.GET.lists():
        if key not in excluded_keys:
            if value_list and any(v for v in value_list):
                if len(value_list) == 1:
                    query_dict[key] = value_list[0]
                else:
                    query_dict[key] = value_list
    
    if query_dict:
        context["current_query_params"] = query_dict
    # Render một template fragment mới CHỈ chứa các <li>
    return render(request, "_saved_filters_list.html", context)