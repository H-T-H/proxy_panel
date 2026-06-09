from django.db import migrations


DEFAULT_TEMPLATE = """mixed-port: 7890
allow-lan: false
mode: rule
log-level: info
proxies: []
proxy-groups:
- name: Proxy
  type: select
  proxies:
  - __PROXIES__
rules:
- MATCH,Proxy
"""


def create_default_settings(apps, schema_editor):
    Setting = apps.get_model("panel", "Setting")
    Setting.objects.get_or_create(key="clash_template", defaults={"value": DEFAULT_TEMPLATE})


def remove_default_settings(apps, schema_editor):
    Setting = apps.get_model("panel", "Setting")
    Setting.objects.filter(key="clash_template", value=DEFAULT_TEMPLATE).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("panel", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_default_settings, remove_default_settings),
    ]
