from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Discount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=50, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("percent", models.DecimalField(decimal_places=2, default=0, help_text="Giảm % (0-100)", max_digits=5)),
                ("amount", models.DecimalField(decimal_places=0, default=0, help_text="Giảm cố định (VND)", max_digits=12)),
                ("max_amount", models.DecimalField(blank=True, decimal_places=0, help_text="Trần giảm giá (VND)", max_digits=12, null=True)),
                ("active", models.BooleanField(default=True)),
                ("start_date", models.DateField(blank=True, null=True)),
                ("end_date", models.DateField(blank=True, null=True)),
                ("usage_limit", models.PositiveIntegerField(blank=True, help_text="Số lần dùng tối đa", null=True)),
                ("usage_count", models.PositiveIntegerField(default=0)),
                ("note", models.CharField(blank=True, max_length=255)),
            ],
            options={
                "ordering": ["code"],
            },
        ),
        migrations.AddField(
            model_name="billingentry",
            name="discount_amount",
            field=models.DecimalField(decimal_places=0, default=0, help_text="Số tiền giảm cho entry này", max_digits=12),
        ),
        migrations.AddField(
            model_name="billingentry",
            name="unit_price",
            field=models.DecimalField(decimal_places=0, default=0, help_text="Đơn giá áp dụng (VND/buổi) sau giảm", max_digits=12),
        ),
        migrations.AddField(
            model_name="billingentry",
            name="discount",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="billing_entries", to="billing.discount"),
        ),
    ]
