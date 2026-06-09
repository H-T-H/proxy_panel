from django.db import migrations, models


def backfill_platform_codes(apps, schema_editor):
    ClientDownload = apps.get_model("panel", "ClientDownload")
    for item in ClientDownload.objects.all():
        text = (item.platform or item.name or "").lower()
        if "android" in text:
            item.platform_code = "android"
        elif "linux" in text:
            item.platform_code = "linux"
        elif "mac" in text:
            item.platform_code = "mac"
        else:
            item.platform_code = "ios"
        item.save(update_fields=["platform_code"])


class Migration(migrations.Migration):
    dependencies = [
        ("panel", "0006_clientdownload_sources"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientdownload",
            name="platform_code",
            field=models.CharField(
                choices=[
                    ("ios", "iOS"),
                    ("mac", "macOS"),
                    ("linux", "Linux"),
                    ("android", "Android"),
                ],
                default="ios",
                max_length=30,
            ),
        ),
        migrations.RunPython(backfill_platform_codes, migrations.RunPython.noop),
    ]
