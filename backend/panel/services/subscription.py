from __future__ import annotations

import hashlib
import json
import secrets

import yaml


def build_subscription(proxies, template_text="", node_order_keywords=""):
    if template_text:
        doc = yaml.safe_load(template_text) or {}
        if not isinstance(doc, dict):
            raise ValueError("模板顶层必须是 YAML 对象")
    else:
        doc = default_subscription()
    ordered_proxies = sort_proxies_by_keywords(proxies, node_order_keywords)
    proxy_names = [proxy["name"] for proxy in ordered_proxies]
    doc["proxies"] = ordered_proxies
    doc["proxy-groups"] = apply_proxy_group_names(doc.get("proxy-groups"), proxy_names)
    if "rules" not in doc:
        doc["rules"] = ["MATCH,Proxy"]
    return doc


def parse_order_keywords(value):
    if isinstance(value, (list, tuple)):
        candidates = value
    else:
        text = str(value or "")
        for delimiter in [",", "，", ";", "；"]:
            text = text.replace(delimiter, "\n")
        candidates = text.splitlines()
    return [item.strip() for item in candidates if str(item).strip()]


def sort_proxies_by_keywords(proxies, node_order_keywords=""):
    keywords = parse_order_keywords(node_order_keywords)
    if not keywords:
        return list(proxies)

    def sort_key(item):
        name = str(item.get("name", ""))
        for index, keyword in enumerate(keywords):
            if keyword in name:
                return index
        return len(keywords)

    return [item for _, item in sorted(enumerate(proxies), key=lambda pair: (sort_key(pair[1]), pair[0]))]


def default_subscription():
    return {
        "mixed-port": 7890,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "info",
        "proxies": [],
        "proxy-groups": [{"name": "Proxy", "type": "select", "proxies": ["__PROXIES__"]}],
        "rules": ["MATCH,Proxy"],
    }


def apply_proxy_group_names(groups, proxy_names):
    if not isinstance(groups, list) or not groups:
        return [{"name": "Proxy", "type": "select", "proxies": proxy_names}]
    result = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        item = dict(group)
        item["proxies"] = expand_proxy_placeholders(item.get("proxies"), proxy_names)
        result.append(item)
    return result or [{"name": "Proxy", "type": "select", "proxies": proxy_names}]


def expand_proxy_placeholders(value, proxy_names):
    if value is None or not isinstance(value, list):
        return proxy_names
    expanded = []
    for item in value:
        if item == "__PROXIES__":
            expanded.extend(proxy_names)
        else:
            expanded.append(item)
    return expanded


def validate_template(template_text):
    data = yaml.safe_load(template_text)
    if not isinstance(data, dict):
        raise ValueError("顶层必须是 YAML 对象")
    if "proxies" in data and not isinstance(data["proxies"], list):
        raise ValueError("proxies 必须是列表，或者删掉让系统自动生成")
    if "proxy-groups" in data and not isinstance(data["proxy-groups"], list):
        raise ValueError("proxy-groups 必须是列表")


def extract_template_from_config(config_text):
    if not config_text:
        raise ValueError("请粘贴完整 mihomo/Clash 配置")
    data = yaml.safe_load(config_text)
    if not isinstance(data, dict):
        raise ValueError("配置顶层必须是 YAML 对象")
    proxies = data.get("proxies") or []
    if not isinstance(proxies, list):
        raise ValueError("proxies 必须是列表")
    proxy_names = {str(proxy.get("name")) for proxy in proxies if isinstance(proxy, dict) and proxy.get("name")}
    template = dict(data)
    template.pop("proxies", None)
    groups = template.get("proxy-groups")
    if isinstance(groups, list):
        template["proxy-groups"] = [extract_proxy_group_template(group, proxy_names) for group in groups if isinstance(group, dict)]
    elif proxy_names:
        template["proxy-groups"] = [{"name": "Proxy", "type": "select", "proxies": ["__PROXIES__"]}]
    return yaml.safe_dump(template, allow_unicode=True, sort_keys=False)


def extract_proxy_group_template(group, proxy_names):
    item = dict(group)
    values = item.get("proxies")
    if not isinstance(values, list):
        item["proxies"] = ["__PROXIES__"]
        return item
    kept = []
    removed_proxy = False
    has_placeholder = False
    for value in values:
        if value == "__PROXIES__":
            has_placeholder = True
        elif str(value) in proxy_names:
            removed_proxy = True
        else:
            kept.append(value)
    if removed_proxy or has_placeholder:
        kept = ["__PROXIES__"] + [value for value in kept if value != "__PROXIES__"]
    item["proxies"] = kept
    return item


def default_template_text():
    return yaml.safe_dump(default_subscription(), allow_unicode=True, sort_keys=False)


def config_hash(config):
    raw = json.dumps(config, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def unique_name(name, used):
    candidate = str(name)
    if candidate not in used:
        used.add(candidate)
        return candidate
    index = 2
    while f"{candidate} {index}" in used:
        index += 1
    final = f"{candidate} {index}"
    used.add(final)
    return final


def new_token():
    return secrets.token_urlsafe(32)
