import json
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from .models import SavedFilter
from .forms import SavedFilterForm
from django.utils.http import urlencode
from django.db.models import Q

def is_htmx_request(request):
    return request.headers.get("HX-Request") == "true"

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
        return render(
            request, 
            "_save_filter_form.html", 
            {"form": form}, 
            status=422
        )

    # GET request: Hiển thị form
    model_name = request.GET.get("model_name", "")
    query_params = {}
    
    # Lấy các tham số filter từ query string của request
    for key, value in request.GET.items():
        if key not in ["page", "model_name", "_"]:
            # Bỏ qua các list rỗng (thường do form filter gửi lên)
            if value or (isinstance(value, list) and any(v for v in value)):
                query_params[key] = request.GET.getlist(key) if len(request.GET.getlist(key)) > 1 else value

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
    
    my_filters = saved.filter(user=request.user)
    public_filters = saved.filter(is_public=True).exclude(user=request.user)
    
    context = {
        "my_filters": my_filters,
        "public_filters": public_filters,
        "model_name": model_name,
        "target_id": request.GET.get("target_id"), # Lấy target_id từ request
    }

    # Chuyển đổi current_query_params từ string (vd: 'subject=4') thành JSON string (vd: '{"subject": "4"}')
    # để so sánh với dữ liệu trong DB
    query_dict = {k: v for k, v in request.GET.items() if k not in ['target_id', 'current_query_params']}
    if query_dict:
        context["current_query_params"] = json.dumps(query_dict)

    # Render một template fragment mới CHỈ chứa các <li>
    return render(request, "_saved_filters_list.html", context)