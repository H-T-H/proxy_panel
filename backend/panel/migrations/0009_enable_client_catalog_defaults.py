import json

from django.db import migrations


def enable_client_defaults(apps, schema_editor):
    ClientDownload = apps.get_model("panel", "ClientDownload")
    Setting = apps.get_model("panel", "Setting")
    ClientDownload.objects.exclude(catalog_key="").update(enabled=True)
    Setting.objects.update_or_create(key="client_downloads_enabled", defaults={"value": "true"})
    Setting.objects.update_or_create(
        key="client_download_platforms_enabled",
        defaults={"value": json.dumps({"ios": True, "mac": True, "linux": True, "android": True})},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("panel", "0008_clientdownload_catalog"),
    ]

    operations = [
        migrations.RunPython(enable_client_defaults, migrations.RunPython.noop),
    ]
