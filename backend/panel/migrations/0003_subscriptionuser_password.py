from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("panel", "0002_default_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscriptionuser",
            name="password",
            field=models.CharField(blank=True, max_length=128),
        ),
    ]
