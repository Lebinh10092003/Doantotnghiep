import json
from datetime import timedelta
from pyexpat.errors import messages
from django.utils.dateparse import parse_date
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator, EmptyPage
from django.template.loader import render_to_string
from django.db.models import Q, Count
from apps.centers.models import Center
from .models import ParentStudentRelation
from .forms import AdminUserCreateForm, AdminUserUpdateForm, ImportUserForm
from .resources import UserResource
from tablib import Dataset

User = get_user_model()


def is_htmx_request(request):
    return (
        request.headers.get("HX-Request") == "true"
        or request.META.get("HTTP_HX_REQUEST") == "true"
        or bool(getattr(request, "htmx", False))
    )


@ensure_csrf_cookie
def login_view(request):
    if request.method == "POST":
        login_id = request.POST.get("phone", "").strip()
        password = request.POST.get("password", "")
        remember = request.POST.get("remember")

        # Tìm user theo phone
        user = User.objects.filter(phone=login_id).first()
        if not user:
            if is_htmx_request(request):
                resp = HttpResponse("", status=400)
                resp["HX-Trigger"] = json.dumps({
                    "show-sweet-alert": {
                        "icon": "error", "title": "Số điện thoại không tồn tại"
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

        # Nếu request HTMX: trả modal + redirect
        if is_htmx_request(request):
            resp = HttpResponse("")
            resp["HX-Trigger"] = json.dumps({
                "show-sweet-alert": {
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


def is_admin(user):
    return user.is_superuser or getattr(user, "role", None) == "ADMIN"

def _filter_users_queryset(request):
    qs = User.objects.all().select_related("center").prefetch_related("groups")
    
    # params
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    role_choice = request.GET.get("role", "")      
    group_name = request.GET.get("group", "")    
    center_id = request.GET.get("center", "")
    is_staff = request.GET.get("is_staff", "")
    is_superuser = request.GET.get("is_superuser", "")
    date_from = request.GET.get("date_joined_from", "")
    date_to = request.GET.get("date_joined_to", "")
    last_login_from = request.GET.get("last_login_from", "")
    last_login_to = request.GET.get("last_login_to", "")

    # Search
    if q:
        tokens = [t for t in q.split() if t]
        for t in tokens:
            qs = qs.filter(
                Q(first_name__icontains=t) |
                Q(last_name__icontains=t) |
                Q(email__icontains=t) |
                Q(phone__icontains=t) |
                Q(username__icontains=t)
            )

    # Status
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)

    # Filter by role (choice field on User)
    if role_choice:
        qs = qs.filter(groups__name=role_choice).distinct()

    # Filter by Django Group (accept name or id)
    if group_name:
        if group_name.isdigit():
            qs = qs.filter(groups__id=int(group_name))
        else:
            qs = qs.filter(groups__name=group_name)
        qs = qs.distinct()

    # Center filter
    if center_id:
        try:
            cid = int(center_id)
            qs = qs.filter(center_id=cid)
        except (ValueError, TypeError):
            pass

    # staff / superuser filters
    if isinstance(is_staff, str) and is_staff:
        v = is_staff.lower()
        if v in ("1", "true", "yes", "on"):
            qs = qs.filter(is_staff=True)
        elif v in ("0", "false", "no"):
            qs = qs.filter(is_staff=False)

    if isinstance(is_superuser, str) and is_superuser:
        v = is_superuser.lower()
        if v in ("1", "true", "yes", "on"):
            qs = qs.filter(is_superuser=True)
        elif v in ("0", "false", "no"):
            qs = qs.filter(is_superuser=False)

    # Date range filters
    def apply_date_range(qs_in, field, start_str, end_str):
        qs_out = qs_in
        if start_str:
            d = parse_date(start_str)
            if d:
                qs_out = qs_out.filter(**{f"{field}__date__gte": d})
        if end_str:
            d = parse_date(end_str)
            if d:
                qs_out = qs_out.filter(**{f"{field}__date__lte": d})
        return qs_out

    qs = apply_date_range(qs, "date_joined", date_from, date_to)
    qs = apply_date_range(qs, "last_login", last_login_from, last_login_to)
    
    return qs.distinct()


@login_required
def manage_accounts(request):
    qs = _filter_users_queryset(request)
    groups_for_dropdown = list(Group.objects.values_list("name", "name"))
    
    # Params for sorting and pagination
    group_by = request.GET.get("group_by", "")
    try:
        per_page = int(request.GET.get("per_page", 10))
    except (TypeError, ValueError):
        per_page = 10
    try:
        page = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page = 1


    # Ordering / grouping
    if group_by == "role":
        qs = qs.order_by("role", "last_name", "first_name")
    elif group_by == "group":
        qs = qs.order_by("groups__name", "last_name", "first_name")
    elif group_by == "center":
        qs = qs.order_by("center__name", "last_name", "first_name")
    else:
        qs = qs.order_by("last_name", "first_name")

    # Pagination
    paginator = Paginator(qs, per_page)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(1)

    relations = ParentStudentRelation.objects.select_related("parent", "student").all()
    groups_list = list(Group.objects.values_list("name", flat=True))
    centers_list = list(Center.objects.values("id", "name").order_by("name"))

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "q": request.GET.get("q", "").strip(),
        "status": request.GET.get("status", ""),
        "role": request.GET.get("role", ""),
        "group_list": groups_for_dropdown,
        "group": request.GET.get("group", ""),
        "groups_list": groups_list,
        "center": request.GET.get("center", ""),
        "centers_list": centers_list,
        "is_staff": request.GET.get("is_staff", ""),
        "is_superuser": request.GET.get("is_superuser", ""),
        "date_joined_from": request.GET.get("date_joined_from", ""),
        "date_joined_to": request.GET.get("date_joined_to", ""),
        "last_login_from": request.GET.get("last_login_from", ""),
        "last_login_to": request.GET.get("last_login_to", ""),
        "group_by": request.GET.get("group_by", ""),
        "per_page": per_page,
        "relations": relations,
    }

    if is_htmx_request(request):
        return render(request, "_accounts_table.html", context)

    return render(request, "manage_accounts.html", context)

@login_required
def user_create_view(request):
    if request.method == 'POST':
        form = AdminUserCreateForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            response = HttpResponse(status=200)
            response['HX-Trigger'] = json.dumps({
                "reloadTableEvent": True,
                "closeUserModal": True,
                "show-sweet-alert": {
                    "icon": "success",
                    "title": f"Đã tạo người dùng '{user.username}' thành công!"
                }
            })
            return response
        else:
            # Nếu form không hợp lệ, render lại form với lỗi để HTMX cập nhật UI
            context = {
                'form': form,
            }
            return render(request, '_add_user_form.html', context, status=422) # status 422 để HTMX biết có lỗi
    else:
        form = AdminUserCreateForm()
    
    # Thêm context `enctype` để template biết cần thêm thuộc tính cho form
    context = {
        'form': form,
        'enctype': 'multipart/form-data'
    }
    return render(request, '_add_user_form.html', context)


@require_POST
@login_required
def user_delete_view(request):
    # Hỗ trợ cả xóa đơn và xóa hàng loạt
    user_ids = request.POST.getlist('user_ids[]') or request.POST.getlist('user_ids')
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
            # Lấy thông tin user trước khi xóa
            if original_count == 1 and user_ids_to_delete:
                user_instance = users_to_delete_qs.first()
                if user_instance:
                    deleted_users_info.append(user_instance.username)

            count_deleted, _ = users_to_delete_qs.delete()

        # Logic thông báo
        self_delete_attempt = original_count > len(user_ids_to_delete)
        
        if self_delete_attempt:
            if count_deleted > 0:
                alert = {
                    "icon": "warning",
                    "title": f"Đã xóa {count_deleted} người dùng.",
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
                    "title": f"Đã xóa người dùng '{deleted_users_info[0]}' thành công."
                }
            else:
                alert = {
                    "icon": "success",
                    "title": f"Đã xóa {count_deleted} người dùng thành công."
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
        "reloadTableEvent": True,
        "closeUserModal": True, # Đóng modal chi tiết nếu xóa từ đó
        "show-sweet-alert": alert
    })
    return response

@login_required
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

    # Kiểm tra vai trò của người dùng và lấy các mối quan hệ tương ứng
    if user.role == 'PARENT':
        children = ParentStudentRelation.objects.filter(parent=user).select_related('student__center')
    
    if user.role == 'STUDENT':
        parents = ParentStudentRelation.objects.filter(student=user).select_related('parent__center')
        # Lấy các lớp học sinh đang ghi danh
        enrolled_classes = user.enrollments.select_related('klass__subject', 'klass__center').all()

    if user.role == 'TEACHER':
        # Lấy các lớp giáo viên đang dạy
        teaching_classes = user.taught_classes.select_related('subject', 'center').all()

    context = {
        'user': user,
        'children': children,
        'parents': parents,
        'enrolled_classes': enrolled_classes,
        'teaching_classes': teaching_classes,
    }
    return render(request, '_user_detail.html', context)

@login_required
def user_edit_view(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        form = AdminUserUpdateForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            # Trả về 200 OK với nội dung trống để đảm bảo HTMX xử lý trigger
            response = HttpResponse(status=200)
            response['HX-Trigger'] = json.dumps({
                "reloadTableEvent": True,
                "closeUserModal": True,
                "show-sweet-alert": {
                    "icon": "success",
                    "title": f"Cập nhật người dùng '{user.username}' thành công!"
                }
            })
            return response
        else:
            # Nếu form không hợp lệ, render lại form với lỗi
            return render(request, '_edit_user_form.html', {'form': form, 'user': user}, status=422)
    else:
        form = AdminUserUpdateForm(instance=user)

    return render(request, '_edit_user_form.html', {'form': form, 'user': user})

@login_required
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

@login_required
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

        # Thực hiện import, dry_run=True để kiểm tra lỗi trước
        result = user_resource.import_data(dataset, dry_run=True, raise_errors=False)

        if not result.has_errors() and not result.has_validation_errors():
            # Nếu không có lỗi, thực hiện import thật
            user_resource.import_data(dataset, dry_run=False)
            response = HttpResponse(status=200)
            response['HX-Trigger'] = json.dumps({
                "reloadTableEvent": True,
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
            return render(request, '_import_users_form.html', {'form': form, 'errors': errors}, status=422)

    else:
        form = ImportUserForm()
        return render(request, '_import_users_form.html', {'form': form})

@login_required
def export_import_template_view(request):
    user_resource = UserResource()
    dataset = Dataset(headers=user_resource.get_export_headers())
    # Sử dụng phương thức export() để đảm bảo định dạng được xử lý đúng cách
    response = HttpResponse(dataset.export('xlsx'), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="import_users_template.xlsx"'
    return response