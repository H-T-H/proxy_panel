from django.db import migrations


def remove_nekobox(apps, schema_editor):
    ClientDownload = apps.get_model("panel", "ClientDownload")
    ClientDownload.objects.filter(catalog_key="nekobox_android").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("panel", "0009_enable_client_catalog_defaults"),
    ]

    operations = [
        migrations.RunPython(remove_nekobox, migrations.RunPython.noop),
    ]
