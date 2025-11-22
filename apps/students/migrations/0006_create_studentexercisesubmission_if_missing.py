from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("students", "0005_alter_studentexercisesubmission_file"),
        ("curriculum", "0001_initial"),
        ("class_sessions", "0001_initial"),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS students_studentexercisesubmission (
                id BIGSERIAL PRIMARY KEY,
                exercise_id BIGINT NOT NULL REFERENCES curriculum_exercise(id) DEFERRABLE INITIALLY DEFERRED,
                session_id BIGINT NULL REFERENCES class_sessions_classsession(id) DEFERRABLE INITIALLY DEFERRED,
                student_id BIGINT NOT NULL REFERENCES accounts_user(id) DEFERRABLE INITIALLY DEFERRED,
                title VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                file VARCHAR(100) NULL,
                link_url VARCHAR(200) NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            """,
            reverse_sql="""
            -- Không xóa bảng khi rollback để tránh mất dữ liệu
            """,
        ),
    ]
