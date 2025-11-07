from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("curriculum", "0004_alter_exercise_lesson"),
    ]

    operations = [
        migrations.AddField(
            model_name="exercise",
            name="link_url",
            field=models.URLField(blank=True, null=True),
        ),
    ]

