from __future__ import annotations

from urllib.parse import urlparse

import requests
import yaml
from django.db import transaction
from django.utils import timezone

from panel.models import Node

from .nodes import save_node
from .proxy_parser import b64decode_text, normalize_proxy
from .subscription import config_hash, extract_template_from_config, validate_template


def sync_clash_source(source):
    response = requests.get(source.url, timeout=20, headers={"User-Agent": "proxypanel/1.0"})
    response.raise_for_status()
    text = decode_subscription_body(response.content)
    data = yaml.safe_load(text)
    if not isinstance(data, dict) or not isinstance(data.get("proxies"), list):
        raise ValueError("订阅不是有效的 mihomo/Clash YAML，缺少 proxies")
    parsed_nodes = []
    for item in data["proxies"]:
        if not isinstance(item, dict):
            continue
        config = normalize_proxy(item)
        parsed_nodes.append((config, yaml.safe_dump(item, allow_unicode=True, sort_keys=False)))

    with transaction.atomic():
        remote_hashes = set()
        created = 0
        updated = 0
        for config, raw_text in parsed_nodes:
            remote_hashes.add(config_hash(config))
            _, was_created = save_node(config, raw_text=raw_text, source=source)
            if was_created:
                created += 1
            else:
                updated += 1

        stale_nodes = Node.objects.filter(source=source).exclude(config_hash__in=remote_hashes)
        deleted = stale_nodes.count()
        stale_nodes.delete()

        source.last_synced_at = timezone.now()
        source.last_error = ""
        source.save(update_fields=["last_synced_at", "last_error"])

    return {
        "count": len(parsed_nodes),
        "created": created,
        "updated": updated,
        "deleted": deleted,
    }


def sync_source_with_error_record(source):
    try:
        return sync_clash_source(source)
    except Exception as exc:
        source.last_error = str(exc)
        source.save(update_fields=["last_error"])
        raise


def decode_subscription_body(content):
    text = content.decode("utf-8", errors="ignore").strip()
    if text.startswith(("proxies:", "mixed-port:", "port:", "proxy-groups:")):
        return text
    try:
        decoded = b64decode_text(text)
        if "proxies:" in decoded:
            return decoded
    except Exception:
        pass
    return text


def validate_remote_template_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("远程模板 URL 必须是 http 或 https 地址")


def fetch_template_from_url(url):
    response = requests.get(url, timeout=20, headers={"User-Agent": "proxypanel/1.0"})
    response.raise_for_status()
    text = response.text.strip()
    if not text:
        raise ValueError("远程模板为空")
    return text


def fetch_and_extract_template(url):
    validate_remote_template_url(url)
    config_text = fetch_template_from_url(url)
    template = extract_template_from_config(config_text)
    validate_template(template)
    return template
