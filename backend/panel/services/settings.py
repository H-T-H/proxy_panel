from panel.models import Setting

from .subscription import default_template_text


def get_setting(key, default=""):
    try:
        return Setting.objects.get(pk=key).value
    except Setting.DoesNotExist:
        return default


def set_setting(key, value):
    Setting.objects.update_or_create(key=key, defaults={"value": value})


def ensure_default_settings():
    setting, _ = Setting.objects.get_or_create(key="clash_template", defaults={"value": default_template_text()})
    if not setting.value:
        setting.value = default_template_text()
        setting.save(update_fields=["value"])
