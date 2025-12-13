import json
from collections import OrderedDict, defaultdict
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import (
    REDIRECT_FIELD_NAME,
    authenticate,
    get_user_model,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.tokens import default_token_generator
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Count, ProtectedError, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils.dateparse import parse_date
from django.utils.encoding import force_str
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_decode
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from tablib import Dataset
from tablib.exceptions import TablibException

try:
    from openpyxl.utils.exceptions import InvalidFileException  
except ImportError:  
    InvalidFileException = Exception  

from apps.centers.models import Center
from apps.classes.models import Class
from apps.common.utils.forms import form_errors_as_text
from apps.common.utils.http import is_htmx_request
from apps.filters.models import SavedFilter
from apps.filters.utils import build_filter_badges, determine_active_filter_name
from apps.rewards.models import PointAccount, RewardTransaction

from .filters import UserFilter
from .forms import (
    AdminUserCreateForm,
    AdminUserUpdateForm,
    ForgotPasswordForm,
    ImportUserForm,
    SimpleGroupForm,
    UserPasswordChangeForm,
    UserProfileUpdateForm,
    UserSetPasswordForm,
)
from .models import ParentStudentRelation
from .resources import UserResource
from .services import send_password_reset_email
User = get_user_model()
PASSWORD_RESET_RATE_LIMIT = getattr(settings, "PASSWORD_RESET_RATE_LIMIT", 5)
PASSWORD_RESET_RATE_WINDOW = getattr(settings, "PASSWORD_RESET_RATE_WINDOW", 300)


# Hỗ trợ giới hạn tần suất yêu cầu đặt lại mật khẩu
def _password_reset_rate_key(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    client_ip = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "unknown")
    return f"pwd-reset-rate:{client_ip}"

# Kiểm tra xem yêu cầu đặt lại mật khẩu có bị giới hạn tần suất không
def _is_password_reset_rate_limited(request) -> bool:
    return cache.get(_password_reset_rate_key(request), 0) >= PASSWORD_RESET_RATE_LIMIT

# Tăng số lần yêu cầu đặt lại mật khẩu
def _increment_password_reset_rate(request):
    key = _password_reset_rate_key(request)
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, PASSWORD_RESET_RATE_WINDOW)

# Phản hồi khi bị giới hạn tần suất
def _rate_limit_response(request):
    alert = {
        "icon": "warning",
        "title": "Thao tác quá nhanh",
        "text": "Vui lòng thử lại sau ít phút để bảo vệ tài khoản của bạn.",
    }
    if is_htmx_request(request):
        resp = HttpResponse("", status=429)
        resp["HX-Trigger"] = json.dumps({"show-sweet-alert": alert})
        return resp
    return render(
        request,
        "resetpassword/password_reset_form.html",
        {"form": ForgotPasswordForm(), "rate_limited": True, "alert": alert},
        status=429,
    )

# Phản hồi thành công sau khi yêu cầu đặt lại mật khẩu
def _password_reset_success_response(request):
    alert = {
        "icon": "success",
        "title": "Nếu email tồn tại chúng tôi đã gửi hướng dẫn",
        "text": "Vui lòng kiểm tra hộp thư và làm theo hướng dẫn để đặt lại mật khẩu.",
    }
    if is_htmx_request(request):
        resp = HttpResponse("", status=200)
        resp["HX-Trigger"] = json.dumps({"show-sweet-alert": alert})
        return resp
    return redirect("accounts:password_reset_done")


def _resolve_user_from_uid(uidb64):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        return User.objects.get(pk=uid, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None
# Định nghĩa các nhóm không được phép xóa
PROTECTED_GROUPS = [
    'Admin', 
    'Teacher', 
    'Student', 
    'Parent', 
    'Center Manager', 
    'Assistant',
    'Staff',
    'ADMIN',
    'TEACHER',
    'STUDENT',
    'PARENT',
    'CENTER_MANAGER',
    'ASSISTANT'
]
# Quy trình đăng nhập
@ensure_csrf_cookie
def login_view(request):
    if request.method == "POST":
        login_id = request.POST.get("phone", "").strip()
        password = request.POST.get("password", "")
        remember = request.POST.get("remember")

        if not login_id:
            if is_htmx_request(request):
                resp = HttpResponse("", status=400)
                resp["HX-Trigger"] = json.dumps(
                    {
                        "show-sweet-alert": {
                            "icon": "error",
                            "title": "Vui lòng nhập thông tin đăng nhập",
                        }
                    }
                )
                return resp
            return redirect("accounts:login")

        # Tìm user theo phone hoặc username hoặc email (fallback khi không có phone)
        user = User.objects.filter(
            Q(phone=login_id) | Q(username=login_id) | Q(email=login_id)
        ).first()
        if not user:
            if is_htmx_request(request):
                resp = HttpResponse("", status=400)
                resp["HX-Trigger"] = json.dumps({
                    "show-sweet-alert": {
                        "icon": "error",
                        "title": "Không tìm thấy tài khoản với thông tin này",
                    }
                })
                return resp
            return redirect("accounts:login")

        # Kiểm tra mật khẩu
        auth_user = authenticate(request, username=user.username, password=password)
        if not auth_user:
            if is_htmx_request(request):
                resp = HttpResponse("", status=400)
                resp["HX-Trigger"] = json.dumps({
                    "show-sweet-alert": {
                        "icon": "error", "title": "Mật khẩu không đúng"
                    }
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

        redirect_to = request.POST.get(REDIRECT_FIELD_NAME) or request.GET.get(REDIRECT_FIELD_NAME)
        if redirect_to and url_has_allowed_host_and_scheme(
            redirect_to,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            final_redirect = redirect_to
        else:
            final_redirect = resolve_url(settings.LOGIN_REDIRECT_URL)

        # Nếu request HTMX: trả modal + redirect
        if is_htmx_request(request):
            resp = HttpResponse("")
            resp["HX-Trigger"] = json.dumps({
                "show-sweet-alert": {
                    "icon": "success",
                    "title": "Đăng nhập thành công!",
                    "redirect": final_redirect   # redirect sau khi modal đóng
                }
            })
            return resp

        # Nếu request thường: redirect về home
        return redirect(final_redirect)

    # Với GET: hiển thị trang đăng nhập
    return render(request, "login.html")


# Quy trình đặt lại mật khẩu qua email
@ensure_csrf_cookie
def password_reset_request_view(request):
    if request.method == "POST":
        if _is_password_reset_rate_limited(request):
            return _rate_limit_response(request)

        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            user = form.get_user()
            if user and (user.preferred_email() or user.email):
                send_password_reset_email(user, request)
            _increment_password_reset_rate(request)
            return _password_reset_success_response(request)
    else:
        form = ForgotPasswordForm()

    return render(request, "resetpassword/password_reset_form.html", {"form": form})

# Xác nhận yêu cầu đặt lại mật khẩu đã gửi
def password_reset_done_view(request):
    return render(request, "resetpassword/password_reset_done.html")

# Xử lý đặt lại mật khẩu từ link email
@ensure_csrf_cookie
def password_reset_confirm_view(request, uidb64, token):
    user = _resolve_user_from_uid(uidb64)
    if not user or not default_token_generator.check_token(user, token):
        return render(
            request,
            "resetpassword/password_reset_confirm.html",
            {"validlink": False},
            status=400,
        )

    if request.method == "POST":
        form = UserSetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            if is_htmx_request(request):
                resp = HttpResponse("")
                resp["HX-Trigger"] = json.dumps(
                    {
                        "show-sweet-alert": {
                            "icon": "success",
                            "title": "Đặt lại mật khẩu thành công",
                            "redirect": resolve_url("accounts:password_reset_complete"),
                        }
                    }
                )
                return resp
            return redirect("accounts:password_reset_complete")
        if is_htmx_request(request):
            html = render_to_string(
                "resetpassword/_password_reset_confirm_form.html",
                {"form": form},
                request=request,
            )
            resp = HttpResponse(html, status=422)
            resp["HX-Trigger"] = json.dumps(
                {
                    "show-sweet-alert": {
                        "icon": "error",
                        "title": "Không thể cập nhật mật khẩu",
                        "text": form_errors_as_text(form),
                    }
                }
            )
            return resp
    else:
        form = UserSetPasswordForm(user)

    return render(
        request,
        "resetpassword/password_reset_confirm.html",
        {"form": form, "validlink": True},
    )

# Xác nhận hoàn tất đặt lại mật khẩu
def password_reset_complete_view(request):
    return render(request, "resetpassword/password_reset_complete.html")

# Đăng xuất
@require_POST
def logout_view(request):
    logout(request)
    if is_htmx_request(request):
        resp = HttpResponse("")
        resp["HX-Trigger"] = json.dumps({
            "show-sweet-alert": {
                "icon": "success",
                "title": "Đăng xuất thành công!",
                "redirect": "/"
            }
        })
        return resp
    return redirect("common:home")

# Kiểm tra quyền admin
def is_admin(user):
    return user.is_superuser or getattr(user, "role", None) == "ADMIN"
# Lọc queryset người dùng dựa trên tham số request
def _base_users_queryset(current_user):
    """Trả về queryset cơ bản phù hợp với quyền xem của người dùng."""
    is_parent = current_user.groups.filter(name="PARENT").exists()
    is_student = current_user.groups.filter(name="STUDENT").exists()

    if is_parent:
        children_ids = (
            ParentStudentRelation.objects.filter(parent=current_user)
            .values_list("student_id", flat=True)
        )
        qs = User.objects.filter(id__in=list(children_ids))
    elif is_student:
        qs = User.objects.filter(pk=current_user.pk)
    else:
        qs = User.objects.all()

    return qs.select_related("center").prefetch_related("groups").distinct()

# Lọc queryset người dùng với bộ lọc
def _filter_users_queryset(request, with_filter=False):
    base_qs = _base_users_queryset(request.user)
    user_filter = UserFilter(request.GET, queryset=base_qs)
    qs = user_filter.qs.select_related("center").prefetch_related("groups").distinct()
    if with_filter:
        return qs, user_filter
    return qs

# Quản lý người dùng
@login_required
@permission_required("accounts.view_user", raise_exception=True)
def manage_accounts(request):
    qs, user_filter = _filter_users_queryset(request, with_filter=True)

    # Xác định chế độ nhóm dựa vào dữ liệu bộ lọc
    if user_filter.form.is_bound:
        user_filter.form.is_valid()
        group_by = user_filter.form.cleaned_data.get("group_by", "") or ""
    else:
        group_by = request.GET.get("group_by", "") or ""

    if group_by == "role":
        qs = qs.order_by("groups__name", "last_name", "first_name").distinct()
    elif group_by == "center":
        qs = qs.order_by("center__name", "last_name", "first_name")
    else:
        qs = qs.order_by("last_name", "first_name")

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

    saved_filters = SavedFilter.objects.filter(model_name="User").filter(
        Q(user=request.user) | Q(is_public=True)
    ).distinct()

    active_filter_name = determine_active_filter_name(request, saved_filters)
    active_filter_badges = build_filter_badges(user_filter)

    query_params = request.GET.copy()
    query_params._mutable = True
    query_params.pop("page", None)

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
        "filter": user_filter,
        "model_name": "User",
        "active_filter_name": active_filter_name,
        "active_filter_badges": active_filter_badges,
        "current_query_params": query_params.urlencode(),
        "group_by": group_by,
    }

    if is_htmx_request(request):
        return render(request, "_account_filterable_content.html", context)

    return render(request, "manage_accounts.html", context)

# Tạo người dùng mới
@login_required
@permission_required("accounts.add_user", raise_exception=True)
def user_create_view(request):
    if request.method == "GET":
        form = AdminUserCreateForm()
        return render(request, "_add_user_form.html", {"form": form})

    form = AdminUserCreateForm(request.POST, request.FILES)
    if form.is_valid():
        user = form.save()
        # GIỐNG change_password_view: dùng show-sweet-alert + đóng modal + reload bảng
        resp = HttpResponse(status=200)
        resp["HX-Trigger"] = json.dumps({
            "reload-accounts-table": True,
            "closeUserModal": True,
            "show-sweet-alert": {
                "icon": "success",
                "title": "Thành công",
                "text": f"Đã tạo tài khoản: {user.username}",
                "timer": 1500,
                "showConfirmButton": False
            }
        })
        return resp

    # LỖI: trả 400 + form có lỗi + thông báo lỗi qua show-sweet-alert (dùng text)
    html = render_to_string("_add_user_form.html", {"form": form}, request=request)
    resp = HttpResponse(html, status=400)
    resp["HX-Trigger"] = json.dumps({
        "show-sweet-alert": {
            "icon": "error",
            "title": "Không thể tạo tài khoản",
            "text": form_errors_as_text(form),
            "showConfirmButton": True
        }
    })
    return resp


# Vô hiệu hóa người dùng
@require_POST
@login_required
@permission_required("accounts.delete_user", raise_exception=True)
def user_delete_view(request):
    # Hỗ trợ cả xóa đơn và xóa hàng loạt
    user_ids = request.POST.getlist('user_ids[]') or request.POST.getlist('user_ids')
    single_user_id = request.POST.get('single_user_id')
    if single_user_id:
        user_ids = list(user_ids) + [single_user_id]
    else:
        user_ids = list(user_ids)
    user_ids = [uid for uid in user_ids if uid]
    # Preserve order while removing duplicates
    seen_ids = set()
    deduped_user_ids = []
    for uid in user_ids:
        if uid not in seen_ids:
            deduped_user_ids.append(uid)
            seen_ids.add(uid)
    user_ids = deduped_user_ids

    original_count = len(user_ids)

    if not user_ids:
        alert = {"icon": "info", "title": "Không có người dùng nào được chọn."}
    else:
        current_user_id_str = str(request.user.id)
        user_ids_to_delete = [uid for uid in user_ids if uid != current_user_id_str]
        deleted_users_info = []
        
        count_deleted = 0
        if user_ids_to_delete:
            user_ids_int = [int(uid) for uid in user_ids_to_delete]
            users_to_delete_qs = User.objects.filter(id__in=user_ids_int)
            # Lấy số lượng user sẽ bị xóa TRƯỚC KHI thực hiện xóa
            count_to_delete = users_to_delete_qs.count()
            # Lấy thông tin user trước khi xóa
            if original_count == 1 and user_ids_to_delete:
                user_instance = users_to_delete_qs.first()
                if user_instance:
                    deleted_users_info.append(user_instance.display_name_with_email())

            # users_to_delete_qs.delete()
            users_to_delete_qs.update(is_active=False)
            count_deleted = count_to_delete # Gán số lượng đúng để hiển thị

        # Logic thông báo
        self_delete_attempt = original_count > len(user_ids_to_delete)
        
        if self_delete_attempt:
            if count_deleted > 0:
                alert = {
                    "icon": "warning",
                    "title": f"Đã vô hiệu hóa {count_deleted} người dùng.",
                    "text": "Bạn không thể tự xóa chính mình."
                }
            else:
                alert = {
                    "icon": "error",
                    "title": "Không thể xóa",
                    "text": "Bạn không thể tự xóa chính mình."
                }
        elif count_deleted > 0:
            if original_count == 1 and deleted_users_info:
                alert = {
                    "icon": "success",
                    "title": f"Đã vô hiệu hóa {deleted_users_info[0]} thành công."
                }
            else:
                alert = {
                    "icon": "success",
                    "title": f"Đã vô hiệu hóa {count_deleted} người dùng thành công."
                }
        else:
            # Trường hợp không có user nào bị xóa (có thể do ID không tồn tại hoặc chỉ có ý định tự xóa)
            alert = {
                "icon": "info",
                "title": "Không có người dùng nào được xóa."
            }

    # Gửi thông báo SweetAlert qua HX-Trigger
    response = HttpResponse(status=200)
    response['HX-Trigger'] = json.dumps({
        "reload-accounts-table": True,
        "closeUserModal": True, 
        "show-sweet-alert": alert
    })
    return response
# Xem chi tiết người dùng
@login_required
@permission_required("accounts.view_user", raise_exception=True)
def user_detail_view(request, user_id):
    # Tối ưu truy vấn bằng cách select_related và prefetch_related
    user = get_object_or_404(
        User.objects.select_related('center').prefetch_related('groups'), 
        pk=user_id
    )
    
    children = None
    parents = None
    enrolled_classes = None
    teaching_classes = None
    assisting_classes = None
    

    # Lấy vai trò và chuyển thành chữ hoa để so sánh nhất quán
    user_role_upper = user.role.upper() if user.role else ''

    # Kiểm tra vai trò của người dùng và lấy các mối quan hệ tương ứng
    if user_role_upper == 'PARENT':
        children = ParentStudentRelation.objects.filter(parent=user).select_related('student__center')
    
    if user_role_upper == 'STUDENT':
        parents = ParentStudentRelation.objects.filter(student=user).select_related('parent__center')
        # Lấy các lớp học sinh đang ghi danh
        enrolled_classes = user.enrollments.select_related('klass__subject', 'klass__center').all()
        enrolled_classes = user.enrollments.select_related('klass__subject', 'klass__center')

    if user_role_upper == 'TEACHER' or user_role_upper == 'ASSISTANT':
        # Lấy các lớp giáo viên đang dạy (giáo viên chính)
        if hasattr(user, 'main_classes'):
            teaching_classes = user.main_classes.select_related('subject', 'center').all()
        else:
            teaching_classes = Class.objects.filter(main_teacher=user).select_related('subject', 'center')

        teaching_classes = user.main_classes.select_related('subject', 'center')
        # Lấy các lớp trợ giảng
        if hasattr(user, 'assist_classes'):
            assisting_classes = user.assist_classes.select_related('subject', 'center').all()
        else:
            assisting_classes = Class.objects.filter(assistants=user).select_related('subject', 'center')
        assisting_classes = user.assist_classes.select_related('subject', 'center')

    context = {
        'user': user,
        'children': children,
        'parents': parents,
        'enrolled_classes': enrolled_classes,
        'teaching_classes': teaching_classes,
        'assisting_classes': assisting_classes,
    }
    response = render(request, '_user_detail.html', context)
    # Nếu đang mở từ modal nhóm thì đóng modal đó trước khi hiển thị modal người dùng
    if is_htmx_request(request) and request.GET.get('from_group'):
        try:
            triggers = {
                "closeGroupModal": True
            }
            response["HX-Trigger"] = json.dumps(triggers)
        except Exception:
            pass
    return response
# Chỉnh sửa người dùng
@login_required
@permission_required("accounts.change_user", raise_exception=True)
def user_edit_view(request, user_id):
    u = get_object_or_404(User, id=user_id)
    if request.method == "GET":
        form = AdminUserUpdateForm(instance=u)
        return render(request, "_edit_user_form.html", {"form": form, "user": u})

    form = AdminUserUpdateForm(request.POST, request.FILES, instance=u)
    if form.is_valid():
        updated_user = form.save()
        resp = HttpResponse(status=200)
        resp["HX-Trigger"] = json.dumps({
            "reload-accounts-table": True,
            "closeUserModal": True,
            "show-sweet-alert": {
                "icon": "success",
                "title": "Thành công",
                "text": f"Đã cập nhật thông tin người dùng: {updated_user.preferred_full_name()}",
                "timer": 1500,
                "showConfirmButton": False
            }
        })
        return resp

    html = render_to_string("_edit_user_form.html", {"form": form, "user": u}, request=request)
    resp = HttpResponse(html, status=400)
    resp["HX-Trigger"] = json.dumps({
        "show-sweet-alert": {
            "icon": "error",
            "title": "Không thể cập nhật thông tin người dùng",
            "text": form_errors_as_text(form),
            "showConfirmButton": True
        }
    })
    return resp

# Xuất danh sách người dùng
@login_required
@permission_required("accounts.view_user", raise_exception=True)
def export_users_view(request):
    user_resource = UserResource()
    # Sử dụng hàm lọc đã được tái cấu trúc
    queryset = _filter_users_queryset(request)
    dataset = user_resource.export(queryset.order_by('id'))
    
    # Định dạng file export, có thể là 'xls', 'xlsx', 'csv'
    file_format = request.GET.get('format', 'xlsx')
    if file_format == 'xlsx':
        response = HttpResponse(dataset.export('xlsx'), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="users.xlsx"'
    elif file_format == 'csv':
        response = HttpResponse(dataset.export('csv'), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="users.csv"'
    else: # Mặc định là xls
        response = HttpResponse(dataset.export('xls'), content_type='application/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename="users.xls"'
        
    return response

# Hiển thị modal chọn định dạng xuất người dùng
@login_required
@permission_required("accounts.view_user", raise_exception=True)
def export_users_modal_view(request):
    if not is_htmx_request(request):
        return redirect("accounts:manage_accounts")

    query_params = request.GET.copy()
    for key in ["format"]:
        query_params.pop(key, None)

    query_string = query_params.urlencode()
    export_url = reverse("accounts:export_users")
    query_suffix = f"&{query_string}" if query_string else ""
    trigger_base = reverse("accounts:initiate_export_users")

    format_links = []
    options = [
        (
            "xlsx",
            "Excel (.xlsx)",
            "bi bi-file-earmark-spreadsheet",
            "Đầy đủ định dạng, phù hợp nhất cho Excel hiện đại.",
        ),
        (
            "csv",
            "CSV (.csv)",
            "bi bi-filetype-csv",
            "Dữ liệu dạng bảng, dễ import vào hệ thống khác.",
        ),
        (
            "xls",
            "Excel cũ (.xls)",
            "bi bi-file-earmark-excel",
            "Tương thích với các phiên bản Excel cũ.",
        ),
    ]

    for fmt, label, icon, description in options:
        format_links.append({
            "label": label,
            "icon": icon,
            "description": description,
            "trigger_url": f"{trigger_base}?format={fmt}{query_suffix}",
        })

    context = {
        "format_links": format_links,
        "has_active_filters": bool(query_params),
    }
    return render(request, "_export_users_modal.html", context)

# Xử lý khởi tạo xuất người dùng (trả về URL tải file)
@login_required
@permission_required("accounts.view_user", raise_exception=True)
def export_users_initiate_view(request):
    if not is_htmx_request(request):
        return redirect("accounts:manage_accounts")

    format_value = (request.GET.get("format") or "xlsx").lower()
    if format_value not in {"xlsx", "csv", "xls"}:
        format_value = "xlsx"

    query_params = request.GET.copy()
    query_params.pop("format", None)
    query_string = query_params.urlencode()

    download_url = reverse("accounts:export_users") + f"?format={format_value}"
    if query_string:
        download_url = f"{download_url}&{query_string}"

    response = HttpResponse(status=204)
    response["HX-Trigger"] = json.dumps({
        "closeUserModal": True,
        "triggerUserExport": {"url": download_url},
    })
    return response

# Nhập người dùng từ file
@login_required
@permission_required("accounts.add_user", raise_exception=True)
def import_users_view(request):
    if request.method == 'POST':
        user_resource = UserResource()
        dataset = Dataset()
        new_users_file = request.FILES.get('file')

        if not new_users_file:
            form = ImportUserForm()
            # Truyền lỗi trực tiếp vào context thay vì dùng messages framework
            return render(request, '_import_users_form.html', {'form': form, 'errors': ["Vui lòng chọn một file để import."]}, status=422)

        # Đọc dữ liệu từ file upload
        try:
            if new_users_file.name.endswith('csv'):
                # Dữ liệu từ file CSV có thể là tab-separated, nên dùng format 'tsv'
                # Thử đọc với utf-8-sig trước, nếu lỗi thì thử cp1252 (Windows encoding)
                file_content = new_users_file.read()
                try:
                    decoded_content = file_content.decode('utf-8-sig')
                except UnicodeDecodeError:
                    # Nếu utf-8-sig thất bại, thử với cp1252 là một phương án dự phòng phổ biến
                    decoded_content = file_content.decode('cp1252')
                # Để tablib tự động phát hiện định dạng (csv hoặc tsv)
                dataset.load(decoded_content)
            else: # Mặc định là excel
                dataset.load(new_users_file.read(), format='xlsx')
        except (UnicodeDecodeError, TablibException, InvalidFileException, ValueError) as exc:
            form = ImportUserForm()
            if isinstance(exc, (TablibException, InvalidFileException, ValueError)):
                error_message = (
                    "Không thể đọc file import. Vui lòng sử dụng đúng định dạng .xlsx hoặc .csv."
                )
            else:
                error_message = (
                    "Không thể giải mã nội dung file. Vui lòng lưu file với mã hóa UTF-8."
                )
            response = render(request, '_import_users_form.html', {
                'form': form,
                'errors': [error_message]
            }, status=422)
            response['HX-Trigger'] = json.dumps({
                "show-sweet-alert": {
                    "icon": "error",
                    "title": "Import thất bại",
                    "text": error_message
                }
            })
            return response

        # Thực hiện import, dry_run=True để kiểm tra lỗi trước
        result = user_resource.import_data(dataset, dry_run=True, raise_errors=False)

        if not result.has_errors() and not result.has_validation_errors():
            # Nếu không có lỗi, thực hiện import thật
            user_resource.import_data(dataset, dry_run=False)
            response = HttpResponse(status=200)
            response['HX-Trigger'] = json.dumps({
                "reload-accounts-table": True,
                "closeUserModal": True,
                "show-sweet-alert": {
                    "icon": "success",
                    "title": "Import người dùng thành công!"
                }
            })
            return response
        else:
            errors = []
            # Lỗi xác thực (validation errors)
            for invalid_row in result.invalid_rows:
                errors.append(f"Dòng {invalid_row.number}: Lỗi dữ liệu - {invalid_row.error_dict}")

            # Lỗi chung (ví dụ: không tìm thấy foreign key)
            for row_num, error_list in result.row_errors():
                error_messages = []
                for error in error_list:
                    original_error = error.error
                    # Tùy chỉnh thông báo lỗi cho các trường hợp cụ thể
                    if isinstance(original_error, Center.DoesNotExist):
                        # Lỗi không tìm thấy Center
                        error_messages.append("Trung tâm không tồn tại. Vui lòng tạo trung tâm trước khi import.")
                    elif isinstance(original_error, Group.DoesNotExist):
                        # Lỗi không tìm thấy Group
                        error_messages.append("Nhóm quyền không tồn tại. Vui lòng tạo nhóm quyền trước khi import.")
                    elif hasattr(original_error, 'messages'):
                        # Dành cho Django ValidationErrors
                        error_messages.extend(original_error.messages)
                    else:
                        # Các lỗi khác
                        error_messages.append(str(original_error))
                errors.append(f"Dòng {row_num}: {', '.join(error_messages)}")
            form = ImportUserForm()
            response = render(request, '_import_users_form.html', {'form': form, 'errors': errors}, status=422)
            response['HX-Trigger'] = json.dumps({
                "show-sweet-alert": {
                    "icon": "error",
                    "title": "Import thất bại",
                    "text": "Vui lòng kiểm tra chi tiết lỗi trong form."
                }
            })
            return response

    else:
        form = ImportUserForm()
        return render(request, '_import_users_form.html', {'form': form})

# Tải mẫu import người dùng
@login_required
@permission_required("accounts.view_user", raise_exception=True)
def export_import_template_view(request):
    user_resource = UserResource()
    dataset = Dataset(headers=user_resource.get_export_headers())
    # Sử dụng phương thức export() để đảm bảo định dạng được xử lý đúng cách
    response = HttpResponse(dataset.export('xlsx'), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="import_users_template.xlsx"'
    return response


# Quản lý nhóm người dùng
PERMISSION_ACTIONS = [
    ("view", "Xem"),
    ("add", "Thêm"),
    ("change", "Sửa"),
    ("delete", "Xóa"),
]

# Nhóm quyền theo tính năng và model
def _group_permissions_by_functionality(permissions_qs):
    """
    Nhóm quyền theo tính năng và model để giao diện hiển thị dạng lưới 4 hành động.
    """
    grouped: OrderedDict[str, list] = OrderedDict()
    model_lookup = {}
    permissions = permissions_qs.select_related('content_type').order_by(
        'content_type__app_label', 'content_type__model', 'codename'
    )

    functional_groups = {
        "Quản lý Người dùng & Nhóm": ['user', 'group', 'parentstudentrelation', 'permission', 'contenttype'],
        "Quản lý Trung tâm": ['center', 'room'],
        "Quản lý Chương trình học": ['subject', 'module', 'lesson', 'lecture', 'exercise'],
        "Quản lý Lớp học & Buổi học": ['class', 'classassistant', 'classsession'],
        "Quản lý Tuyển sinh & Điểm danh": ['enrollment', 'attendance'],
        "Quản lý Đánh giá": ['assessment'],
        "Quản lý Điểm thưởng & Quà tặng": ['pointaccount', 'rewarditem', 'rewardtransaction'],
        "Quản lý Sản phẩm Học sinh": ['studentproduct'],
        "Quản lý Thông báo": ['notification'],
        "Quản lý Tài chính (Billing)": [], 
        "Quản lý Báo cáo": [],
        "Hệ thống & Admin": ['logentry', 'session'],
    }

    model_to_group = {}
    for group_name, models in functional_groups.items():
        for model_name in models:
            model_to_group[model_name] = group_name

    for perm in permissions:
        model_name = perm.content_type.model
        group_name = model_to_group.get(model_name, "Chức năng Khác")

        if group_name not in grouped:
            grouped[group_name] = []

        if perm.codename.startswith('add_'):
            action = "Thêm"
            action_key = "add"
        elif perm.codename.startswith('change_'):
            action = "Sửa"
            action_key = "change"
        elif perm.codename.startswith('delete_'):
            action = "Xóa"
            action_key = "delete"
        elif perm.codename.startswith('view_'):
            action = "Xem"
            action_key = "view"
        else:
            action = perm.codename.replace('_', ' ').capitalize() 
            action_key = None

        # Lấy tên model dễ đọc
        try:
             # Ưu tiên verbose_name nếu có
            model_class = perm.content_type.model_class()
            if model_class and hasattr(model_class._meta, 'verbose_name'):
                 model_verbose_name = model_class._meta.verbose_name.title()
            else:
                 # Nếu không, dùng tên ContentType (thường là tên model viết thường)
                 model_verbose_name = ContentType.objects.get_for_id(perm.content_type_id).name.title()
        except Exception:
             # Fallback nếu có lỗi
             model_verbose_name = perm.content_type.model.replace('_', ' ').capitalize()


        clear_label = f"{action} {model_verbose_name}"
        model_key = (group_name, model_name)
        if model_key not in model_lookup:
            model_lookup[model_key] = {
                "model": model_verbose_name,
                "permissions": {key: None for key, _ in PERMISSION_ACTIONS},
                "others": []
            }
            grouped[group_name].append(model_lookup[model_key])

        if action_key in model_lookup[model_key]["permissions"]:
            model_lookup[model_key]["permissions"][action_key] = {"id": perm.id, "label": clear_label}
        else:
            model_lookup[model_key]["others"].append((perm.id, clear_label))

    # Sắp xếp lại dict theo thứ tự functional_groups
    ordered_grouped = {name: grouped.get(name, []) for name in functional_groups if name in grouped}
    if "Chức năng Khác" in grouped:
         ordered_grouped["Chức năng Khác"] = grouped["Chức năng Khác"]

    return ordered_grouped

# Quản lý nhóm người dùng
@login_required
@permission_required("auth.view_group", raise_exception=True)
def manage_groups(request):
    groups_list = Group.objects.annotate(user_count=Count('user')).order_by('name')

    try:
        per_page = int(request.GET.get("per_page", 10))
    except (TypeError, ValueError):
        per_page = 10
    try:
        page = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page = 1

    paginator = Paginator(groups_list, per_page)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(1)

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
        "current_query_params": request.GET.urlencode(),
    }

    if is_htmx_request(request):
        return render(request, "_groups_table.html", context)

    return render(request, "manage_groups.html", context)

# Tạo nhóm người dùng
@login_required
@permission_required("auth.add_group", raise_exception=True)
def group_create_view(request):
    if request.method == 'POST':
        form = SimpleGroupForm(request.POST)
        if form.is_valid():
            group = form.save()
            response = HttpResponse(status=200)
            response['HX-Trigger'] = json.dumps({
                "reload-groups-table": True,
                "closeGroupModal": True,
                "show-sweet-alert": {
                    "icon": "success",
                    "title": f"Đã tạo nhóm '{group.name}' thành công!"
                }
            })
            return response
        else:
            all_permissions = Permission.objects.all()
            functional_grouped_permissions = _group_permissions_by_functionality(all_permissions)
            context = {
                'form': form,
                'functional_grouped_permissions': functional_grouped_permissions,
                'permission_actions': PERMISSION_ACTIONS,
            }
            response = render(request, '_group_form.html', context, status=422)
            response['HX-Trigger'] = json.dumps({
                "show-sweet-alert": {
                    "icon": "error",
                    "title": "Không thể tạo nhóm",
                    "text": form_errors_as_text(form)
                }
            })
            return response
    else:  # Yêu cầu GET
        form = SimpleGroupForm()
        all_permissions = Permission.objects.all()
        functional_grouped_permissions = _group_permissions_by_functionality(all_permissions)
        context = {
            'form': form,
            'functional_grouped_permissions': functional_grouped_permissions,
            'permission_actions': PERMISSION_ACTIONS,
        }
        return render(request, '_group_form.html', context)

# Chỉnh sửa nhóm người dùng
@login_required
@permission_required("auth.change_group", raise_exception=True)
def group_edit_view(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    if request.method == 'POST':
        form = SimpleGroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            response = HttpResponse(status=200)
            response['HX-Trigger'] = json.dumps({
                "reload-groups-table": True,
                "closeGroupModal": True,
                "show-sweet-alert": {
                    "icon": "success",
                    "title": f"Cập nhật nhóm '{group.name}' thành công!"
                }
            })
            return response
        else:
            all_permissions = Permission.objects.all()
            functional_grouped_permissions = _group_permissions_by_functionality(all_permissions)
            context = {
                'form': form,
                'group': group,
                'functional_grouped_permissions': functional_grouped_permissions,
                'permission_actions': PERMISSION_ACTIONS,
            }
            response = render(request, '_group_form.html', context, status=422)
            response['HX-Trigger'] = json.dumps({
                "show-sweet-alert": {
                    "icon": "error",
                    "title": "Không thể cập nhật nhóm",
                    "text": form_errors_as_text(form)
                }
            })
            return response
    else:  # Yêu cầu GET
        form = SimpleGroupForm(instance=group)
        all_permissions = Permission.objects.all()
        functional_grouped_permissions = _group_permissions_by_functionality(all_permissions)
        context = {
            'form': form,
            'group': group,
            'functional_grouped_permissions': functional_grouped_permissions,
            'permission_actions': PERMISSION_ACTIONS,
        }
        return render(request, '_group_form.html', context)

# Xóa nhóm người dùng
@require_POST
@login_required
@permission_required("auth.delete_group", raise_exception=True)
def group_delete_view(request):
    group_ids = request.POST.getlist('group_ids[]') or request.POST.getlist('group_id_single')
    unique_group_ids = list(set(group_ids))
    alert = {} 
    deleted_names = []
    protected_names = []
    in_use_names = []
    
    if not unique_group_ids:
        alert = {"icon": "info", "title": "Không có nhóm nào được chọn."}
    else:
        try:
            group_ids_int = [int(gid) for gid in unique_group_ids]
            
            # Lấy tất cả các nhóm được chọn VÀ đếm số lượng người dùng của mỗi nhóm
            selected_groups_qs = Group.objects.filter(id__in=group_ids_int).annotate(user_count_agg=Count('user'))
            
            groups_to_delete = []
            
            # Phân loại các nhóm dựa trên tiêu chí xóa
            for group in selected_groups_qs:
                # Tiêu chí 1: Không phải nhóm được bảo vệ
                if group.name in PROTECTED_GROUPS:
                    protected_names.append(group.name)
                # Tiêu chí 2: Không có người dùng nào (an toàn để xóa)
                elif group.user_count_agg > 0:
                    in_use_names.append(group.name)
                # Đủ điều kiện xóa
                else:
                    groups_to_delete.append(group)
            
            deleted_count = len(groups_to_delete)
            if deleted_count > 0:
                for group in groups_to_delete:
                    deleted_names.append(group.name)
                
                # Thực hiện xóa chỉ các nhóm đủ điều kiện
                Group.objects.filter(id__in=[g.id for g in groups_to_delete]).delete()

            # --- Xây dựng thông báo phản hồi ---
            if deleted_count > 0:
                alert = {
                    "icon": "success", 
                    "title": f"Đã xóa {deleted_count} nhóm thành công.",
                    # SỬA LỖI CÚ PHÁP: Bỏ dấu \
                    "text": f"Các nhóm đã xóa: {', '.join([f"'{n}'" for n in deleted_names])}"
                }
            else:
                 alert = {"icon": "info", "title": "Không có nhóm nào được xóa."}
            
            # Bổ sung thông tin lỗi (nếu có)
            error_details = []
            if protected_names:
                # SỬA LỖI CÚ PHÁP: Bỏ dấu \
                error_details.append(f"Không thể xóa nhóm hệ thống: {', '.join([f"'{n}'" for n in protected_names])}.")
            if in_use_names:
                # SỬA LỖI CÚ PHÁP: Bỏ dấu \
                error_details.append(f"Không thể xóa nhóm đang có người dùng: {', '.join([f"'{n}'" for n in in_use_names])}.")
            
            if error_details:
                if deleted_count > 0: # Đã xóa 1 số, 1 số lỗi
                     alert["icon"] = "warning" # Đổi thành Warning
                     alert["title"] = f"Đã xóa {deleted_count} nhóm, tuy nhiên:"
                     alert["text"] = " ".join(error_details)
                else: # Không xóa được gì
                    alert["icon"] = "error"
                    alert["title"] = "Không thể xóa"
                    alert["text"] = " ".join(error_details)

        except ValueError:
            alert = {"icon": "error", "title": "ID nhóm không hợp lệ."}
        except ProtectedError as e: # Bắt lỗi nếu có quan hệ không xóa được
             alert = {"icon": "error", "title": "Lỗi ràng buộc", "text": "Không thể xóa nhóm vì có các đối tượng khác đang tham chiếu đến nó."}
        except Exception as e:
            alert = {"icon": "error", "title": "Lỗi máy chủ", "text": str(e)}

    # Trả về response cho HTMX
    response = HttpResponse(status=200)
    response['HX-Trigger'] = json.dumps({
        "reload-groups-table": True,
        "closeGroupModal": True,
        "show-sweet-alert": alert
    })
    return response

# Lọc người dùng theo các tiêu chí (hàm tái sử dụng)
@login_required
@permission_required("accounts.view_user", raise_exception=True)
def group_users_view(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    
    # Lấy query cơ sở từ hàm filter
    qs = _filter_users_queryset(request)
    
    # Lọc thêm theo nhóm này
    qs = qs.filter(groups=group).order_by('last_name', 'first_name')
    
    # Phân trang
    try:
        per_page = int(request.GET.get("per_page_group", 10)) # Dùng 1 param khác
    except (TypeError, ValueError):
        per_page = 10
    try:
        page = int(request.GET.get("page_group", 1)) # Dùng 1 param khác
    except (TypeError, ValueError):
        page = 1

    paginator = Paginator(qs, per_page)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(1)

    context = {
        "group": group,
        "page_obj": page_obj,
        "paginator": paginator,
        "per_page": per_page,
        "current_query_params": request.GET.urlencode(),
    }
    
    # Trả về partial mới
    return render(request, '_group_users_list.html', context)

# Xem chi tiết nhóm người dùng
@login_required
@permission_required("auth.view_group", raise_exception=True)
def group_view(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    # Gom và trình bày danh sách quyền theo từng nhóm để dễ đọc
    group_permissions = group.permissions.select_related('content_type').all()
    functional_grouped_permissions = _group_permissions_by_functionality(group_permissions)

    context = {
        'group': group,
        'functional_grouped_permissions': functional_grouped_permissions,
        'permission_actions': PERMISSION_ACTIONS,
    }
    return render(request, '_group_view.html', context)


# Hồ sơ và mật khẩu cá nhân
@login_required
def profile_view(request):
    user = request.user
    # Xử lý khi người dùng submit form chỉnh sửa
    if request.method == 'POST' and is_htmx_request(request):
        form = UserProfileUpdateForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            # Làm mới instance người dùng từ DB để lấy dữ liệu mới nhất
            user.refresh_from_db()
            response = render(request, '_profile_detail.html', {'user': user})
            response['HX-Trigger'] = json.dumps({
                "show-sweet-alert": {
                    "icon": "success",
                    "title": "Cập nhật hồ sơ thành công!",
                },
                "updateProfileHeader": {
                    "fullName": user.get_full_name() or user.username,
                    "avatarUrl": user.avatar.url if user.avatar else None
                }
            })
            return response
        else:
            response = render(request, '_profile_form_edit.html', {'form': form}, status=422)
            response['HX-Trigger'] = json.dumps({
                "show-sweet-alert": {
                    "icon": "error",
                    "title": "Không thể cập nhật hồ sơ",
                    "text": form_errors_as_text(form)
                }
            })
            return response

    # Xử lý GET request (tải trang lần đầu hoặc bấm nút "Hủy")
    # Mặc định là hiển thị thông tin "chỉ xem"
    try:
        reward_account = PointAccount.get_or_create_for_student(user)
        reward_transactions = RewardTransaction.objects.filter(student=user).order_by("-created_at")[:5]
    except Exception:
        reward_account = None
        reward_transactions = []

    if is_htmx_request(request):
        return render(request, '_profile_detail.html', {'user': user, 'reward_account': reward_account, 'reward_transactions': reward_transactions})

    context = {
        'user': user,
        'password_form': UserPasswordChangeForm(user=user),
        'reward_account': reward_account,
        'reward_transactions': reward_transactions,
    }
    return render(request, 'profile.html', context)


# Chỉnh sửa hồ sơ cá nhân
@login_required
def profile_edit_view(request):
    # View này chỉ để trả về form chỉnh sửa khi người dùng bấm nút "Chỉnh sửa"
    form = UserProfileUpdateForm(instance=request.user)
    return render(request, '_profile_form_edit.html', {'form': form})

# Đổi mật khẩu cá nhân
@login_required
@require_POST # Chỉ chấp nhận POST
def change_password_view(request):
    user = request.user
    form = UserPasswordChangeForm(user=user, data=request.POST)
    if form.is_valid():
        user = form.save()
        # Quan trọng: Cập nhật session auth hash để người dùng không bị logout
        update_session_auth_hash(request, user)

        # Gửi trigger thành công (ví dụ: reset form, hiển thị toast)
        response = HttpResponse(status=200) 
        response['HX-Trigger'] = json.dumps({
            "resetPasswordForm": True, 
            "closePasswordModal": True, 
            "show-sweet-alert": {
                "icon": "success",
                "title": "Đổi mật khẩu thành công!",
            },
        })
        return response
    else:
        # Trả về partial template của form mật khẩu với lỗi
        # Đảm bảo template này chỉ chứa form đổi mật khẩu
        response = render(request, '_password_change_form.html', {'password_form': form, 'user': user}, status=422) # Giữ nguyên status 422 cho HTMX
        
        error_messages_html_parts = []

        # Xử lý lỗi mật khẩu cũ
        # Kiểm tra nếu lỗi sai mật khẩu cũ (code: 'password_incorrect')
        if 'old_password' in form.errors:
            if any(e.code == 'password_incorrect' for e in form.errors.as_data()['old_password']):
                # Lấy thông báo lỗi tùy chỉnh đã định nghĩa trong forms.py
                error_messages_html_parts.append(f"{form.fields['old_password'].error_messages['password_incorrect']}")
            # Xử lý lỗi mật khẩu cũ khác (ví dụ: trường bắt buộc)
            elif form.fields['old_password'].error_messages.get('required') in form.errors['old_password']:
                error_messages_html_parts.append(f"{form.fields['old_password'].error_messages['required']}")


        # Lỗi không liên quan đến một trường cụ thể (ví dụ: mật khẩu xác nhận không khớp)
        if form.non_field_errors():
            for error in form.non_field_errors():
                error_messages_html_parts.append(f"{error}")

        # Lỗi của trường mật khẩu mới (new_password1)
        if 'new_password1' in form.errors:
            for error_msg in form.errors['new_password1']:
                # Chỉ lấy thông báo lỗi, không thêm label trường
                error_messages_html_parts.append(f"Mật khẩu mới: {error_msg}")
        if 'new_password2' in form.errors:
            for error_msg in form.errors['new_password2']:

                if form.fields['new_password2'].error_messages.get('required') == error_msg:
                    error_messages_html_parts.append(f"{error_msg}") 


        final_error_text = "Đã có lỗi xảy ra. Vui lòng kiểm tra lại."
        if error_messages_html_parts:
            # Lọc các lỗi trùng lặp và tạo chuỗi HTML cuối cùng
            unique_errors = list(dict.fromkeys(error_messages_html_parts))
            final_error_text = "".join(unique_errors)

        response['HX-Trigger'] = json.dumps({
            "show-sweet-alert": {"icon": "error", "title": "Lỗi", "text": final_error_text}
        })
        return response
