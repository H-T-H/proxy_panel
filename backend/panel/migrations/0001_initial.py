from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Setting",
            fields=[
                ("key", models.CharField(max_length=120, primary_key=True, serialize=False)),
                ("value", models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name="Source",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("url", models.TextField()),
                ("enabled", models.BooleanField(default=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True, null=True)),
            ],
            options={"ordering": ["-id"]},
        ),
        migrations.CreateModel(
            name="Node",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("type", models.CharField(max_length=50)),
                ("enabled", models.BooleanField(default=True)),
                ("tags", models.CharField(blank=True, max_length=200)),
                ("remark", models.TextField(blank=True)),
                ("raw_text", models.TextField(blank=True)),
                ("config", models.JSONField()),
                ("config_hash", models.CharField(max_length=64)),
                ("source_name", models.CharField(default="手动添加", max_length=200)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("source", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="nodes", to="panel.source")),
            ],
            options={"ordering": ["source_name", "name", "id"]},
        ),
        migrations.CreateModel(
            name="SubscriptionUser",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.CharField(max_length=120, unique=True)),
                ("token", models.CharField(max_length=64, unique=True)),
                ("enabled", models.BooleanField(default=True)),
                ("remark", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={"ordering": ["-id"]},
        ),
        migrations.CreateModel(
            name="UserNode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("node", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="user_nodes", to="panel.node")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="user_nodes", to="panel.subscriptionuser")),
            ],
        ),
        migrations.AddField(
            model_name="subscriptionuser",
            name="nodes",
            field=models.ManyToManyField(related_name="subscription_users", through="panel.UserNode", to="panel.node"),
        ),
        migrations.AddConstraint(
            model_name="node",
            constraint=models.UniqueConstraint(fields=("source", "config_hash"), name="uq_source_config_hash"),
        ),
        migrations.AddConstraint(
            model_name="usernode",
            constraint=models.UniqueConstraint(fields=("user", "node"), name="uq_user_node"),
        ),
    ]
