from django.db import migrations, models


def seed_catalog(apps, schema_editor):
    ClientDownload = apps.get_model("panel", "ClientDownload")
    catalog = [
        ("shadowrocket_ios", "Shadowrocket", "ios", "iOS", "App Store", "https://apps.apple.com/us/app/shadowrocket/id932747118", 10, "App Store"),
        ("stash_ios", "Stash", "ios", "iOS", "App Store", "https://apps.apple.com/us/app/stash-rule-based-proxy/id1596063349", 20, "App Store"),
        ("clash_verge_rev_mac", "Clash Verge Rev", "mac", "macOS", "", "https://github.com/clash-verge-rev/clash-verge-rev/releases/latest", 110, "macOS arm64"),
        ("mihomo_party_mac", "Mihomo Party", "mac", "macOS", "", "https://github.com/mihomo-party-org/mihomo-party/releases/latest", 120, "macOS arm64"),
        ("clash_verge_rev_linux", "Clash Verge Rev", "linux", "Linux", "", "https://github.com/clash-verge-rev/clash-verge-rev/releases/latest", 210, "Linux amd64"),
        ("mihomo_party_linux", "Mihomo Party", "linux", "Linux", "", "https://github.com/mihomo-party-org/mihomo-party/releases/latest", 220, "Linux amd64"),
        ("v2rayng_android", "v2rayNG", "android", "Android", "", "https://github.com/2dust/v2rayNG/releases/latest", 310, "APK"),
        ("clash_meta_android", "Clash Meta for Android", "android", "Android", "", "https://github.com/MetaCubeX/ClashMetaForAndroid/releases/latest", 320, "APK"),
    ]
    for key, name, platform_code, platform, version, url, sort_order, remark in catalog:
        item = ClientDownload.objects.filter(catalog_key=key).first()
        if not item:
            item = ClientDownload.objects.filter(catalog_key="", name=name, platform_code=platform_code).first()
        values = {
            "catalog_key": key,
            "name": name,
            "platform_code": platform_code,
            "platform": platform,
            "version": version,
            "source_type": "external_link",
            "delivery_mode": "link",
            "download_url": url,
            "release_url": url,
            "remote_url": "",
            "auto_update_latest": True,
            "sort_order": sort_order,
            "remark": remark,
        }
        if item:
            for field, value in values.items():
                setattr(item, field, value)
            item.enabled = True
            item.save()
        else:
            ClientDownload.objects.create(**values, enabled=True)


class Migration(migrations.Migration):

    dependencies = [
        ("panel", "0007_clientdownload_platform_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientdownload",
            name="catalog_key",
            field=models.CharField(blank=True, db_index=True, max_length=80),
        ),
        migrations.AddField(
            model_name="clientdownload",
            name="delivery_mode",
            field=models.CharField(
                choices=[("link", "链接"), ("file", "客户端文件")],
                default="link",
                max_length=20,
            ),
        ),
        migrations.RunPython(seed_catalog, migrations.RunPython.noop),
    ]
