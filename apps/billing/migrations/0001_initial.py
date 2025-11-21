from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("enrollments", "0005_enrollment_tuition_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="BillingEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("entry_type", models.CharField(choices=[("PURCHASE", "Purchase"), ("CONSUME", "Consume"), ("ADJUST", "Adjust")], max_length=20)),
                ("amount", models.DecimalField(decimal_places=0, default=0, help_text="Amount in VND", max_digits=12)),
                ("sessions", models.IntegerField(default=0, help_text="Positive for purchase/adjust up, negative for consume/adjust down")),
                ("note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("enrollment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="billing_entries", to="enrollments.enrollment")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
