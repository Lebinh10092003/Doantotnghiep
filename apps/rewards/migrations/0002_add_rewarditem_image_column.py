from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("rewards", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE rewards_rewarditem ADD COLUMN IF NOT EXISTS image varchar(100);",
            reverse_sql="ALTER TABLE rewards_rewarditem DROP COLUMN IF EXISTS image;",
        ),
    ]
