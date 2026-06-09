from __future__ import annotations

import base64
import json
from urllib.parse import parse_qs, unquote, urlparse

import yaml


def normalize_proxy(config):
    if not isinstance(config, dict):
        raise ValueError("节点配置必须是 YAML 对象")
    if not config.get("name"):
        raise ValueError("节点缺少 name")
    if not config.get("type"):
        raise ValueError("节点缺少 type")
    config = dict(config)
    config["name"] = str(config["name"])
    config["type"] = str(config["type"]).lower()
    return config


def parse_manual_node(text):
    if not text:
        raise ValueError("请输入 URI 或 YAML 节点配置")
    if "://" in text and not text.lstrip().startswith("{"):
        return parse_proxy_uri(text)
    return normalize_proxy(yaml.safe_load(text))


def parse_proxy_uri(uri):
    parsed = urlparse(uri)
    scheme = parsed.scheme.lower()
    if scheme == "vmess":
        return parse_vmess(uri)
    if scheme in {"vless", "trojan", "hysteria", "hysteria2", "hy2", "tuic", "wireguard", "socks", "socks5", "http", "https"}:
        return parse_url_style_proxy(uri, scheme)
    if scheme == "ss":
        return parse_ss(uri)
    if scheme == "ssr":
        return parse_ssr(uri)
    raise ValueError(f"暂不支持的 URI 协议：{scheme}")


def parse_vmess(uri):
    payload = uri.split("://", 1)[1]
    data = json.loads(b64decode_text(payload))
    network = data.get("net")
    config = {
        "name": data.get("ps") or data.get("add") or "vmess",
        "type": "vmess",
        "server": data.get("add"),
        "port": int(data.get("port")),
        "uuid": data.get("id"),
        "alterId": int(data.get("aid") or 0),
        "cipher": data.get("scy") or data.get("cipher") or "auto",
        "tls": str(data.get("tls", "")).lower() == "tls",
    }
    if network:
        config["network"] = network
    if network == "ws":
        config["ws-opts"] = {"path": data.get("path") or "/", "headers": {"Host": data.get("host") or ""}}
    if data.get("sni"):
        config["servername"] = data["sni"]
    return normalize_proxy(clean_empty(config))


def parse_url_style_proxy(uri, scheme):
    parsed = urlparse(uri)
    query = {k: v[-1] for k, v in parse_qs(parsed.query).items()}
    proxy_type = {"hy2": "hysteria2", "socks5": "socks", "https": "http"}.get(scheme, scheme)
    config = {
        "name": unquote(parsed.fragment) if parsed.fragment else parsed.hostname or proxy_type,
        "type": proxy_type,
        "server": parsed.hostname,
        "port": parsed.port,
    }
    username = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    if proxy_type == "vless":
        config["uuid"] = username
        config["tls"] = query.get("security") in {"tls", "reality"} or query.get("tls") == "1"
        if query.get("security") == "reality":
            config["reality-opts"] = clean_empty({"public-key": query.get("pbk"), "short-id": query.get("sid")})
    elif proxy_type in {"trojan", "hysteria", "hysteria2", "tuic"}:
        config["password"] = username or password
    elif proxy_type == "wireguard":
        config["private-key"] = username or password
    elif proxy_type in {"socks", "http"}:
        if username:
            config["username"] = username
        if password:
            config["password"] = password
    for src, dst in {
        "type": "network",
        "encryption": "cipher",
        "sni": "sni",
        "fp": "client-fingerprint",
        "alpn": "alpn",
        "host": "host",
        "path": "path",
        "flow": "flow",
        "allowInsecure": "skip-cert-verify",
    }.items():
        if src in query:
            config[dst] = query[src]
    return normalize_proxy(clean_empty(config))


def parse_ss(uri):
    body = uri.split("://", 1)[1]
    name = "shadowsocks"
    if "#" in body:
        body, frag = body.split("#", 1)
        name = unquote(frag)
    if "@" not in body:
        decoded = b64decode_text(body)
        if "#" in decoded:
            decoded, frag = decoded.split("#", 1)
            name = unquote(frag)
        body = decoded
    auth, server = body.rsplit("@", 1)
    if ":" not in auth:
        auth = b64decode_text(auth)
    cipher, password = auth.split(":", 1)
    host, port = split_host_port(server)
    return normalize_proxy({"name": name, "type": "ss", "server": host, "port": int(port), "cipher": cipher, "password": password})


def parse_ssr(uri):
    decoded = b64decode_text(uri.split("://", 1)[1])
    parts = decoded.split("/?", 1)
    main = parts[0].split(":")
    if len(main) < 6:
        raise ValueError("SSR URI 格式不完整")
    query = {k: v[-1] for k, v in parse_qs(parts[1] if len(parts) > 1 else "").items()}
    name = b64decode_text(query.get("remarks", "")) if query.get("remarks") else main[0]
    return normalize_proxy({
        "name": name,
        "type": "ssr",
        "server": main[0],
        "port": int(main[1]),
        "cipher": main[3],
        "password": b64decode_text(main[5]),
        "obfs": main[4],
        "protocol": main[2],
    })


def b64decode_text(value):
    value = value.strip()
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode()).decode("utf-8")


def split_host_port(value):
    if value.startswith("["):
        host, port = value.rsplit("]:", 1)
        return host[1:], port
    return value.rsplit(":", 1)


def clean_empty(data):
    return {key: value for key, value in data.items() if value not in (None, "", {}, [])}
