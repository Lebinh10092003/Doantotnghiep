from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from apps.centers.models import Center

User = get_user_model()

class UserResource(resources.ModelResource):
    # Sử dụng widget để import/export các trường quan hệ theo tên thay vì ID
    center = fields.Field(
        column_name='center',
        attribute='center',
        widget=ForeignKeyWidget(Center, 'name'))

    groups = fields.Field(
        column_name='groups',
        attribute='groups',
        widget=ManyToManyWidget(Group, separator=', ', field='name'))

    class Meta:
        model = User
        # Các trường sẽ được import/export.
        # Bỏ qua 'password' để không export hash password.
        fields = ('id', 'username', 'first_name', 'last_name', 'email', 'phone', 'is_active', 'is_staff', 'center', 'groups')
        # Các trường chỉ để export, không dùng để import
        export_order = fields
        # Khi import, nếu một dòng dữ liệu đã tồn tại, bỏ qua không cập nhật
        skip_unchanged = True
        # Báo cáo các dòng đã bỏ qua
        report_skipped = True
        # Sử dụng 'username' làm khóa chính để tìm và cập nhật người dùng khi import
        import_id_fields = ('username',)

    # Xử lý mật khẩu khi import
    def before_save_instance(self, instance, using_transactions, dry_run):
        # Nếu là người dùng mới (chưa có id), đặt mật khẩu mặc định.
        if not instance.pk:
            instance.set_password('123456') # Mật khẩu mặc định cho user mới
        if hasattr(instance, '_m2m_data') and 'groups' in instance._m2m_data:
            group_names = instance._m2m_data['groups']
            if group_names:
                instance.role = group_names[0]