from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("class_sessions", "0001_initial"),
        ("rewards", "0002_add_rewarditem_image_column"),
    ]

    operations = [
        migrations.AddField(
            model_name="rewardtransaction",
            name="session",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reward_transactions",
                to="class_sessions.classsession",
            ),
        ),
        migrations.CreateModel(
            name="SessionPointEvent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("ATTENDANCE", "Điểm danh"),
                            ("PRODUCT", "Sản phẩm"),
                            ("MANUAL", "Thủ công"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("note", models.CharField(blank=True, max_length=255)),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="point_events",
                        to="class_sessions.classsession",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="session_point_events",
                        to="accounts.user",
                    ),
                ),
                (
                    "transaction",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="session_point_events",
                        to="rewards.rewardtransaction",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="sessionpointevent",
            index=models.Index(
                fields=["student"], name="rewards_ses_student_02cacb_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="sessionpointevent",
            index=models.Index(fields=["session"], name="rewards_ses_session_9b7fa5_idx"),
        ),
        migrations.AddIndex(
            model_name="sessionpointevent",
            index=models.Index(
                fields=["event_type"], name="rewards_ses_event_t_56a512_idx"
            ),
        ),
        migrations.AlterUniqueTogether(
            name="sessionpointevent",
            unique_together={("student", "session", "event_type")},
        ),
    ]
