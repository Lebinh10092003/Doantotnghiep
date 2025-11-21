from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("enrollments", "0004_rename_enrollments_status_b2a39f_idx_enrollments_status_48622c_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="enrollment",
            name="amount_paid",
            field=models.DecimalField(decimal_places=0, default=0, help_text="Số tiền đã đóng (VND, nếu nhập tiền sẽ tự tính buổi)", max_digits=12),
        ),
        migrations.AddField(
            model_name="enrollment",
            name="fee_per_session",
            field=models.DecimalField(decimal_places=0, default=300000, help_text="Đơn giá mỗi buổi (VND)", max_digits=12),
        ),
        migrations.AddField(
            model_name="enrollment",
            name="sessions_consumed",
            field=models.PositiveIntegerField(default=0, help_text="Số buổi đã sử dụng (tự động tính từ điểm danh)"),
        ),
        migrations.AddField(
            model_name="enrollment",
            name="sessions_purchased",
            field=models.PositiveIntegerField(default=0, help_text="Số buổi mua (nếu nhập số buổi)"),
        ),
    ]
