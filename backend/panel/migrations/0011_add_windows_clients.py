import json

from django.db import migrations


def add_windows_clients(apps, schema_editor):
    ClientDownload = apps.get_model("panel", "ClientDownload")
    Setting = apps.get_model("panel", "Setting")
    catalog = [
        (
            "clash_verge_rev_windows",
            "Clash Verge Rev",
            "windows",
            "Windows",
            "https://github.com/clash-verge-rev/clash-verge-rev/releases/latest",
            210,
            "Windows amd64",
        ),
        (
            "mihomo_party_windows",
            "Mihomo Party",
            "windows",
            "Windows",
            "https://github.com/mihomo-party-org/mihomo-party/releases/latest",
            220,
            "Windows amd64",
        ),
    ]
    for key, name, platform_code, platform, url, sort_order, remark in catalog:
        ClientDownload.objects.update_or_create(
            catalog_key=key,
            defaults={
                "name": name,
                "platform_code": platform_code,
                "platform": platform,
                "source_type": "external_link",
                "delivery_mode": "link",
                "download_url": url,
                "release_url": url,
                "remote_url": "",
                "auto_update_latest": True,
                "enabled": True,
                "sort_order": sort_order,
                "remark": remark,
            },
        )

    setting, _ = Setting.objects.get_or_create(key="client_download_platforms_enabled", defaults={"value": "{}"})
    try:
        platforms = json.loads(setting.value or "{}")
    except json.JSONDecodeError:
        platforms = {}
    platforms["windows"] = True
    setting.value = json.dumps(platforms)
    setting.save(update_fields=["value"])


class Migration(migrations.Migration):

    dependencies = [
        ("panel", "0010_remove_nekobox_client"),
    ]

    operations = [
        migrations.RunPython(add_windows_clients, migrations.RunPython.noop),
    ]
