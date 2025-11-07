from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("curriculum", "0006_subject_avatar_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="module",
            name="image_url",
            field=models.URLField(blank=True, null=True),
        ),
    ]

