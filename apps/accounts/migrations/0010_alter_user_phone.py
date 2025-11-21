from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0009_alter_user_avatar"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="phone",
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
