from __future__ import annotations

import yaml

from panel.models import Node

from .proxy_parser import normalize_proxy
from .subscription import config_hash


def save_node(config, raw_text="", source=None):
    config = normalize_proxy(config)
    digest = config_hash(config)
    source_name = source.name if source else "手动添加"
    defaults = {
        "name": config["name"],
        "type": config["type"],
        "raw_text": raw_text or "",
        "config": config,
        "source_name": source_name,
    }
    if source:
        node, created = Node.objects.update_or_create(source=source, config_hash=digest, defaults=defaults)
    else:
        node = Node.objects.create(config_hash=digest, **defaults)
        created = True
    return node, created


def formatted_node_config(node):
    return yaml.safe_dump(node.config, allow_unicode=True, sort_keys=False)


def node_sort_key(node):
    return (
        0 if node.source_id is None else 1,
        node.source_name or "",
        node.name or "",
        node.id or 0,
    )
