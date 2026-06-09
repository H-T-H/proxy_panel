from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import ClientDownload, Node, Setting, Source, SubscriptionUser, UserNode
from .services.proxy_parser import parse_manual_node, normalize_proxy
from .services.subscription import config_hash, new_token, validate_template


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)

    def validate(self, attrs):
        user = authenticate(username=attrs["username"], password=attrs["password"])
        if not user:
            raise serializers.ValidationError("用户名或密码错误")
        if not user.is_active:
            raise serializers.ValidationError("账号已停用")
        if not user.is_staff:
            raise serializers.ValidationError("该账号没有后台管理权限")
        attrs["user"] = user
        return attrs


class SourceSerializer(serializers.ModelSerializer):
    node_count = serializers.IntegerField(source="nodes.count", read_only=True)

    class Meta:
        model = Source
        fields = ["id", "name", "url", "enabled", "last_synced_at", "last_error", "node_count"]


class ClientDownloadSerializer(serializers.ModelSerializer):
    upload_file = serializers.FileField(write_only=True, required=False)
    clear_file = serializers.BooleanField(write_only=True, required=False)
    has_local_file = serializers.SerializerMethodField()
    local_file_url = serializers.SerializerMethodField()
    file_available = serializers.SerializerMethodField()
    icon_url = serializers.SerializerMethodField()

    class Meta:
        model = ClientDownload
        fields = [
            "id",
            "catalog_key",
            "name",
            "platform_code",
            "platform",
            "version",
            "source_type",
            "delivery_mode",
            "download_url",
            "release_url",
            "remote_url",
            "auto_update_latest",
            "last_fetched_at",
            "last_fetch_error",
            "upload_file",
            "clear_file",
            "has_local_file",
            "local_file_url",
            "file_available",
            "icon_url",
            "file_name",
            "enabled",
            "sort_order",
            "remark",
            "updated_at",
        ]
        read_only_fields = [
            "catalog_key",
            "name",
            "platform_code",
            "platform",
            "version",
            "source_type",
            "download_url",
            "release_url",
            "remote_url",
            "auto_update_latest",
            "has_local_file",
            "local_file_url",
            "file_available",
            "icon_url",
            "file_name",
            "last_fetched_at",
            "last_fetch_error",
            "sort_order",
            "remark",
            "updated_at",
        ]

    def get_has_local_file(self, obj):
        return bool(obj.local_file)

    def get_local_file_url(self, obj):
        if not obj.local_file:
            return ""
        request = self.context.get("request")
        path = f"/api/client-downloads/{obj.id}/file/"
        return request.build_absolute_uri(path) if request else path

    def get_file_available(self, obj):
        from .services.client_catalog import catalog_for

        catalog = catalog_for(obj)
        return bool(catalog and catalog.get("file_available"))

    def get_icon_url(self, obj):
        from .services.client_catalog import catalog_for

        catalog = catalog_for(obj)
        return catalog.get("icon_url", "") if catalog else ""

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        if instance and instance.catalog_key:
            if attrs.get("upload_file") and not self.get_file_available(instance):
                raise serializers.ValidationError("该客户端只能提供 App Store 链接")
            return attrs
        source_type = attrs.get("source_type", instance.source_type if instance else ClientDownload.SOURCE_EXTERNAL_LINK)
        upload_file = attrs.get("upload_file")
        has_existing_file = bool(instance and instance.local_file)
        download_url = attrs.get("download_url", instance.download_url if instance else "")
        remote_url = attrs.get("remote_url", instance.remote_url if instance else "")
        if source_type == ClientDownload.SOURCE_EXTERNAL_LINK and not download_url:
            raise serializers.ValidationError("外部链接来源必须填写客户端链接")
        if source_type == ClientDownload.SOURCE_LOCAL_FILE and not upload_file and not has_existing_file:
            raise serializers.ValidationError("本地上传来源必须上传文件")
        if source_type == ClientDownload.SOURCE_REMOTE_FETCH and not remote_url and not has_existing_file:
            raise serializers.ValidationError("远程拉取来源必须填写远程地址或先完成拉取")
        return attrs

    def create(self, validated_data):
        upload_file = validated_data.pop("upload_file", None)
        item = super().create(validated_data)
        if upload_file:
            item.local_file = upload_file
            item.file_name = upload_file.name
            item.save(update_fields=["local_file", "file_name", "updated_at"])
        return item

    def update(self, instance, validated_data):
        clear_file = validated_data.pop("clear_file", False)
        upload_file = validated_data.pop("upload_file", None)
        item = super().update(instance, validated_data)
        if clear_file and item.local_file:
            item.local_file.delete(save=False)
            item.local_file = ""
            item.file_name = ""
            item.delivery_mode = ClientDownload.DELIVERY_LINK
            item.source_type = ClientDownload.SOURCE_EXTERNAL_LINK
            item.save(update_fields=["local_file", "file_name", "delivery_mode", "source_type", "updated_at"])
        if upload_file:
            if item.local_file:
                item.local_file.delete(save=False)
            item.local_file = upload_file
            item.file_name = upload_file.name
            item.delivery_mode = ClientDownload.DELIVERY_FILE
            item.source_type = ClientDownload.SOURCE_LOCAL_FILE
            item.save(update_fields=["local_file", "file_name", "delivery_mode", "source_type", "updated_at"])
        return item


class NodeSerializer(serializers.ModelSerializer):
    source_label = serializers.CharField(read_only=True)
    source = serializers.PrimaryKeyRelatedField(queryset=Source.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Node
        fields = [
            "id",
            "name",
            "type",
            "enabled",
            "tags",
            "remark",
            "raw_text",
            "config",
            "config_hash",
            "source",
            "source_name",
            "source_label",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["config_hash", "source_name", "source_label", "created_at", "updated_at"]
        extra_kwargs = {
            "name": {"required": False},
            "type": {"required": False},
        }

    def validate_config(self, value):
        return normalize_proxy(value)

    def create(self, validated_data):
        config = validated_data["config"]
        validated_data["name"] = config["name"]
        validated_data["type"] = config["type"]
        validated_data["config_hash"] = config_hash(config)
        source = validated_data.get("source")
        validated_data["source_name"] = source.name if source else "手动添加"
        return super().create(validated_data)

    def update(self, instance, validated_data):
        config = validated_data.get("config")
        if config:
            validated_data["name"] = config["name"]
            validated_data["type"] = config["type"]
            validated_data["config_hash"] = config_hash(config)
        elif "name" in validated_data:
            merged = dict(instance.config)
            merged["name"] = validated_data["name"]
            validated_data["config"] = merged
        return super().update(instance, validated_data)


class ManualNodeSerializer(serializers.Serializer):
    node_text = serializers.CharField()

    def validate_node_text(self, value):
        self.config = parse_manual_node(value.strip())
        return value


class BulkIdsSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False)


class BulkNodeStateSerializer(BulkIdsSerializer):
    enabled = serializers.BooleanField()


class TemplatePreviewSerializer(serializers.Serializer):
    template = serializers.CharField(required=False, allow_blank=True)
    node_order_keywords = serializers.CharField(required=False, allow_blank=True)
    user_id = serializers.IntegerField(required=False, min_value=1)
    node_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )

    def validate(self, attrs):
        if attrs.get("user_id") and "node_ids" in attrs:
            raise serializers.ValidationError("user_id 和 node_ids 只能选择一种预览方式")
        return attrs


class UserNodeSerializer(serializers.ModelSerializer):
    node_name = serializers.CharField(source="node.name", read_only=True)
    node_type = serializers.CharField(source="node.type", read_only=True)

    class Meta:
        model = UserNode
        fields = ["id", "node", "node_name", "node_type"]


class SubscriptionUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        trim_whitespace=False,
    )
    node_ids = serializers.PrimaryKeyRelatedField(
        source="nodes",
        many=True,
        queryset=Node.objects.all(),
        required=False,
    )
    node_count = serializers.IntegerField(source="nodes.count", read_only=True)
    subscription_path = serializers.SerializerMethodField()
    subscription_url = serializers.SerializerMethodField()

    class Meta:
        model = SubscriptionUser
        fields = [
            "id",
            "username",
            "password",
            "token",
            "enabled",
            "remark",
            "created_at",
            "node_ids",
            "node_count",
            "subscription_path",
            "subscription_url",
        ]
        read_only_fields = ["token", "created_at", "subscription_path", "subscription_url"]

    def get_subscription_path(self, obj):
        return f"/sub/{obj.token}"

    def get_subscription_url(self, obj):
        request = self.context.get("request")
        path = self.get_subscription_path(obj)
        return request.build_absolute_uri(path) if request else path

    def create(self, validated_data):
        nodes = validated_data.pop("nodes", [])
        password = validated_data.pop("password", "")
        if not password:
            raise serializers.ValidationError({"password": "创建用户时必须设置初始密码"})
        user = SubscriptionUser(token=new_token(), **validated_data)
        user.set_password(password)
        user.save()
        user.nodes.set(nodes)
        return user

    def update(self, instance, validated_data):
        nodes = validated_data.pop("nodes", None)
        password = validated_data.pop("password", "")
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=["password"])
        if nodes is not None:
            instance.nodes.set(nodes)
        return instance


class SubscriptionUserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)

    def validate(self, attrs):
        try:
            user = SubscriptionUser.objects.get(username=attrs["username"], enabled=True)
        except SubscriptionUser.DoesNotExist:
            user = None
        if not user or not user.check_password(attrs["password"]):
            raise serializers.ValidationError("用户名或密码错误")
        attrs["user"] = user
        return attrs


class SettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Setting
        fields = ["key", "value"]

    def validate(self, attrs):
        if attrs.get("key") == "clash_template" and attrs.get("value"):
            validate_template(attrs["value"])
        return attrs


class TemplateExtractSerializer(serializers.Serializer):
    config_text = serializers.CharField()


class RemoteTemplateSerializer(serializers.Serializer):
    remote_url = serializers.URLField()
