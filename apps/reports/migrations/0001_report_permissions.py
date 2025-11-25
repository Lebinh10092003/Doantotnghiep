from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ReportPermission",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                )
            ],
            options={
                "managed": False,
                "default_permissions": (),
                "permissions": [
                    ("view_enrollment_report", "Can view enrollment reports"),
                    ("view_student_report", "Can view student reports"),
                    ("view_revenue_report", "Can view revenue reports"),
                    ("view_teaching_hours_report", "Can view teaching hours reports"),
                    ("view_class_activity_report", "Can view class activity reports"),
                ],
                "verbose_name": "Report permission",
                "verbose_name_plural": "Report permissions",
            },
        ),
    ]
