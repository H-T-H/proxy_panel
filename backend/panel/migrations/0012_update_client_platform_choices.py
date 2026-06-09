from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("panel", "0011_add_windows_clients"),
    ]

    operations = [
        migrations.AlterField(
            model_name="clientdownload",
            name="platform_code",
            field=models.CharField(
                choices=[
                    ("ios", "iOS"),
                    ("mac", "macOS"),
                    ("windows", "Windows"),
                    ("linux", "Linux"),
                    ("android", "Android"),
                ],
                default="ios",
                max_length=30,
            ),
        ),
    ]
