from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from rest_framework.test import APIClient
import yaml

from panel.models import ClientDownload, Node, Source, SubscriptionUser, UserNode
from panel.services.client_catalog import CATALOG_BY_KEY, asset_matches, ensure_client_catalog
from panel.services.subscription import config_hash


@pytest.fixture
def client(db):
    User = get_user_model()
    user = User.objects.create_user(username="admin", password="secret", is_staff=True)
    api_client = APIClient()
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


@pytest.mark.django_db
def test_manual_node_api_creates_node(client):
    response = client.post(
        "/api/nodes/manual/",
        {
            "node_text": """
name: HK 01
type: ss
server: example.com
port: 8388
cipher: aes-128-gcm
password: secret
"""
        },
        format="json",
    )
    assert response.status_code == 201
    assert Node.objects.count() == 1
    assert response.data["name"] == "HK 01"


def test_client_catalog_asset_arch_rules():
    mac_catalog = CATALOG_BY_KEY["clash_verge_rev_mac"]
    linux_catalog = CATALOG_BY_KEY["clash_verge_rev_linux"]

    assert asset_matches(mac_catalog, "Clash.Verge_2.5.1_aarch64.dmg")
    assert not asset_matches(mac_catalog, "Clash.Verge_2.5.1_x64.dmg")
    assert not asset_matches(mac_catalog, "Clash.Verge_2.5.1_amd64.dmg")

    assert asset_matches(linux_catalog, "Clash.Verge_2.5.1_linux_amd64.AppImage")
    assert not asset_matches(linux_catalog, "Clash.Verge_2.5.1_linux_arm64.AppImage")


@pytest.mark.django_db
def test_login_api_sets_session():
    User = get_user_model()
    User.objects.create_user(username="admin", password="secret", is_staff=True)
    api_client = APIClient()
    response = api_client.post("/api/auth/login/", {"username": "admin", "password": "secret"}, format="json")
    assert response.status_code == 200
    assert response.data["username"] == "admin"
    assert "sessionid" in response.cookies


@pytest.mark.django_db
def test_admin_login_is_throttled_after_repeated_failures():
    User = get_user_model()
    User.objects.create_user(username="admin", password="secret", is_staff=True)
    api_client = APIClient()
    for _ in range(10):
        response = api_client.post(
            "/api/auth/login/",
            {"username": "admin", "password": "wrong"},
            format="json",
        )
        assert response.status_code == 400

    throttled = api_client.post(
        "/api/auth/login/",
        {"username": "admin", "password": "secret"},
        format="json",
    )
    assert throttled.status_code == 429


@pytest.mark.django_db
def test_successful_admin_login_clears_failed_login_counter():
    User = get_user_model()
    User.objects.create_user(username="admin", password="secret", is_staff=True)
    api_client = APIClient()
    api_client.post(
        "/api/auth/login/",
        {"username": "admin", "password": "wrong"},
        format="json",
    )
    success = api_client.post(
        "/api/auth/login/",
        {"username": "admin", "password": "secret"},
        format="json",
    )
    assert success.status_code == 200
    api_client.post("/api/auth/logout/", {}, format="json")
    second_success = api_client.post(
        "/api/auth/login/",
        {"username": "admin", "password": "secret"},
        format="json",
    )
    assert second_success.status_code == 200


@pytest.mark.django_db
def test_initadmin_does_not_use_public_default_password(settings, tmp_path, monkeypatch):
    settings.DATA_DIR = tmp_path
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "change-me")

    output = StringIO()
    call_command("initadmin", stdout=output)

    password = (tmp_path / "admin_password").read_text().strip()
    user = get_user_model().objects.get(username="admin")
    assert password
    assert password != "change-me"
    assert user.check_password(password)
    assert not user.check_password("change-me")
    assert "admin_password" in output.getvalue()


@pytest.mark.django_db
def test_non_staff_user_cannot_login_or_access_admin_api():
    User = get_user_model()
    user = User.objects.create_user(username="member", password="secret")
    api_client = APIClient()
    login_response = api_client.post("/api/auth/login/", {"username": "member", "password": "secret"}, format="json")
    assert login_response.status_code == 400

    api_client.force_authenticate(user=user)
    assert api_client.get("/api/nodes/").status_code == 403


@pytest.mark.django_db
def test_list_api_is_paginated_and_caps_page_size(client):
    Node.objects.bulk_create(
        [
            Node(
                name=f"Node {index:03}",
                type="ss",
                config={"name": f"Node {index:03}", "type": "ss"},
                config_hash=f"hash-{index}",
            )
            for index in range(105)
        ]
    )
    response = client.get("/api/nodes/?page=1&page_size=500")
    assert response.status_code == 200
    assert response.data["count"] == 105
    assert len(response.data["results"]) == 100


@pytest.mark.django_db
def test_list_filters_cover_sources_nodes_and_users(client):
    source = Source.objects.create(name="Hong Kong", url="https://example.com/hk", enabled=False, last_error="timeout")
    Node.objects.create(
        name="HK Fast",
        type="ss",
        enabled=False,
        source=source,
        source_name=source.name,
        tags="premium",
        config={"name": "HK Fast", "type": "ss"},
        config_hash="filter-hash",
    )
    SubscriptionUser.objects.create(username="alice", token="filter-token", enabled=False, remark="trial")

    source_response = client.get("/api/sources/?search=Hong&enabled=false&sync_status=error")
    node_response = client.get(f"/api/nodes/?search=premium&source={source.id}&type=ss&enabled=false")
    user_response = client.get("/api/users/?search=trial&enabled=false")

    assert source_response.data["count"] == 1
    assert node_response.data["count"] == 1
    assert user_response.data["count"] == 1


@pytest.mark.django_db
def test_user_api_binds_nodes(client):
    node = Node.objects.create(
        name="HK 01",
        type="ss",
        config={"name": "HK 01", "type": "ss", "server": "example.com", "port": 8388},
        config_hash=config_hash({"name": "HK 01", "type": "ss", "server": "example.com", "port": 8388}),
    )
    response = client.post(
        "/api/users/",
        {"username": "alice", "password": "initial-secret", "node_ids": [node.id]},
        format="json",
    )
    assert response.status_code == 201
    user = SubscriptionUser.objects.get(username="alice")
    assert list(user.nodes.values_list("id", flat=True)) == [node.id]
    assert user.password != "initial-secret"
    assert user.check_password("initial-secret")
    assert "password" not in response.data


@pytest.mark.django_db
def test_admin_user_create_requires_password_and_can_reset_it(client):
    missing = client.post("/api/users/", {"username": "alice"}, format="json")
    assert missing.status_code == 400
    assert "password" in missing.data

    created = client.post(
        "/api/users/",
        {"username": "alice", "password": "initial-secret"},
        format="json",
    )
    user = SubscriptionUser.objects.get(username="alice")
    assert created.status_code == 201
    assert user.check_password("initial-secret")
    assert "password" not in created.data

    unchanged = client.patch(
        f"/api/users/{user.id}/",
        {"remark": "updated", "password": ""},
        format="json",
    )
    user.refresh_from_db()
    assert unchanged.status_code == 200
    assert user.check_password("initial-secret")

    reset = client.patch(
        f"/api/users/{user.id}/",
        {"password": "replacement-secret"},
        format="json",
    )
    user.refresh_from_db()
    assert reset.status_code == 200
    assert user.check_password("replacement-secret")
    assert not user.check_password("initial-secret")
    assert "password" not in reset.data


def create_subscription_user(username="alice", password="user-secret", **kwargs):
    user = SubscriptionUser(username=username, token=f"{username}-token", **kwargs)
    user.set_password(password)
    user.save()
    return user


@pytest.mark.django_db
def test_subscription_user_login_accepts_direct_post_and_uses_generic_failure():
    create_subscription_user()
    api_client = APIClient()
    wrong_password = api_client.post(
        "/api/user-auth/login/",
        {"username": "alice", "password": "wrong"},
        format="json",
    )
    unknown_user = api_client.post(
        "/api/user-auth/login/",
        {"username": "unknown", "password": "wrong"},
        format="json",
    )
    assert wrong_password.status_code == 400
    assert unknown_user.status_code == 400
    assert wrong_password.data == unknown_user.data

    success = api_client.post(
        "/api/user-auth/login/",
        {"username": "alice", "password": "user-secret"},
        format="json",
    )
    assert success.status_code == 200
    assert api_client.session["subscription_user_id"] == SubscriptionUser.objects.get(username="alice").id


@pytest.mark.django_db
def test_subscription_user_login_is_throttled_after_repeated_failures():
    create_subscription_user()
    api_client = APIClient()
    for _ in range(10):
        response = api_client.post(
            "/api/user-auth/login/",
            {"username": "alice", "password": "wrong"},
            format="json",
        )
        assert response.status_code == 400

    throttled = api_client.post(
        "/api/user-auth/login/",
        {"username": "alice", "password": "user-secret"},
        format="json",
    )
    assert throttled.status_code == 429


@pytest.mark.django_db
def test_disabled_subscription_user_cannot_login_or_keep_session():
    user = create_subscription_user()
    api_client = APIClient()
    assert api_client.post(
        "/api/user-auth/login/",
        {"username": "alice", "password": "user-secret"},
        format="json",
    ).status_code == 200

    user.enabled = False
    user.save(update_fields=["enabled"])
    denied = api_client.get("/api/user-auth/me/")
    assert denied.status_code == 403
    assert denied.data["detail"] == "账号已停用"
    assert "subscription_user_id" not in api_client.session

    login_denied = api_client.post(
        "/api/user-auth/login/",
        {"username": "alice", "password": "user-secret"},
        format="json",
    )
    assert login_denied.status_code == 400


@pytest.mark.django_db
def test_subscription_user_me_and_subscription_only_return_current_user():
    node = Node.objects.create(
        name="HK 01",
        type="ss",
        config={"name": "HK 01", "type": "ss", "server": "example.com", "port": 8388},
        config_hash="portal-node",
    )
    alice = create_subscription_user(remark="primary")
    alice.nodes.add(node)
    create_subscription_user(username="bob", password="bob-secret", remark="other")
    api_client = APIClient()
    api_client.post(
        "/api/user-auth/login/",
        {"username": "alice", "password": "user-secret"},
        format="json",
    )

    me = api_client.get("/api/user-auth/me/")
    subscription = api_client.get("/api/user/subscription/?user_id=2")
    assert me.status_code == 200
    assert me.data["username"] == "alice"
    assert subscription.status_code == 200
    assert subscription.data["username"] == "alice"
    assert subscription.data["remark"] == "primary"
    assert subscription.data["node_count"] == 1
    assert subscription.data["subscription_path"] == "/sub/alice-token"
    assert subscription.data["subscription_url"] == "http://testserver/sub/alice-token"
    assert subscription.data["download_url"] == "http://testserver/sub/alice-token?download=1"
    assert [item["key"] for item in subscription.data["import_links"]] == [
        "clash_verge",
        "mihomo_party",
        "stash",
        "shadowrocket",
    ]
    assert "http%3A%2F%2Ftestserver%2Fsub%2Falice-token" in subscription.data["import_links"][0]["url"]
    shadowrocket = subscription.data["import_links"][3]
    assert shadowrocket["available"] is True
    assert shadowrocket["url"] == "shadowrocket://"
    assert shadowrocket["requires_clipboard"] is True
    assert shadowrocket["clipboard_text"] == "http://testserver/sub/alice-token"
    assert subscription.data["client_downloads_enabled"] is True
    assert subscription.data["client_downloads"]


@pytest.mark.django_db
def test_subscription_user_subscription_returns_enabled_client_downloads_when_enabled():
    user = create_subscription_user()
    ClientDownload.objects.all().delete()
    ensure_client_catalog()
    ClientDownload.objects.exclude(catalog_key="shadowrocket_ios").update(enabled=False)
    client = APIClient()
    admin = get_user_model().objects.create_user(username="admin", password="secret", is_staff=True)
    client.force_authenticate(user=admin)
    config = client.post("/api/client-downloads/config/", {"enabled": True}, format="json")
    assert config.status_code == 200

    api_client = APIClient()
    api_client.post(
        "/api/user-auth/login/",
        {"username": user.username, "password": "user-secret"},
        format="json",
    )

    subscription = api_client.get("/api/user/subscription/")
    assert subscription.status_code == 200
    assert subscription.data["client_downloads_enabled"] is True
    assert [item["name"] for item in subscription.data["client_downloads"]] == ["Shadowrocket"]
    assert subscription.data["client_downloads"][0]["download_url"].startswith("https://apps.apple.com/")
    assert subscription.data["client_platforms"][0]["key"] == "ios"


@pytest.mark.django_db
def test_subscription_user_subscription_hides_disabled_client_platforms():
    user = create_subscription_user()
    ClientDownload.objects.all().delete()
    ensure_client_catalog()
    ClientDownload.objects.exclude(catalog_key__in=["shadowrocket_ios", "clash_verge_rev_linux"]).update(enabled=False)
    client = APIClient()
    admin = get_user_model().objects.create_user(username="admin", password="secret", is_staff=True)
    client.force_authenticate(user=admin)
    config = client.post(
        "/api/client-downloads/config/",
        {"enabled": True, "platforms": {"linux": False}},
        format="json",
    )
    assert config.status_code == 200

    api_client = APIClient()
    api_client.post(
        "/api/user-auth/login/",
        {"username": user.username, "password": "user-secret"},
        format="json",
    )
    subscription = api_client.get("/api/user/subscription/")
    assert [item["name"] for item in subscription.data["client_downloads"]] == ["Shadowrocket"]
    assert [item["key"] for item in subscription.data["client_platforms"]] == ["ios"]


@pytest.mark.django_db
def test_client_download_create_is_forbidden(client):
    config = client.post("/api/client-downloads/config/", {"enabled": True}, format="json")
    assert config.status_code == 200
    upload = SimpleUploadedFile("client.zip", b"local client bytes", content_type="application/zip")
    created = client.post(
        "/api/client-downloads/",
        {
            "name": "Local Client",
            "platform_code": "linux",
            "platform": "Windows",
            "version": "1.0.0",
            "source_type": "local_file",
            "enabled": "true",
            "sort_order": "1",
            "upload_file": upload,
        },
        format="multipart",
    )
    assert created.status_code == 405
    assert created.data["detail"] == "客户端由面板内置，不能手动添加"


@pytest.mark.django_db
def test_catalog_client_uploaded_file_overrides_release_link_for_subscription_users(client):
    user = create_subscription_user()
    config = client.post("/api/client-downloads/config/", {"enabled": True}, format="json")
    assert config.status_code == 200
    item = ClientDownload.objects.get(catalog_key="clash_verge_rev_linux")
    ClientDownload.objects.exclude(id=item.id).update(enabled=False)
    updated = client.patch(
        f"/api/client-downloads/{item.id}/",
        {"enabled": True, "upload_file": SimpleUploadedFile("clash.AppImage", b"catalog client bytes")},
        format="multipart",
    )
    assert updated.status_code == 200
    assert updated.data["has_local_file"] is True
    assert updated.data["file_name"] == "clash.AppImage"

    api_client = APIClient()
    api_client.post(
        "/api/user-auth/login/",
        {"username": user.username, "password": "user-secret"},
        format="json",
    )
    subscription = api_client.get("/api/user/subscription/")
    remote_item = next(item for item in subscription.data["client_downloads"] if item["name"] == "Clash Verge Rev")
    assert remote_item["source_type"] == "local_file"
    assert remote_item["delivery_mode"] == "file"
    assert remote_item["download_url"].endswith(f"/api/client-downloads/{item.id}/file/")

    download = api_client.get(f"/api/client-downloads/{item.id}/file/")
    assert download.status_code == 200
    assert b"".join(download.streaming_content) == b"catalog client bytes"


@pytest.mark.django_db
def test_subscription_user_file_download_respects_client_visibility_switches(client):
    user = create_subscription_user()
    config = client.post("/api/client-downloads/config/", {"enabled": True}, format="json")
    assert config.status_code == 200
    item = ClientDownload.objects.get(catalog_key="clash_verge_rev_linux")
    updated = client.patch(
        f"/api/client-downloads/{item.id}/",
        {"enabled": True, "upload_file": SimpleUploadedFile("clash.AppImage", b"catalog client bytes")},
        format="multipart",
    )
    assert updated.status_code == 200

    api_client = APIClient()
    api_client.post(
        "/api/user-auth/login/",
        {"username": user.username, "password": "user-secret"},
        format="json",
    )
    assert api_client.get(f"/api/client-downloads/{item.id}/file/").status_code == 200

    disabled = client.post("/api/client-downloads/config/", {"enabled": False}, format="json")
    assert disabled.status_code == 200
    assert api_client.get(f"/api/client-downloads/{item.id}/file/").status_code == 404

    platform_hidden = client.post(
        "/api/client-downloads/config/",
        {"enabled": True, "platforms": {"linux": False}},
        format="json",
    )
    assert platform_hidden.status_code == 200
    assert api_client.get(f"/api/client-downloads/{item.id}/file/").status_code == 404

    admin_download = client.get(f"/api/client-downloads/{item.id}/file/")
    assert admin_download.status_code == 200


@pytest.mark.django_db
def test_subscription_user_cannot_access_admin_api_and_logout_isolated_from_admin():
    User = get_user_model()
    User.objects.create_user(username="admin", password="secret", is_staff=True)
    create_subscription_user()
    api_client = APIClient()

    api_client.post(
        "/api/auth/login/",
        {"username": "admin", "password": "secret"},
        format="json",
    )
    api_client.post(
        "/api/user-auth/login/",
        {"username": "alice", "password": "user-secret"},
        format="json",
    )
    assert api_client.get("/api/nodes/").status_code == 200
    assert api_client.post(
        "/api/user-auth/logout/",
        {},
        format="json",
    ).status_code == 200
    assert api_client.get("/api/user-auth/me/").status_code == 401
    assert api_client.get("/api/auth/me/").status_code == 200

    anonymous_user_client = APIClient()
    anonymous_user_client.post(
        "/api/user-auth/login/",
        {"username": "alice", "password": "user-secret"},
        format="json",
    )
    assert anonymous_user_client.get("/api/nodes/").status_code == 403


@pytest.mark.django_db
def test_admin_logout_preserves_subscription_user_session():
    User = get_user_model()
    User.objects.create_user(username="admin", password="secret", is_staff=True)
    create_subscription_user()
    api_client = APIClient()
    api_client.post(
        "/api/user-auth/login/",
        {"username": "alice", "password": "user-secret"},
        format="json",
    )
    api_client.post("/api/auth/login/", {"username": "admin", "password": "secret"}, format="json")
    assert api_client.post(
        "/api/auth/logout/",
        {},
        format="json",
    ).status_code == 200
    assert api_client.get("/api/auth/me/").status_code in {401, 403}
    assert api_client.get("/api/user-auth/me/").status_code == 200


@pytest.mark.django_db
def test_deleted_subscription_user_session_is_rejected():
    user = create_subscription_user()
    api_client = APIClient()
    session = api_client.session
    session["subscription_user_id"] = user.id
    session.save()
    user.delete()

    response = api_client.get("/api/user/subscription/")
    assert response.status_code == 401
    assert "subscription_user_id" not in api_client.session


@pytest.mark.django_db
def test_node_toggle_and_bulk_delete(client):
    first = Node.objects.create(
        name="HK 01",
        type="ss",
        enabled=True,
        config={"name": "HK 01", "type": "ss", "server": "example.com", "port": 8388},
        config_hash="hash-1",
    )
    second = Node.objects.create(
        name="HK 02",
        type="ss",
        enabled=True,
        config={"name": "HK 02", "type": "ss", "server": "example.net", "port": 8388},
        config_hash="hash-2",
    )
    toggle_response = client.post(f"/api/nodes/{first.id}/toggle/", {}, format="json")
    first.refresh_from_db()
    assert toggle_response.status_code == 200
    assert first.enabled is False

    delete_response = client.post("/api/nodes/bulk-delete/", {"ids": [first.id, second.id]}, format="json")
    assert delete_response.status_code == 200
    assert Node.objects.count() == 0


@pytest.mark.django_db
def test_node_preview_bulk_state_and_options(client):
    preview = client.post(
        "/api/nodes/preview/",
        {"node_text": "name: Preview\ntype: ss\nserver: example.com\nport: 8388"},
        format="json",
    )
    assert preview.status_code == 200
    assert preview.data["config"]["name"] == "Preview"

    node = Node.objects.create(
        name="Preview",
        type="ss",
        enabled=True,
        config=preview.data["config"],
        config_hash="preview-hash",
    )
    state = client.post("/api/nodes/bulk-state/", {"ids": [node.id], "enabled": False}, format="json")
    options = client.get("/api/nodes/options/")
    node.refresh_from_db()
    assert state.data == {"updated": 1, "enabled": False}
    assert node.enabled is False
    assert options.data["types"] == ["ss"]


@pytest.mark.django_db
def test_node_update_api_updates_config(client):
    node = Node.objects.create(
        name="HK 01",
        type="ss",
        enabled=True,
        config={"name": "HK 01", "type": "ss", "server": "example.com", "port": 8388},
        config_hash="hash-1",
    )
    response = client.patch(
        f"/api/nodes/{node.id}/",
        {
            "tags": "hk,fast",
            "remark": "primary",
            "config": {"name": "HK 02", "type": "ss", "server": "example.net", "port": 8389},
        },
        format="json",
    )
    node.refresh_from_db()
    assert response.status_code == 200
    assert node.name == "HK 02"
    assert node.type == "ss"
    assert node.tags == "hk,fast"
    assert node.remark == "primary"
    assert node.config["server"] == "example.net"


@pytest.mark.django_db
def test_user_reset_token_and_delete(client):
    user = SubscriptionUser.objects.create(username="alice", token="token-1")
    reset_response = client.post(f"/api/users/{user.id}/reset-token/", {}, format="json")
    user.refresh_from_db()
    assert reset_response.status_code == 200
    assert user.token != "token-1"

    delete_response = client.delete(f"/api/users/{user.id}/")
    assert delete_response.status_code == 204
    assert SubscriptionUser.objects.count() == 0


@pytest.mark.django_db
def test_subscribe_outputs_yaml(client):
    node = Node.objects.create(
        name="HK 01",
        type="ss",
        enabled=True,
        config={"name": "HK 01", "type": "ss", "server": "example.com", "port": 8388},
        config_hash=config_hash({"name": "HK 01", "type": "ss", "server": "example.com", "port": 8388}),
    )
    user = SubscriptionUser.objects.create(username="alice", token="token-1", enabled=True)
    user.nodes.add(node)
    public_client = APIClient()
    response = public_client.get("/sub/token-1")
    assert response.status_code == 200
    assert "proxies:" in response.content.decode()
    assert "HK 01" in response.content.decode()

    download = public_client.get("/sub/token-1?download=1")
    assert download.status_code == 200
    assert download["Content-Disposition"] == 'attachment; filename="subscription.yaml"'


@pytest.mark.django_db
def test_template_api_saves_and_extracts(client):
    save_response = client.post(
        "/api/settings/template/",
        {
            "template": "proxy-groups:\n- name: Proxy\n  type: select\n  proxies:\n  - __PROXIES__\n",
            "node_order_keywords": "香港\n日本",
        },
        format="json",
    )
    assert save_response.status_code == 200
    assert save_response.data["node_order_keywords"] == "香港\n日本"
    assert client.get("/api/settings/template/").data["node_order_keywords"] == "香港\n日本"

    extract_response = client.post(
        "/api/settings/template/extract/",
        {
            "config_text": """
proxies:
- name: HK 01
  type: ss
  server: example.com
  port: 8388
proxy-groups:
- name: Proxy
  type: select
  proxies:
  - HK 01
rules:
- MATCH,Proxy
"""
        },
        format="json",
    )
    assert extract_response.status_code == 200
    assert "__PROXIES__" in extract_response.data["template"]


@pytest.mark.django_db
def test_source_sync_records_error(client, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr("panel.services.sync.requests.get", fail)
    source = Source.objects.create(name="Broken", url="https://example.com/sub.yaml")
    response = client.post(f"/api/sources/{source.id}/sync/", {}, format="json")
    source.refresh_from_db()
    assert response.status_code == 400
    assert source.last_error == "network down"


@pytest.mark.django_db
def test_source_sync_imports_nodes(client, monkeypatch):
    class FakeResponse:
        content = yaml.safe_dump(
            {
                "proxies": [
                    {
                        "name": "HK 01",
                        "type": "ss",
                        "server": "example.com",
                        "port": 8388,
                        "cipher": "aes-128-gcm",
                        "password": "secret",
                    }
                ]
            },
            allow_unicode=True,
        ).encode()

        def raise_for_status(self):
            return None

    monkeypatch.setattr("panel.services.sync.requests.get", lambda *args, **kwargs: FakeResponse())
    source = Source.objects.create(name="Remote", url="https://example.com/sub.yaml")
    response = client.post(f"/api/sources/{source.id}/sync/", {}, format="json")
    source.refresh_from_db()
    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["created"] == 1
    assert response.data["updated"] == 0
    assert response.data["deleted"] == 0
    assert source.last_error == ""
    assert Node.objects.get().source == source


@pytest.mark.django_db
def test_bulk_source_sync_reports_individual_results(client, monkeypatch):
    first = Source.objects.create(name="First", url="https://example.com/first")
    second = Source.objects.create(name="Second", url="https://example.com/second")

    def fake_sync(source):
        if source == second:
            raise RuntimeError("broken")
        return {"count": 1, "created": 1, "updated": 0, "deleted": 0}

    monkeypatch.setattr("panel.views.sync_source_with_error_record", fake_sync)
    response = client.post("/api/sources/bulk-sync/", {"ids": [first.id, second.id, 9999]}, format="json")
    assert response.status_code == 200
    assert response.data["succeeded"] == 1
    assert response.data["failed"] == 2


@pytest.mark.django_db
def test_source_sync_deletes_stale_nodes_and_user_bindings(client, monkeypatch):
    source = Source.objects.create(name="Remote", url="https://example.com/sub.yaml")
    stale = Node.objects.create(
        name="Old",
        type="ss",
        source=source,
        source_name=source.name,
        config={"name": "Old", "type": "ss", "server": "old.example.com", "port": 8388},
        config_hash="old-hash",
    )
    user = SubscriptionUser.objects.create(username="alice", token="token-1")
    user.nodes.add(stale)

    class FakeResponse:
        content = yaml.safe_dump(
            {"proxies": [{"name": "New", "type": "ss", "server": "new.example.com", "port": 8388}]}
        ).encode()

        def raise_for_status(self):
            return None

    monkeypatch.setattr("panel.services.sync.requests.get", lambda *args, **kwargs: FakeResponse())
    response = client.post(f"/api/sources/{source.id}/sync/", {}, format="json")

    assert response.status_code == 200
    assert response.data["deleted"] == 1
    assert not Node.objects.filter(id=stale.id).exists()
    assert UserNode.objects.count() == 0


@pytest.mark.django_db
def test_source_sync_rolls_back_partial_changes(client, monkeypatch):
    source = Source.objects.create(name="Remote", url="https://example.com/sub.yaml")
    existing = Node.objects.create(
        name="Existing",
        type="ss",
        source=source,
        source_name=source.name,
        config={"name": "Existing", "type": "ss"},
        config_hash="existing-hash",
    )

    class FakeResponse:
        content = yaml.safe_dump(
            {
                "proxies": [
                    {"name": "First", "type": "ss"},
                    {"name": "Second", "type": "ss"},
                ]
            }
        ).encode()

        def raise_for_status(self):
            return None

    calls = 0

    def fail_on_second(config, raw_text="", source=None):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("save failed")
        return Node.objects.create(
            name=config["name"],
            type=config["type"],
            source=source,
            source_name=source.name,
            config=config,
            config_hash=f"new-hash-{calls}",
        ), True

    monkeypatch.setattr("panel.services.sync.requests.get", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr("panel.services.sync.save_node", fail_on_second)
    response = client.post(f"/api/sources/{source.id}/sync/", {}, format="json")

    source.refresh_from_db()
    assert response.status_code == 400
    assert source.last_error == "save failed"
    assert list(Node.objects.values_list("id", flat=True)) == [existing.id]


@pytest.mark.django_db
def test_remote_template_fetch_api(client, monkeypatch):
    class FakeResponse:
        text = """
proxies:
- name: HK 01
  type: ss
  server: example.com
  port: 8388
proxy-groups:
- name: Proxy
  type: select
  proxies:
  - HK 01
rules:
- MATCH,Proxy
"""

        def raise_for_status(self):
            return None

    monkeypatch.setattr("panel.services.sync.requests.get", lambda *args, **kwargs: FakeResponse())
    response = client.post("/api/settings/template/fetch/", {"remote_url": "https://example.com/config.yaml"}, format="json")
    assert response.status_code == 200
    assert "__PROXIES__" in response.data["template"]


@pytest.mark.django_db
def test_template_preview_and_restore_api(client):
    us_node = Node.objects.create(
        name="美国 01",
        type="ss",
        config={"name": "美国 01", "type": "ss", "server": "us.example.com", "port": 8388},
        config_hash="template-preview-us-hash",
    )
    hk_node = Node.objects.create(
        name="香港 01",
        type="ss",
        config={"name": "香港 01", "type": "ss", "server": "hk.example.com", "port": 8388},
        config_hash="template-preview-hk-hash",
    )
    preview = client.post(
        "/api/settings/template/preview/",
        {
            "template": "proxy-groups:\n- name: Proxy\n  type: select\n  proxies:\n  - __PROXIES__\n",
            "node_order_keywords": "香港",
            "node_ids": [us_node.id, hk_node.id],
        },
        format="json",
    )
    restore = client.post("/api/settings/template/restore/", {}, format="json")
    assert preview.status_code == 200
    assert preview.data["node_count"] == 2
    assert preview.data["yaml"].find("香港 01") < preview.data["yaml"].find("美国 01")
    assert restore.status_code == 200
    assert "proxy-groups:" in restore.data["template"]
