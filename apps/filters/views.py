import json
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from .models import SavedFilter
from .forms import SavedFilterForm
from django.utils.http import urlencode

def is_htmx_request(request):
    return request.headers.get("HX-Request") == "true"

@login_required
def save_filter_view(request):
    """
    Xử lý lưu bộ lọc.
    GET: Trả về form modal.
    POST: Lưu bộ lọc.
    """
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
    """
    Xóa một bộ lọc đã lưu (chỉ chủ sở hữu mới được xóa).
    """
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