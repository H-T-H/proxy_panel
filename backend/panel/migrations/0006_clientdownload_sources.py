from django.db import migrations, models


def backfill_source_types(apps, schema_editor):
    ClientDownload = apps.get_model("panel", "ClientDownload")
    for item in ClientDownload.objects.all():
        item.source_type = "local_file" if item.local_file else "external_link"
        item.save(update_fields=["source_type"])


class Migration(migrations.Migration):
    dependencies = [
        ("panel", "0005_clientdownload_local_file"),
    ]

    operations = [
        migrations.AddField(
            model_name="clientdownload",
            name="source_type",
            field=models.CharField(
                choices=[
                    ("external_link", "外部链接"),
                    ("local_file", "本地上传"),
                    ("remote_fetch", "远程拉取"),
                ],
                default="external_link",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="clientdownload",
            name="remote_url",
            field=models.URLField(blank=True, max_length=1000),
        ),
        migrations.AddField(
            model_name="clientdownload",
            name="auto_update_latest",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="clientdownload",
            name="last_fetched_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="clientdownload",
            name="last_fetch_error",
            field=models.TextField(blank=True),
        ),
        migrations.RunPython(backfill_source_types, migrations.RunPython.noop),
    ]
