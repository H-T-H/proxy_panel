from django.db import models
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone


class Source(models.Model):
    name = models.CharField(max_length=120)
    url = models.TextField()
    enabled = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return self.name


class Node(models.Model):
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=50)
    enabled = models.BooleanField(default=True)
    tags = models.CharField(max_length=200, blank=True)
    remark = models.TextField(blank=True)
    raw_text = models.TextField(blank=True)
    config = models.JSONField()
    config_hash = models.CharField(max_length=64)
    source_name = models.CharField(max_length=200, default="手动添加")
    source = models.ForeignKey(Source, null=True, blank=True, related_name="nodes", on_delete=models.SET_NULL)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "config_hash"], name="uq_source_config_hash"),
        ]
        ordering = ["source_name", "name", "id"]

    @property
    def source_label(self):
        return self.source.name if self.source else (self.source_name or "手动添加")

    def __str__(self):
        return self.name


class SubscriptionUser(models.Model):
    username = models.CharField(max_length=120, unique=True)
    token = models.CharField(max_length=64, unique=True)
    password = models.CharField(max_length=128, blank=True)
    enabled = models.BooleanField(default=True)
    remark = models.TextField(blank=True)
    nodes = models.ManyToManyField(Node, through="UserNode", related_name="subscription_users")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return self.username

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)


class UserNode(models.Model):
    user = models.ForeignKey(SubscriptionUser, related_name="user_nodes", on_delete=models.CASCADE)
    node = models.ForeignKey(Node, related_name="user_nodes", on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "node"], name="uq_user_node"),
        ]


class Setting(models.Model):
    key = models.CharField(max_length=120, primary_key=True)
    value = models.TextField(blank=True)

    def __str__(self):
        return self.key


class ClientDownload(models.Model):
    DELIVERY_LINK = "link"
    DELIVERY_FILE = "file"
    DELIVERY_MODE_CHOICES = [
        (DELIVERY_LINK, "链接"),
        (DELIVERY_FILE, "客户端文件"),
    ]
    SOURCE_EXTERNAL_LINK = "external_link"
    SOURCE_LOCAL_FILE = "local_file"
    SOURCE_REMOTE_FETCH = "remote_fetch"
    SOURCE_TYPE_CHOICES = [
        (SOURCE_EXTERNAL_LINK, "外部链接"),
        (SOURCE_LOCAL_FILE, "本地上传"),
        (SOURCE_REMOTE_FETCH, "远程拉取"),
    ]
    PLATFORM_IOS = "ios"
    PLATFORM_MAC = "mac"
    PLATFORM_WINDOWS = "windows"
    PLATFORM_LINUX = "linux"
    PLATFORM_ANDROID = "android"
    PLATFORM_CHOICES = [
        (PLATFORM_IOS, "iOS"),
        (PLATFORM_MAC, "macOS"),
        (PLATFORM_WINDOWS, "Windows"),
        (PLATFORM_LINUX, "Linux"),
        (PLATFORM_ANDROID, "Android"),
    ]

    catalog_key = models.CharField(max_length=80, blank=True, db_index=True)
    name = models.CharField(max_length=120)
    platform_code = models.CharField(max_length=30, choices=PLATFORM_CHOICES, default=PLATFORM_IOS)
    platform = models.CharField(max_length=80, blank=True)
    version = models.CharField(max_length=80, blank=True)
    source_type = models.CharField(max_length=30, choices=SOURCE_TYPE_CHOICES, default=SOURCE_EXTERNAL_LINK)
    download_url = models.URLField(max_length=1000, blank=True)
    release_url = models.URLField(max_length=1000, blank=True)
    remote_url = models.URLField(max_length=1000, blank=True)
    auto_update_latest = models.BooleanField(default=False)
    delivery_mode = models.CharField(max_length=20, choices=DELIVERY_MODE_CHOICES, default=DELIVERY_LINK)
    last_fetched_at = models.DateTimeField(null=True, blank=True)
    last_fetch_error = models.TextField(blank=True)
    local_file = models.FileField(upload_to="client-downloads/", blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    enabled = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=100)
    remark = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name", "id"]

    def __str__(self):
        return self.name
