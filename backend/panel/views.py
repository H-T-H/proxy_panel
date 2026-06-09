from django.contrib.auth import login, logout
from django.core.cache import cache
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
import hashlib
from urllib.parse import urlparse
import json
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
import yaml
import requests

from .models import ClientDownload, Node, Setting, Source, SubscriptionUser
from .serializers import (
    ClientDownloadSerializer,
    LoginSerializer,
    BulkIdsSerializer,
    BulkNodeStateSerializer,
    ManualNodeSerializer,
    NodeSerializer,
    RemoteTemplateSerializer,
    SettingSerializer,
    SourceSerializer,
    SubscriptionUserSerializer,
    SubscriptionUserLoginSerializer,
    TemplateExtractSerializer,
    TemplatePreviewSerializer,
)
from .services.nodes import node_sort_key, save_node
from .services.client_downloads import fetch_client_download
from .services.client_catalog import CLIENT_PLATFORMS, ensure_client_catalog
from .services.settings import get_setting, set_setting
from .services.subscription import (
    build_subscription,
    default_template_text,
    extract_template_from_config,
    new_token,
    unique_name,
    validate_template,
)
from .services.sync import fetch_and_extract_template, sync_source_with_error_record
from .services.user_portal import SUBSCRIPTION_USER_SESSION_KEY, subscription_payload

LOGIN_THROTTLE_LIMIT = 10
LOGIN_THROTTLE_WINDOW_SECONDS = 5 * 60


def login_throttle_key(request, scope, username):
    remote_addr = request.META.get("REMOTE_ADDR", "")
    raw = f"{scope}:{remote_addr}:{str(username or '').strip().lower()}"
    return "login-failures:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def throttle_response():
    return Response({"detail": "登录尝试次数过多，请稍后再试"}, status=status.HTTP_429_TOO_MANY_REQUESTS)


def is_login_throttled(request, scope, username):
    return int(cache.get(login_throttle_key(request, scope, username), 0) or 0) >= LOGIN_THROTTLE_LIMIT


def record_login_failure(request, scope, username):
    key = login_throttle_key(request, scope, username)
    failures = cache.get(key)
    if failures is None:
        cache.set(key, 1, LOGIN_THROTTLE_WINDOW_SECONDS)
    else:
        cache.incr(key)


def clear_login_failures(request, scope, username):
    cache.delete(login_throttle_key(request, scope, username))


def client_platform_settings():
    default = {item["key"]: True for item in CLIENT_PLATFORMS}
    try:
        saved = json.loads(get_setting("client_download_platforms_enabled", "{}") or "{}")
    except json.JSONDecodeError:
        saved = {}
    return {**default, **{key: bool(value) for key, value in saved.items() if key in default}}


def client_platform_payload():
    enabled = client_platform_settings()
    return [{**item, "enabled": enabled[item["key"]]} for item in CLIENT_PLATFORMS]


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok"})


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get("username", "")
    if is_login_throttled(request, "admin", username):
        return throttle_response()
    serializer = LoginSerializer(data=request.data)
    if not serializer.is_valid():
        record_login_failure(request, "admin", username)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    clear_login_failures(request, "admin", username)
    login(request, serializer.validated_data["user"])
    return Response({"username": serializer.validated_data["user"].username})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    subscription_user_id = request.session.get(SUBSCRIPTION_USER_SESSION_KEY)
    logout(request)
    if subscription_user_id:
        request.session[SUBSCRIPTION_USER_SESSION_KEY] = subscription_user_id
    return Response({"ok": True})


@api_view(["GET"])
def me_view(request):
    return Response({"username": request.user.username, "is_staff": request.user.is_staff})


def current_subscription_user(request):
    user_id = request.session.get(SUBSCRIPTION_USER_SESSION_KEY)
    if not user_id:
        return None, Response({"detail": "普通用户未登录"}, status=status.HTTP_401_UNAUTHORIZED)
    try:
        user = SubscriptionUser.objects.prefetch_related("nodes").get(id=user_id)
    except SubscriptionUser.DoesNotExist:
        request.session.pop(SUBSCRIPTION_USER_SESSION_KEY, None)
        return None, Response({"detail": "普通用户会话已失效"}, status=status.HTTP_401_UNAUTHORIZED)
    if not user.enabled:
        request.session.pop(SUBSCRIPTION_USER_SESSION_KEY, None)
        return None, Response({"detail": "账号已停用"}, status=status.HTTP_403_FORBIDDEN)
    return user, None


@api_view(["POST"])
@permission_classes([AllowAny])
def subscription_user_login_view(request):
    username = request.data.get("username", "")
    if is_login_throttled(request, "subscription", username):
        return throttle_response()
    serializer = SubscriptionUserLoginSerializer(data=request.data)
    if not serializer.is_valid():
        record_login_failure(request, "subscription", username)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    clear_login_failures(request, "subscription", username)
    request.session[SUBSCRIPTION_USER_SESSION_KEY] = serializer.validated_data["user"].id
    return Response({"username": serializer.validated_data["user"].username})


@api_view(["POST"])
@permission_classes([AllowAny])
def subscription_user_logout_view(request):
    request.session.pop(SUBSCRIPTION_USER_SESSION_KEY, None)
    return Response({"ok": True})


@api_view(["GET"])
@permission_classes([AllowAny])
def subscription_user_me_view(request):
    user, error = current_subscription_user(request)
    if error:
        return error
    return Response(
        {
            "username": user.username,
            "enabled": user.enabled,
            "remark": user.remark,
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def subscription_user_subscription_view(request):
    user, error = current_subscription_user(request)
    if error:
        return error
    return Response(subscription_payload(request, user))


@api_view(["GET"])
def dashboard_view(request):
    latest_sync = Source.objects.exclude(last_synced_at__isnull=True).order_by("-last_synced_at").first()
    return Response(
        {
            "sources": Source.objects.count(),
            "enabled_sources": Source.objects.filter(enabled=True).count(),
            "source_errors": Source.objects.exclude(Q(last_error="") | Q(last_error__isnull=True)).count(),
            "nodes": Node.objects.count(),
            "enabled_nodes": Node.objects.filter(enabled=True).count(),
            "users": SubscriptionUser.objects.count(),
            "enabled_users": SubscriptionUser.objects.filter(enabled=True).count(),
            "latest_synced_at": latest_sync.last_synced_at if latest_sync else None,
            "recent_sources": SourceSerializer(
                Source.objects.order_by("-last_synced_at", "-id")[:5],
                many=True,
                context={"request": request},
            ).data,
        }
    )


class SourceViewSet(viewsets.ModelViewSet):
    queryset = Source.objects.all().order_by("-id")
    serializer_class = SourceSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get("search", "").strip()
        enabled = self.request.query_params.get("enabled")
        sync_status = self.request.query_params.get("sync_status")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(url__icontains=search))
        if enabled in {"true", "false"}:
            queryset = queryset.filter(enabled=enabled == "true")
        if sync_status == "error":
            queryset = queryset.exclude(Q(last_error="") | Q(last_error__isnull=True))
        elif sync_status == "never":
            queryset = queryset.filter(last_synced_at__isnull=True)
        elif sync_status == "success":
            queryset = queryset.filter(last_synced_at__isnull=False).filter(Q(last_error="") | Q(last_error__isnull=True))
        return queryset

    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        source = self.get_object()
        try:
            result = sync_source_with_error_record(source)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({**result, "last_synced_at": source.last_synced_at})

    @action(detail=False, methods=["post"], url_path="bulk-sync")
    def bulk_sync(self, request):
        serializer = BulkIdsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sources = {item.id: item for item in Source.objects.filter(id__in=serializer.validated_data["ids"])}
        results = []
        for source_id in serializer.validated_data["ids"]:
            source = sources.get(source_id)
            if not source:
                results.append({"id": source_id, "ok": False, "error": "订阅源不存在"})
                continue
            try:
                result = sync_source_with_error_record(source)
                results.append({"id": source_id, "name": source.name, "ok": True, **result})
            except Exception as exc:
                results.append({"id": source_id, "name": source.name, "ok": False, "error": str(exc)})
        return Response(
            {
                "results": results,
                "succeeded": sum(1 for item in results if item["ok"]),
                "failed": sum(1 for item in results if not item["ok"]),
            }
        )


class ClientDownloadViewSet(viewsets.ModelViewSet):
    queryset = ClientDownload.objects.all().order_by("sort_order", "name", "id")
    serializer_class = ClientDownloadSerializer

    def get_queryset(self):
        ensure_client_catalog()
        queryset = super().get_queryset().exclude(catalog_key="")
        search = self.request.query_params.get("search", "").strip()
        enabled = self.request.query_params.get("enabled")
        platform_code = self.request.query_params.get("platform_code")
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(platform__icontains=search)
                | Q(version__icontains=search)
                | Q(download_url__icontains=search)
                | Q(remote_url__icontains=search)
            )
        if enabled in {"true", "false"}:
            queryset = queryset.filter(enabled=enabled == "true")
        if platform_code in {"ios", "mac", "windows", "linux", "android"}:
            queryset = queryset.filter(platform_code=platform_code)
        return queryset

    def create(self, request, *args, **kwargs):
        return Response({"detail": "客户端由面板内置，不能手动添加"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def destroy(self, request, *args, **kwargs):
        return Response({"detail": "客户端由面板内置，不能删除"}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @action(detail=False, methods=["get", "post"], url_path="config")
    def config(self, request):
        if request.method == "POST":
            enabled = bool(request.data.get("enabled"))
            set_setting("client_downloads_enabled", "true" if enabled else "false")
            platforms = request.data.get("platforms")
            if isinstance(platforms, dict):
                current = client_platform_settings()
                current.update({key: bool(value) for key, value in platforms.items() if key in current})
                set_setting("client_download_platforms_enabled", json.dumps(current))
            return Response({"enabled": enabled, "platforms": client_platform_payload()})
        return Response({
            "enabled": get_setting("client_downloads_enabled", "true") == "true",
            "platforms": client_platform_payload(),
        })

    @action(detail=True, methods=["post"], url_path="sync-latest")
    def sync_latest(self, request, pk=None):
        item = self.get_object()
        source_url = item.release_url or item.download_url
        parsed = urlparse(source_url)
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        if parsed.netloc.lower() != "github.com" or len(parts) < 2:
            return Response(
                {"detail": "当前客户端链接不是 GitHub Release 来源，请手动维护版本和链接地址。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        owner, repo = parts[0], parts[1]
        try:
            response = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/releases/latest",
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            return Response({"detail": f"同步失败：{exc}"}, status=status.HTTP_400_BAD_REQUEST)

        item.version = data.get("tag_name") or item.version
        item.download_url = data.get("html_url") or source_url
        item.release_url = data.get("html_url") or source_url
        item.save(update_fields=["version", "download_url", "release_url", "updated_at"])
        return Response(ClientDownloadSerializer(item).data)

    @action(detail=True, methods=["post"], url_path="fetch-remote")
    def fetch_remote(self, request, pk=None):
        item = self.get_object()
        try:
            item = fetch_client_download(item)
        except (ValueError, requests.RequestException) as exc:
            item.last_fetch_error = str(exc)
            item.save(update_fields=["last_fetch_error", "updated_at"])
            return Response({"detail": f"拉取失败：{exc}"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ClientDownloadSerializer(item, context={"request": request}).data)

    @action(detail=True, methods=["get"], permission_classes=[AllowAny], url_path="file")
    def file(self, request, pk=None):
        item = get_object_or_404(ClientDownload, pk=pk, enabled=True)
        if not item.local_file:
            raise Http404
        staff_user = request.user.is_authenticated and request.user.is_staff
        if not staff_user:
            if get_setting("client_downloads_enabled", "true") != "true":
                raise Http404
            if not item.catalog_key or not client_platform_settings().get(item.platform_code, True):
                raise Http404
            _, error = current_subscription_user(request)
            if error:
                return error
        return FileResponse(
            item.local_file.open("rb"),
            as_attachment=True,
            filename=item.file_name or item.local_file.name.rsplit("/", 1)[-1],
        )


class NodeViewSet(viewsets.ModelViewSet):
    queryset = Node.objects.select_related("source").all().order_by("source_name", "name", "id")
    serializer_class = NodeSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        source = self.request.query_params.get("source")
        search = self.request.query_params.get("search")
        proxy_type = self.request.query_params.get("type")
        enabled = self.request.query_params.get("enabled")
        if source == "manual":
            queryset = queryset.filter(source__isnull=True, source_name="手动添加")
        elif source and source.isdigit():
            queryset = queryset.filter(source_id=int(source))
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(tags__icontains=search) | Q(remark__icontains=search)
            )
        if proxy_type:
            queryset = queryset.filter(type=proxy_type)
        if enabled in {"true", "false"}:
            queryset = queryset.filter(enabled=enabled == "true")
        return queryset

    @action(detail=False, methods=["post"], url_path="manual")
    def manual(self, request):
        serializer = ManualNodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        node, _ = save_node(serializer.config, raw_text=serializer.validated_data["node_text"])
        return Response(NodeSerializer(node).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="preview")
    def preview(self, request):
        serializer = ManualNodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({"config": serializer.config})

    @action(detail=True, methods=["post"])
    def toggle(self, request, pk=None):
        node = self.get_object()
        node.enabled = not node.enabled
        node.save(update_fields=["enabled"])
        return Response(NodeSerializer(node).data)

    @action(detail=False, methods=["post"], url_path="bulk-delete")
    def bulk_delete(self, request):
        serializer = BulkIdsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        deleted, _ = Node.objects.filter(id__in=ids).delete()
        return Response({"deleted": deleted})

    @action(detail=False, methods=["post"], url_path="bulk-state")
    def bulk_state(self, request):
        serializer = BulkNodeStateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = Node.objects.filter(id__in=serializer.validated_data["ids"]).update(
            enabled=serializer.validated_data["enabled"]
        )
        return Response({"updated": updated, "enabled": serializer.validated_data["enabled"]})

    @action(detail=False, methods=["get"], url_path="options")
    def options(self, request):
        return Response(
            {
                "types": list(Node.objects.order_by("type").values_list("type", flat=True).distinct()),
                "sources": SourceSerializer(Source.objects.order_by("name"), many=True).data,
            }
        )


class SubscriptionUserViewSet(viewsets.ModelViewSet):
    queryset = SubscriptionUser.objects.prefetch_related("nodes").all().order_by("-id")
    serializer_class = SubscriptionUserSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get("search", "").strip()
        enabled = self.request.query_params.get("enabled")
        if search:
            queryset = queryset.filter(Q(username__icontains=search) | Q(remark__icontains=search))
        if enabled in {"true", "false"}:
            queryset = queryset.filter(enabled=enabled == "true")
        return queryset

    @action(detail=True, methods=["post"], url_path="reset-token")
    def reset_token(self, request, pk=None):
        user = self.get_object()
        user.token = new_token()
        user.save(update_fields=["token"])
        return Response(SubscriptionUserSerializer(user, context={"request": request}).data)


class SettingViewSet(viewsets.ModelViewSet):
    queryset = Setting.objects.all().order_by("key")
    serializer_class = SettingSerializer
    lookup_field = "key"

    @action(detail=False, methods=["get", "post"], url_path="template")
    def template(self, request):
        if request.method == "POST":
            template = request.data.get("template", "").strip()
            node_order_keywords = request.data.get("node_order_keywords", "")
            if template:
                validate_template(template)
            set_setting("clash_template", template)
            set_setting("node_order_keywords", str(node_order_keywords or "").strip())
            return Response({"template": template, "node_order_keywords": str(node_order_keywords or "").strip()})
        return Response(
            {
                "template": get_setting("clash_template", ""),
                "node_order_keywords": get_setting("node_order_keywords", ""),
                "remote_url": get_setting("remote_template_url", ""),
                "remote_updated_at": get_setting("remote_template_updated_at", ""),
            }
        )

    @action(detail=False, methods=["post"], url_path="template/extract")
    def extract_template(self, request):
        serializer = TemplateExtractSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = extract_template_from_config(serializer.validated_data["config_text"])
        validate_template(template)
        return Response({"template": template})

    @action(detail=False, methods=["post"], url_path="template/fetch")
    def fetch_template(self, request):
        serializer = RemoteTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = fetch_and_extract_template(serializer.validated_data["remote_url"])
        set_setting("remote_template_url", serializer.validated_data["remote_url"])
        set_setting("remote_template_updated_at", timezone.now().strftime("%Y-%m-%d %H:%M:%S %Z"))
        return Response({"template": template})

    @action(detail=False, methods=["post"], url_path="template/preview")
    def preview_template(self, request):
        serializer = TemplatePreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = serializer.validated_data.get("template", get_setting("clash_template", ""))
        if template:
            validate_template(template)
        nodes = Node.objects.filter(enabled=True)
        user_id = serializer.validated_data.get("user_id")
        if user_id:
            user = get_object_or_404(SubscriptionUser.objects.prefetch_related("nodes"), id=user_id)
            nodes = user.nodes.filter(enabled=True)
        elif "node_ids" in serializer.validated_data:
            nodes = nodes.filter(id__in=serializer.validated_data["node_ids"])
        configs = []
        used_names = set()
        for node in sorted(nodes, key=node_sort_key):
            config = dict(node.config)
            config["name"] = unique_name(config.get("name") or node.name, used_names)
            configs.append(config)
        node_order_keywords = serializer.validated_data.get(
            "node_order_keywords",
            get_setting("node_order_keywords", ""),
        )
        content = yaml.safe_dump(
            build_subscription(configs, template, node_order_keywords),
            allow_unicode=True,
            sort_keys=False,
        )
        return Response({"yaml": content, "node_count": len(configs)})

    @action(detail=False, methods=["post"], url_path="template/restore")
    def restore_template(self, request):
        template = default_template_text()
        set_setting("clash_template", template)
        return Response({"template": template, "node_order_keywords": get_setting("node_order_keywords", "")})


@api_view(["GET"])
@permission_classes([AllowAny])
def subscribe(request, token):
    user = get_object_or_404(SubscriptionUser.objects.prefetch_related("nodes"), token=token, enabled=True)
    configs = []
    used_names = set()
    nodes = sorted(user.nodes.filter(enabled=True), key=node_sort_key)
    for node in nodes:
        config = dict(node.config)
        config["name"] = unique_name(config.get("name") or node.name, used_names)
        configs.append(config)
    doc = build_subscription(configs, get_setting("clash_template", ""), get_setting("node_order_keywords", ""))
    response = HttpResponse(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
        content_type="text/yaml; charset=utf-8",
    )
    if request.GET.get("download") == "1":
        response["Content-Disposition"] = 'attachment; filename="subscription.yaml"'
    return response
