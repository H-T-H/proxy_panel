from urllib.parse import quote
import json

from panel.models import ClientDownload
from panel.services.client_catalog import CLIENT_PLATFORMS, catalog_for, ensure_client_catalog
from panel.services.settings import get_setting


SUBSCRIPTION_USER_SESSION_KEY = "subscription_user_id"

def client_platform_settings():
    default = {item["key"]: True for item in CLIENT_PLATFORMS}
    try:
        saved = json.loads(get_setting("client_download_platforms_enabled", "{}") or "{}")
    except json.JSONDecodeError:
        saved = {}
    return {**default, **{key: bool(value) for key, value in saved.items() if key in default}}


def build_import_links(subscription_url):
    encoded_url = quote(subscription_url, safe="")
    return [
        {
            "key": "clash_verge",
            "name": "Clash Verge / Clash Verge Rev",
            "url": f"clash://install-config?url={encoded_url}",
            "available": True,
        },
        {
            "key": "mihomo_party",
            "name": "Mihomo Party",
            "url": f"mihomo://install-config?url={encoded_url}",
            "available": True,
        },
        {
            "key": "stash",
            "name": "Stash",
            "url": f"stash://install-config?url={encoded_url}",
            "available": True,
        },
        {
            "key": "shadowrocket",
            "name": "Shadowrocket",
            "url": "shadowrocket://",
            "available": True,
            "requires_clipboard": True,
            "clipboard_text": subscription_url,
        },
    ]


def subscription_payload(request, user):
    subscription_path = f"/sub/{user.token}"
    subscription_url = request.build_absolute_uri(subscription_path)
    download_url = request.build_absolute_uri(f"{subscription_path}?download=1")
    client_downloads_enabled = get_setting("client_downloads_enabled", "true") == "true"
    client_downloads = []
    client_platforms = []
    if client_downloads_enabled:
        ensure_client_catalog()
        enabled_platforms = client_platform_settings()
        client_downloads = [
            {
                "id": item.id,
                "name": item.name,
                "platform_code": item.platform_code,
                "platform": item.platform,
                "version": item.version,
                "icon_url": (catalog_for(item) or {}).get("icon_url", ""),
                "source_type": item.source_type,
                "delivery_mode": ClientDownload.DELIVERY_FILE if item.local_file else ClientDownload.DELIVERY_LINK,
                "download_url": (
                    request.build_absolute_uri(f"/api/client-downloads/{item.id}/file/")
                    if item.local_file
                    else item.download_url
                ),
                "release_url": item.release_url,
                "remote_url": item.remote_url,
                "file_name": item.file_name,
                "remark": item.remark,
            }
            for item in ClientDownload.objects.filter(enabled=True).exclude(catalog_key="").order_by("platform_code", "sort_order", "name", "id")
            if enabled_platforms.get(item.platform_code, True)
            and (item.local_file or item.download_url)
        ]
        for platform in CLIENT_PLATFORMS:
            if not enabled_platforms.get(platform["key"], True):
                continue
            items = [item for item in client_downloads if item["platform_code"] == platform["key"]]
            if items:
                client_platforms.append({**platform, "items": items})
    return {
        "username": user.username,
        "enabled": user.enabled,
        "remark": user.remark,
        "node_count": user.nodes.filter(enabled=True).count(),
        "subscription_path": subscription_path,
        "subscription_url": subscription_url,
        "download_url": download_url,
        "import_links": build_import_links(subscription_url),
        "client_downloads_enabled": client_downloads_enabled,
        "client_downloads": client_downloads,
        "client_platforms": client_platforms,
    }
