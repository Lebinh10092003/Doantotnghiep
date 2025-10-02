import json
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.shortcuts import render, redirect

User = get_user_model()

from datetime import timedelta
import json

from django.http import HttpResponse
from django.contrib.auth import authenticate, login, get_user_model
from django.shortcuts import render, redirect
from django.views.decorators.csrf import ensure_csrf_cookie

User = get_user_model()

@ensure_csrf_cookie
def login_view(request):
    if request.method == "POST":
        login_id = request.POST.get("phone", "").strip()
        password = request.POST.get("password", "")
        remember = request.POST.get("remember")

        # Tìm user theo phone
        user = User.objects.filter(phone=login_id).first()
        if not user:
            if request.headers.get("HX-Request"):
                resp = HttpResponse("", status=400)
                resp["HX-Trigger"] = json.dumps({
                    "modal": {"icon": "error", "title": "Số điện thoại không tồn tại"}
                })
                return resp
            return redirect("accounts:login")

        # Kiểm tra mật khẩu
        auth_user = authenticate(request, username=user.username, password=password)
        if not auth_user:
            if request.headers.get("HX-Request"):
                resp = HttpResponse("", status=400)
                resp["HX-Trigger"] = json.dumps({
                    "modal": {"icon": "error", "title": "Mật khẩu không đúng"}
                })
                return resp
            return redirect("accounts:login")

        # Đăng nhập
        login(request, auth_user)


        # Ghi nhớ đăng nhập
        if remember == "on":
            request.session.set_expiry(timedelta(days=14))  # giữ 14 ngày
        else:
            request.session.set_expiry(0)  # hết khi đóng browser

        # Nếu request HTMX: trả modal + redirect
        if request.headers.get("HX-Request"):
            resp = HttpResponse("")
            resp["HX-Trigger"] = json.dumps({
                "modal": {
                    "icon": "success",
                    "title": "Đăng nhập thành công!",
                    "redirect": "/"   # redirect sau khi modal đóng
                }
            })
            return resp

        # Nếu request thường: redirect về home
        return redirect("common:home")

    # GET: render form login
    return render(request, "login.html")

@require_POST
def logout_view(request):
    logout(request)
    if request.headers.get("HX-Request"):
        resp = HttpResponse("")
        resp["HX-Trigger"] = json.dumps({
            "modal": {
                "icon": "success",
                "title": "Đăng xuất thành công!",
                "redirect": "/"   
            }
        })
        return resp
    return redirect("common:home")
