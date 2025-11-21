from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("enrollments", "0005_enrollment_tuition_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="EnrollmentStatusLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("old_status", models.CharField(blank=True, max_length=20)),
                ("new_status", models.CharField(max_length=20)),
                ("reason", models.CharField(blank=True, max_length=50)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("enrollment", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="status_logs", to="enrollments.enrollment")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
