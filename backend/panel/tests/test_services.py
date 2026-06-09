import base64
import json

import pytest
import yaml

from panel.services.proxy_parser import parse_manual_node
from panel.services.subscription import build_subscription, extract_template_from_config


def test_parse_yaml_node():
    node = parse_manual_node(
        """
name: HK 01
type: ss
server: example.com
port: 8388
cipher: aes-128-gcm
password: secret
"""
    )
    assert node["name"] == "HK 01"
    assert node["type"] == "ss"


def encode(value):
    raw = value.encode() if isinstance(value, str) else value
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


@pytest.mark.parametrize(
    ("uri", "proxy_type", "field", "value"),
    [
        ("vless://uuid@example.com:443?security=tls#VLESS", "vless", "uuid", "uuid"),
        ("trojan://secret@example.com:443#Trojan", "trojan", "password", "secret"),
        ("hysteria://secret@example.com:443#HY", "hysteria", "password", "secret"),
        ("hy2://secret@example.com:443#HY2", "hysteria2", "password", "secret"),
        ("tuic://secret@example.com:443#TUIC", "tuic", "password", "secret"),
        ("wireguard://private@example.com:51820#WG", "wireguard", "private-key", "private"),
        ("socks5://user:pass@example.com:1080#SOCKS", "socks", "username", "user"),
        ("https://user:pass@example.com:443#HTTP", "http", "password", "pass"),
    ],
)
def test_parse_url_style_protocols(uri, proxy_type, field, value):
    node = parse_manual_node(uri)
    assert node["type"] == proxy_type
    assert node[field] == value


def test_parse_vmess_uri():
    payload = encode(
        json.dumps(
            {
                "v": "2",
                "ps": "VMess",
                "add": "example.com",
                "port": "443",
                "id": "uuid",
                "aid": "0",
                "net": "ws",
                "path": "/ws",
                "host": "cdn.example.com",
                "tls": "tls",
            }
        )
    )
    node = parse_manual_node(f"vmess://{payload}")
    assert node["type"] == "vmess"
    assert node["ws-opts"]["path"] == "/ws"


def test_parse_ss_uri():
    node = parse_manual_node(f"ss://{encode('aes-128-gcm:secret')}@example.com:8388#SS")
    assert node["type"] == "ss"
    assert node["password"] == "secret"


def test_parse_ssr_uri():
    main = f"example.com:8388:origin:aes-128-cfb:plain:{encode('secret')}/?remarks={encode('SSR')}"
    node = parse_manual_node(f"ssr://{encode(main)}")
    assert node["type"] == "ssr"
    assert node["name"] == "SSR"


def test_build_subscription_expands_proxy_placeholder():
    doc = build_subscription(
        [{"name": "HK 01", "type": "ss", "server": "example.com", "port": 8388}],
        "proxy-groups:\n- name: Proxy\n  type: select\n  proxies:\n  - __PROXIES__\nrules:\n- MATCH,Proxy\n",
    )
    assert doc["proxy-groups"][0]["proxies"] == ["HK 01"]


def test_build_subscription_orders_proxies_by_keywords():
    doc = build_subscription(
        [
            {"name": "美国 01", "type": "ss", "server": "us.example.com", "port": 8388},
            {"name": "日本 01", "type": "ss", "server": "jp.example.com", "port": 8388},
            {"name": "香港 01", "type": "ss", "server": "hk.example.com", "port": 8388},
            {"name": "新加坡 01", "type": "ss", "server": "sg.example.com", "port": 8388},
        ],
        "proxy-groups:\n- name: Proxy\n  type: select\n  proxies:\n  - __PROXIES__\n",
        "香港\n日本",
    )
    assert [item["name"] for item in doc["proxies"]] == ["香港 01", "日本 01", "美国 01", "新加坡 01"]
    assert doc["proxy-groups"][0]["proxies"] == ["香港 01", "日本 01", "美国 01", "新加坡 01"]


def test_extract_template_removes_proxy_names():
    template = extract_template_from_config(
        """
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
  - DIRECT
rules:
- MATCH,Proxy
"""
    )
    data = yaml.safe_load(template)
    assert "proxies" not in data
    assert data["proxy-groups"][0]["proxies"] == ["__PROXIES__", "DIRECT"]
