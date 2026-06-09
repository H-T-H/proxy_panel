from django.db import migrations, models


DEFAULT_DOWNLOADS = [
    {
        "name": "Clash Verge Rev",
        "platform": "Windows / macOS / Linux",
        "version": "请在后台更新",
        "download_url": "https://github.com/clash-verge-rev/clash-verge-rev/releases/latest",
        "release_url": "https://github.com/clash-verge-rev/clash-verge-rev/releases/latest",
        "sort_order": 10,
    },
    {
        "name": "Mihomo Party",
        "platform": "Windows / macOS / Linux",
        "version": "请在后台更新",
        "download_url": "https://github.com/mihomo-party-org/mihomo-party/releases/latest",
        "release_url": "https://github.com/mihomo-party-org/mihomo-party/releases/latest",
        "sort_order": 20,
    },
    {
        "name": "Stash",
        "platform": "iOS / macOS",
        "version": "App Store",
        "download_url": "https://apps.apple.com/app/stash-rule-based-proxy/id1596063349",
        "release_url": "https://apps.apple.com/app/stash-rule-based-proxy/id1596063349",
        "sort_order": 30,
    },
    {
        "name": "Shadowrocket",
        "platform": "iOS",
        "version": "App Store",
        "download_url": "https://apps.apple.com/app/shadowrocket/id932747118",
        "release_url": "https://apps.apple.com/app/shadowrocket/id932747118",
        "sort_order": 40,
    },
]


def seed_client_downloads(apps, schema_editor):
    Setting = apps.get_model("panel", "Setting")
    ClientDownload = apps.get_model("panel", "ClientDownload")
    Setting.objects.update_or_create(key="client_downloads_enabled", defaults={"value": "true"})
    for item in DEFAULT_DOWNLOADS:
        ClientDownload.objects.get_or_create(name=item["name"], platform=item["platform"], defaults=item)


class Migration(migrations.Migration):
    dependencies = [
        ("panel", "0003_subscriptionuser_password"),
    ]

    operations = [
        migrations.CreateModel(
            name="ClientDownload",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("platform", models.CharField(blank=True, max_length=80)),
                ("version", models.CharField(blank=True, max_length=80)),
                ("download_url", models.URLField(max_length=1000)),
                ("release_url", models.URLField(blank=True, max_length=1000)),
                ("enabled", models.BooleanField(default=True)),
                ("sort_order", models.PositiveIntegerField(default=100)),
                ("remark", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["sort_order", "name", "id"],
            },
        ),
        migrations.RunPython(seed_client_downloads, migrations.RunPython.noop),
    ]
