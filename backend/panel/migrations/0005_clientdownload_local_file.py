from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("panel", "0004_clientdownload"),
    ]

    operations = [
        migrations.AlterField(
            model_name="clientdownload",
            name="download_url",
            field=models.URLField(blank=True, max_length=1000),
        ),
        migrations.AddField(
            model_name="clientdownload",
            name="local_file",
            field=models.FileField(blank=True, upload_to="client-downloads/"),
        ),
        migrations.AddField(
            model_name="clientdownload",
            name="file_name",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
