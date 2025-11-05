import json
from datetime import timedelta
from pyexpat.errors import messages
from django.utils.dateparse import parse_date
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import Group
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator, EmptyPage
from django.template.loader import render_to_string
from django.db.models import Q, Count
from apps.centers.models import Center
from apps.classes.models import Class
from .models import ParentStudentRelation
from .forms import AdminUserCreateForm, AdminUserUpdateForm, ImportUserForm,UserProfileUpdateForm,UserPasswordChangeForm
from .resources import UserResource
from tablib import Dataset
from .forms import SimpleGroupForm
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from collections import defaultdict
from django.contrib.auth import update_session_auth_hash 
from django import forms as dj_forms
User = get_user_model()

# 
def is_htmx_request(request):
    return (
        request.headers.get("HX-Request") == "true"
        or request.META.get("HTTP_HX_REQUEST") == "true"
        or bool(getattr(request, "htmx", False))
    )

# Đăng nhập và đăng xuất
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

# Kiểm tra quyền admin
def is_admin(user):
    return user.is_superuser or getattr(user, "role", None) == "ADMIN"
# Lọc queryset người dùng dựa trên tham số request
def _filter_users_queryset(request):
    current_user = request.user
    # Kiểm tra xem người dùng có thuộc các nhóm vai trò cụ thể hay không
    is_parent = current_user.groups.filter(name='PARENT').exists()
    is_student = current_user.groups.filter(name='STUDENT').exists()

    # Bắt đầu với một queryset cơ sở dựa trên quyền của người dùng
    if is_parent:
        # Phụ huynh chỉ thấy danh sách con của mình
        children_ids = ParentStudentRelation.objects.filter(parent=current_user).values_list('student_id', flat=True)
        qs = User.objects.filter(id__in=list(children_ids))
    elif is_student:
        # Học sinh chỉ thấy chính mình
        qs = User.objects.filter(pk=current_user.pk)
    else:
        # Các vai trò khác (Admin, Manager, Staff, Teacher,...) không bị giới hạn
        qs = User.objects.all()
    
    # Áp dụng các bộ lọc bổ sung trên queryset cơ sở
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
    if is_staff: # is_staff will be a string or None. If it's an empty string, it evaluates to False.
        v = is_staff.lower()
        if v in ("1", "true", "yes", "on"):
            qs = qs.filter(is_staff=True)
        elif v in ("0", "false", "no"):
            qs = qs.filter(is_staff=False)

    if is_superuser: # Same logic for is_superuser
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
    
    return qs.select_related("center").prefetch_related("groups").distinct()

# Quản lý người dùng
@login_required
@permission_required("accounts.view_user", raise_exception=True)
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
        # Sắp xếp theo tên của nhóm đầu tiên để `regroup` hoạt động chính xác khi nhóm theo vai trò
        qs = qs.order_by("groups__name", "last_name", "first_name").distinct()
    elif group_by == "group": # group_by=group không được sử dụng trong template, nhưng để lại cho nhất quán
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


def _form_errors_as_text(form) -> str:
    """
    Trả lỗi dạng text, mỗi lỗi một dòng.
    Hỗ trợ cả field errors và non-field errors.
    """
    parts = []

    # Field errors
    for field_name, error_list in form.errors.items():  # error_list là ErrorList
        if field_name == dj_forms.forms.NON_FIELD_ERRORS:
            continue
        label = getattr(form.fields.get(field_name), "label", field_name)
        for err in error_list:  # ErrorList có thể lặp
            parts.append(f"{label}: {err}")

    # Non-field errors
    for err in form.non_field_errors():
        parts.append(str(err))

    # Loại bỏ trùng lặp, giữ thứ tự
    uniq = list(dict.fromkeys(parts))
    return "\n".join(uniq) if uniq else "Dữ liệu không hợp lệ."
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
            "text": _form_errors_as_text(form),
            "showConfirmButton": True
        }
    })
    return resp



@require_POST
@login_required
@permission_required("accounts.delete_user", raise_exception=True)
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
            # Lấy số lượng user sẽ bị xóa TRƯỚC KHI thực hiện xóa
            count_to_delete = users_to_delete_qs.count()
            # Lấy thông tin user trước khi xóa
            if original_count == 1 and user_ids_to_delete:
                user_instance = users_to_delete_qs.first()
                if user_instance:
                    deleted_users_info.append(user_instance.username)

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
                    "title": f"Đã vô hiệu hóa người dùng '{deleted_users_info[0]}' thành công."
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
        "closeUserModal": True, # Đóng modal chi tiết nếu xóa từ đó
        "show-sweet-alert": alert
    })
    return response

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

    if user_role_upper == 'TEACHER' or user_role_upper == 'ASSISTANT':
        # Lấy các lớp giáo viên đang dạy (giáo viên chính)
        if hasattr(user, 'main_classes'):
            teaching_classes = user.main_classes.select_related('subject', 'center').all()
        else:
            teaching_classes = Class.objects.filter(main_teacher=user).select_related('subject', 'center')

        # Lấy các lớp trợ giảng
        if hasattr(user, 'assist_classes'):
            assisting_classes = user.assist_classes.select_related('subject', 'center').all()
        else:
            assisting_classes = Class.objects.filter(assistants=user).select_related('subject', 'center')

    context = {
        'user': user,
        'children': children,
        'parents': parents,
        'enrolled_classes': enrolled_classes,
        'teaching_classes': teaching_classes,
        'assisting_classes': assisting_classes,
    }
    return render(request, '_user_detail.html', context)

@login_required
@permission_required("accounts.change_user", raise_exception=True)
def user_edit_view(request, user_id):
    u = get_object_or_404(User, id=user_id)
    if request.method == "GET":
        form = AdminUserUpdateForm(instance=u)
        return render(request, "_edit_user_form.html", {"form": form, "user": u})

    form = AdminUserUpdateForm(request.POST, request.FILES, instance=u)
    if form.is_valid():
        form.save()
        resp = HttpResponse(status=200)
        resp["HX-Trigger"] = json.dumps({
            "reload-accounts-table": True,
            "closeUserModal": True,
            "show-sweet-alert": {
                "icon": "success",
                "title": "Thành công",
                "text": f"Đã cập nhật: {u.username}",
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
            "title": "Không thể cập nhật",
            "text": _form_errors_as_text(form),
            "showConfirmButton": True
        }
    })
    return resp


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
            return render(request, '_import_users_form.html', {'form': form, 'errors': errors}, status=422)

    else:
        form = ImportUserForm()
        return render(request, '_import_users_form.html', {'form': form})

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
def _group_permissions_by_functionality(permissions_qs):
    """
    Nhóm quyền theo chức năng dựa trên model và codename.
    Trả về dict: {'Tên Chức Năng': [(permission_id, 'Label rõ ràng'), ...]}
    """
    grouped = {}
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
        "Quản lý Tài chính (Billing)": [], # Thêm model khi có
        "Quản lý Báo cáo": [], # Thêm model khi có
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

        action = ""
        if perm.codename.startswith('add_'):
            action = "Tạo mới"
        elif perm.codename.startswith('change_'):
            action = "Chỉnh sửa"
        elif perm.codename.startswith('delete_'):
            action = "Xóa"
        elif perm.codename.startswith('view_'):
            action = "Xem"
        else:
            action = perm.codename.replace('_', ' ').capitalize() # Xử lý codename tùy chỉnh

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
        grouped[group_name].append((perm.id, clear_label))

    # Sắp xếp lại dict theo thứ tự functional_groups
    ordered_grouped = {name: grouped.get(name, []) for name in functional_groups if name in grouped}
    if "Chức năng Khác" in grouped:
         ordered_grouped["Chức năng Khác"] = grouped["Chức năng Khác"]

    return ordered_grouped


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
    }

    if is_htmx_request(request):
        return render(request, "_groups_table.html", context)

    return render(request, "manage_groups.html", context)


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
            context = {'form': form, 'functional_grouped_permissions': functional_grouped_permissions}
            return render(request, '_group_form.html', context, status=422)
    else: # GET
        form = SimpleGroupForm()
        all_permissions = Permission.objects.all()
        functional_grouped_permissions = _group_permissions_by_functionality(all_permissions)
        context = {'form': form, 'functional_grouped_permissions': functional_grouped_permissions}
        return render(request, '_group_form.html', context)


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
            context = {'form': form, 'group': group, 'functional_grouped_permissions': functional_grouped_permissions}
            return render(request, '_group_form.html', context, status=422)
    else: # GET
        form = SimpleGroupForm(instance=group)
        all_permissions = Permission.objects.all()
        functional_grouped_permissions = _group_permissions_by_functionality(all_permissions)
        context = {'form': form, 'group': group, 'functional_grouped_permissions': functional_grouped_permissions}
        return render(request, '_group_form.html', context)


@require_POST
@login_required
@permission_required("auth.delete_group", raise_exception=True)
def group_delete_view(request):
    # Lấy ID từ cả xóa hàng loạt (checkbox) và xóa đơn (input ẩn)
    group_ids = request.POST.getlist('group_ids[]') or request.POST.getlist('group_id_single')
    # Loại bỏ các ID trùng lặp
    unique_group_ids = list(set(group_ids))
    alert = {} # Khởi tạo alert

    if not unique_group_ids:
        alert = {"icon": "info", "title": "Không có nhóm nào được chọn."}
    else:
        try:
            group_ids_int = [int(gid) for gid in unique_group_ids]
            groups_to_delete_qs = Group.objects.filter(id__in=group_ids_int)

            # Lấy tên các nhóm TRƯỚC KHI xóa để hiển thị trong thông báo
            deleted_names = []
            for group in groups_to_delete_qs:
                deleted_names.append(group.name)

            deleted_count = len(deleted_names)
            if deleted_count > 0:
                groups_to_delete_qs.delete()

            if deleted_count > 0:
                if deleted_count == 1:
                    alert = {"icon": "success", "title": f"Đã xóa nhóm '{deleted_names[0]}' thành công."}
                else:
                    # Tạo thông báo chi tiết
                    deleted_list_str = ", ".join([f"'{name}'" for name in deleted_names])
                    alert = {
                        "icon": "success", 
                        "title": f"Đã xóa {deleted_count} nhóm thành công.",
                        "text": f"Các nhóm đã xóa: {deleted_list_str}"
                    }
            else:
                alert = {"icon": "info", "title": "Không có nhóm nào được xóa."}

        except ValueError:
            alert = {"icon": "error", "title": "ID nhóm không hợp lệ."}
        except Exception as e:
            alert = {"icon": "error", "title": "Lỗi máy chủ", "text": str(e)}

    response = HttpResponse(status=200)
    response['HX-Trigger'] = json.dumps({
        "reload-groups-table": True,
        "closeGroupModal": True,
        "show-sweet-alert": alert
    })
    return response

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
            # Nếu form không hợp lệ, render lại form edit với lỗi
            return render(request, '_profile_form_edit.html', {'form': form}, status=422)

    # Xử lý GET request (tải trang lần đầu hoặc bấm nút "Hủy")
    # Mặc định là hiển thị thông tin "chỉ xem"
    if is_htmx_request(request):
        return render(request, '_profile_detail.html', {'user': user})

    context = {
        'user': user,
        'password_form': UserPasswordChangeForm(user=user),
    }
    return render(request, 'profile.html', context)

@login_required
def profile_edit_view(request):
    # View này chỉ để trả về form chỉnh sửa khi người dùng bấm nút "Chỉnh sửa"
    form = UserProfileUpdateForm(instance=request.user)
    return render(request, '_profile_form_edit.html', {'form': form})

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
