from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("curriculum", "0005_exercise_link_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="subject",
            name="avatar_url",
            field=models.URLField(blank=True, null=True),
        ),
    ]

