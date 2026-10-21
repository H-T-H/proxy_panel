import functools
import http.server
import re
import threading

import pytest
import yaml

import app as app_module
from conftest import csrf


def flashes(html):
    return re.findall(r'<div class="toast [a-z]+">.*?<span>([^<]*)</span>', html, re.S)


def create_user(admin, username="alice"):
    response = admin.post("/users", data={"username": username})
    assert response.status_code == 302
    return int(response.headers["Location"].rstrip("/").split("/")[-1])


def add_nodes(admin, text):
    return admin.post("/nodes/new", data={"node_text": text}, follow_redirects=True)


def node_ids(admin, query=""):
    return re.findall(r'name="node_ids" value="(\d+)"', admin.get(f"/nodes{query}").text)


def sub_path(admin, user_id):
    html = admin.get(f"/users/{user_id}").text
    url = re.search(r'id="sub-url" value="([^"]+)"', html).group(1)
    return "/sub/" + url.split("/sub/")[1]


# ---------- auth & security ----------

def test_pages_require_login(app):
    client = app.test_client()
    for path in ["/", "/nodes", "/users", "/sources", "/settings/template"]:
        assert client.get(path).headers["Location"].endswith("/login")


def test_login_rejects_bad_password_and_rate_limits(app):
    client = app.test_client()
    token = csrf(client.get("/login").text)
    codes = [client.post("/login", data={"username": "admin", "password": "nope", "csrf_token": token}).status_code for _ in range(6)]
    assert codes[:5] == [200] * 5
    assert codes[5] == 429


def test_post_without_csrf_is_rejected(admin):
    response = admin.client.post("/users", data={"username": "mallory"}, follow_redirects=True)
    assert "页面已过期" in response.text
    assert "mallory" not in admin.get("/users").text


def test_next_parameter_cannot_redirect_offsite(admin):
    add_nodes(admin, "trojan://pw@a.example.com:443#A")
    node_id = node_ids(admin)[0]
    response = admin.post(f"/nodes/{node_id}/toggle", data={"next": "//evil.example"})
    assert response.headers["Location"] == "/nodes"
    page = admin.get(f"/nodes/{node_id}/edit?next=javascript:alert(1)").text
    assert "javascript:" not in page


def test_all_pages_render(admin):
    create_user(admin)
    add_nodes(admin, "trojan://pw@a.example.com:443#A")
    for path in ["/", "/sources", "/nodes", "/nodes/new", "/users", "/users/1", "/settings/template", "/nodes/1/edit"]:
        assert admin.get(path).status_code == 200, path


# ---------- users & subscriptions ----------

def test_subscription_contains_only_bound_enabled_nodes(admin):
    add_nodes(admin, "trojan://pw@a.example.com:443#A\ntrojan://pw@b.example.com:443#B")
    ids = node_ids(admin)
    user_id = create_user(admin)
    admin.post(f"/users/{user_id}", data={"username": "alice", "enabled": "1", "node_ids": ids})
    admin.post(f"/nodes/{ids[1]}/toggle")

    response = admin.client.get(sub_path(admin, user_id), headers={"User-Agent": "clash-verge/2.0"})
    assert response.status_code == 200
    assert "filename*=UTF-8''alice" in response.headers["Content-Disposition"]
    doc = yaml.safe_load(response.text)
    assert [p["name"] for p in doc["proxies"]] == ["A"]

    detail = admin.get(f"/users/{user_id}").text
    assert "clash-verge/2.0" in detail


def test_preview_does_not_count_as_fetch(admin):
    user_id = create_user(admin)
    assert admin.get(f"/users/{user_id}/preview").status_code == 200
    assert "从未" in admin.get(f"/users/{user_id}").text


def test_disabled_user_and_reset_token_invalidate_link(admin):
    user_id = create_user(admin)
    old = sub_path(admin, user_id)
    admin.post(f"/users/{user_id}/reset-token")
    assert admin.client.get(old).status_code == 404
    new = sub_path(admin, user_id)
    assert admin.client.get(new).status_code == 200
    admin.post(f"/users/{user_id}/toggle")
    assert admin.client.get(new).status_code == 404


def test_duplicate_username_is_reported(admin):
    create_user(admin, "bob")
    response = admin.post("/users", data={"username": "bob"}, follow_redirects=True)
    assert "用户名已存在" in response.text


# ---------- nodes ----------

def test_manual_import_accepts_uri_lines_and_proxies_block(admin):
    response = add_nodes(admin, "trojan://pw@a.example.com:443#T1\nss://YWVzLTI1Ni1nY206cHc=@b.example.com:8388#S1")
    assert "已添加 2 个节点" in response.text
    response = add_nodes(admin, "proxies:\n  - {name: Y1, type: socks5, server: c, port: 1}\n  - {name: Y2, type: http, server: d, port: 2}")
    assert "已添加 2 个节点" in response.text
    assert len(node_ids(admin)) == 4


def test_bulk_enable_disable_delete(admin):
    add_nodes(admin, "trojan://pw@a.example.com:443#A\ntrojan://pw@b.example.com:443#B")
    ids = node_ids(admin)
    admin.post("/nodes/bulk", data={"action": "disable", "node_ids": ids})
    assert len(node_ids(admin, "?status=disabled")) == 2
    admin.post("/nodes/bulk", data={"action": "delete", "node_ids": ids})
    assert node_ids(admin) == []


@pytest.mark.parametrize(
    "uri, expected",
    [
        ("trojan://secret@h.example.com:443?sni=s.example.com#Name", {"type": "trojan", "server": "h.example.com", "port": 443, "password": "secret", "sni": "s.example.com"}),
        ("ss://YWVzLTI1Ni1nY206cHc=@b.example.com:8388#S1", {"type": "ss", "cipher": "aes-256-gcm", "password": "pw", "port": 8388}),
        ("hy2://pw@h.example.com:8443#H", {"type": "hysteria2", "password": "pw"}),
        ("vless://uuid-1@h.example.com:443?security=reality&pbk=KEY&sid=ab#V", {"type": "vless", "uuid": "uuid-1", "tls": True}),
    ],
)
def test_parse_proxy_uri(uri, expected):
    config = app_module.parse_proxy_uri(uri)
    for key, value in expected.items():
        assert config[key] == value


# ---------- source sync ----------

@pytest.fixture()
def upstream(tmp_path):
    body = tmp_path / "sub.yaml"
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    handler.log_message = lambda *args: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield body, f"http://127.0.0.1:{server.server_port}/sub.yaml"
    server.shutdown()


def test_sync_keeps_bindings_and_custom_names_and_marks_stale(admin, upstream):
    body, url = upstream
    body.write_text(
        "proxies:\n"
        "  - {name: A, type: trojan, server: a, port: 1, password: old}\n"
        "  - {name: B, type: trojan, server: b, port: 1, password: x}\n"
        "  - {name: C, type: trojan, server: c, port: 1, password: x}\n"
    )
    response = admin.post("/sources", data={"name": "S", "url": url, "sync_now": "1"}, follow_redirects=True)
    assert "新增 3" in response.text
    ids = dict((name, nid) for nid, name in re.findall(r'/nodes/(\d+)/edit[^"]*">([^<]+)</a>', admin.get("/nodes").text))
    user_id = create_user(admin)
    admin.post(f"/users/{user_id}", data={"username": "alice", "enabled": "1", "node_ids": list(ids.values())})
    admin.post(f"/nodes/{ids['B']}/edit", data={"name": "B-custom", "enabled": "1"})

    # upstream rotates A's password, drops C, adds D
    body.write_text(
        "proxies:\n"
        "  - {name: A, type: trojan, server: a, port: 1, password: NEW}\n"
        "  - {name: B, type: trojan, server: b, port: 1, password: x}\n"
        "  - {name: D, type: trojan, server: d, port: 1, password: x}\n"
    )
    response = admin.post("/sources/1/sync", follow_redirects=True)
    assert "上游已移除 1 个" in response.text

    preview = admin.get(f"/users/{user_id}/preview").text
    assert "password: NEW" in preview  # same node id updated in place, binding kept
    assert "B-custom" in preview  # local rename survives sync
    assert "name: D" not in preview  # new upstream nodes are not auto-bound
    stale = admin.get("/nodes?status=stale").text
    assert ">C<" in stale and ">A<" not in stale


def test_sync_failure_is_recorded(admin):
    admin.post("/sources", data={"name": "Broken", "url": "http://127.0.0.1:9/none"})
    response = admin.post("/sources/1/sync", follow_redirects=True)
    assert "同步失败" in response.text


# ---------- node ordering ----------

def test_sort_rule_parsing():
    rules = app_module.parse_sort_rules("香港|HK\n# comment\n\n日本 | JP |\n")
    assert rules == [["香港", "hk"], ["日本", "jp"]]
    assert app_module.sort_priority("🇭🇰 香港 01", rules) == 0
    assert app_module.sort_priority("jp-tokyo", rules) == 1
    assert app_module.sort_priority("US", rules) == 2


def test_keyword_order_applies_to_proxies_and_groups(admin):
    add_nodes(admin, "trojan://p@a:1#US-1\ntrojan://p@b:1#JP-1\ntrojan://p@c:1#HK-1\ntrojan://p@d:1#US-2")
    user_id = create_user(admin)
    admin.post(f"/users/{user_id}", data={"username": "alice", "enabled": "1", "node_ids": node_ids(admin)})
    before = [p["name"] for p in yaml.safe_load(admin.get(f"/users/{user_id}/preview").text)["proxies"]]

    admin.post("/settings/node-order", data={"sort_keywords": "HK\nJP"})
    doc = yaml.safe_load(admin.get(f"/users/{user_id}/preview").text)
    names = [p["name"] for p in doc["proxies"]]
    assert names[:2] == ["HK-1", "JP-1"]
    assert [n for n in names if n.startswith("US")] == [n for n in before if n.startswith("US")]
    group = doc["proxy-groups"][0]["proxies"]
    assert [n for n in group if n in names] == names

    admin.post("/settings/node-order", data={"sort_keywords": ""})
    assert [p["name"] for p in yaml.safe_load(admin.get(f"/users/{user_id}/preview").text)["proxies"]] == before


# ---------- template & group defaults ----------

TEMPLATE = """
mixed-port: 7890
proxy-groups:
  - {name: Proxy, type: select, proxies: [__PROXIES__, DIRECT]}
  - {name: Video, type: select, proxies: [Proxy, __PROXIES__, DIRECT]}
  - {name: Microsoft, type: select, proxies: [__PROXIES__, DIRECT]}
  - {name: Direct, type: select, proxies: [DIRECT]}
rules:
  - MATCH,Proxy
"""


@pytest.mark.parametrize("bad", ["- a list", "a: [", "just text"])
def test_invalid_template_is_rejected_without_crash(admin, bad):
    response = admin.post("/settings/template", data={"template": bad}, follow_redirects=True)
    assert response.status_code == 200
    assert "模板无效" in response.text


def test_group_defaults_reorder_and_block_cycles(admin):
    admin.post("/settings/template", data={"template": TEMPLATE})
    add_nodes(admin, "trojan://p@a:1#N1")
    user_id = create_user(admin)
    admin.post(f"/users/{user_id}", data={"username": "alice", "enabled": "1", "node_ids": node_ids(admin)})

    page = admin.get("/settings/template").text
    names = re.findall(r'name="group_name" value="([^"]+)"', page)
    assert names == ["Proxy", "Video", "Microsoft"]  # fixed DIRECT-only group is not configurable
    proxy_options = re.findall(r'<option value="([^"]*)"', page.split('value="Proxy"', 1)[1].split("</select>", 1)[0])
    assert "Video" not in proxy_options  # Video references Proxy -> would be a cycle

    wanted = {"Microsoft": "DIRECT", "Video": "__PROXIES__", "Proxy": "Video"}  # last one is a forged cycle
    admin.post("/settings/group-defaults", data={"group_name": names, "group_choice": [wanted.get(n, "") for n in names]})
    groups = {g["name"]: g["proxies"] for g in yaml.safe_load(admin.get(f"/users/{user_id}/preview").text)["proxy-groups"]}
    assert groups["Microsoft"] == ["DIRECT", "N1"]
    assert groups["Video"] == ["N1", "Proxy", "DIRECT"]
    assert groups["Proxy"] == ["N1", "DIRECT"]


def test_spoofed_x_real_ip_cannot_bypass_rate_limit(app):
    client = app.test_client()
    token = csrf(client.get("/login").text)
    codes = []
    for i in range(6):
        response = client.post(
            "/login",
            data={"username": "admin", "password": "nope", "csrf_token": token},
            headers={"X-Real-IP": f"10.0.0.{i}"},
            environ_base={"REMOTE_ADDR": "203.0.113.7"},
        )
        codes.append(response.status_code)
    assert codes[5] == 429


@pytest.mark.parametrize(
    "key, expected",
    [
        ("+.bilivideo.+", ["+.bilivideo.com", "+.bilivideo.cn", "+.bilivideo.net"]),
        ("+.qq.com", ["+.qq.com"]),
        ("geosite:cn", ["geosite:cn"]),
        ("rule-set:direct", ["rule-set:direct"]),
        ("a.+.example.com", []),
        ("xbox.*.*.microsoft.com", ["xbox.*.*.microsoft.com"]),
    ],
)
def test_expand_policy_domain(key, expected):
    assert app_module.expand_policy_domain(key) == expected


def test_subscription_fixes_wildcards_rejected_by_new_mihomo(admin):
    template = TEMPLATE + "dns:\n  nameserver-policy: {'+.qq.com': 119.29.29.29, '+.bilivideo.+': 119.29.29.29}\n"
    admin.post("/settings/template", data={"template": template})
    user_id = create_user(admin)
    policy = yaml.safe_load(admin.get(f"/users/{user_id}/preview").text)["dns"]["nameserver-policy"]
    assert policy == {
        "+.qq.com": "119.29.29.29",
        "+.bilivideo.com": "119.29.29.29",
        "+.bilivideo.cn": "119.29.29.29",
        "+.bilivideo.net": "119.29.29.29",
    }



def edit_manual_node(admin, node_id, name, config_text):
    return admin.post(f"/nodes/{node_id}/edit", data={"name": name, "enabled": "1", "config_text": config_text})


def node_config_text(admin, node_id):
    import html
    page = admin.get(f"/nodes/{node_id}/edit").text
    return html.unescape(re.search(r'<textarea name="config_text"[^>]*>(.*?)</textarea>', page, re.S).group(1))


def test_renaming_manual_node_via_name_field(admin):
    add_nodes(admin, "trojan://pw@a.example.com:443#Old")
    node_id = node_ids(admin)[0]
    edit_manual_node(admin, node_id, "New", node_config_text(admin, node_id))  # config text still says "Old"
    assert ">New<" in admin.get("/nodes").text
    assert "name: New" in node_config_text(admin, node_id)
    user_id = create_user(admin)
    admin.post(f"/users/{user_id}", data={"username": "alice", "enabled": "1", "node_ids": [node_id]})
    assert [p["name"] for p in yaml.safe_load(admin.get(f"/users/{user_id}/preview").text)["proxies"]] == ["New"]


def test_renaming_manual_node_via_config(admin):
    add_nodes(admin, "trojan://pw@a.example.com:443#Old")
    node_id = node_ids(admin)[0]
    edit_manual_node(admin, node_id, "Old", node_config_text(admin, node_id).replace("name: Old", "name: FromYaml"))
    assert ">FromYaml<" in admin.get("/nodes").text


def test_name_field_wins_when_both_changed(admin):
    add_nodes(admin, "trojan://pw@a.example.com:443#Old")
    node_id = node_ids(admin)[0]
    edit_manual_node(admin, node_id, "FromField", node_config_text(admin, node_id).replace("name: Old", "name: FromYaml"))
    assert ">FromField<" in admin.get("/nodes").text
    assert "name: FromField" in node_config_text(admin, node_id)
