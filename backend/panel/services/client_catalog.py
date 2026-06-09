from panel.models import ClientDownload


CLIENT_PLATFORMS = [
    {"key": "ios", "label": "iOS"},
    {"key": "mac", "label": "macOS"},
    {"key": "windows", "label": "Windows"},
    {"key": "linux", "label": "Linux"},
    {"key": "android", "label": "Android"},
]


CLIENT_CATALOG = [
    {
        "key": "shadowrocket_ios",
        "name": "Shadowrocket",
        "platform_code": "ios",
        "platform": "iOS",
        "version": "App Store",
        "link_url": "https://apps.apple.com/us/app/shadowrocket/id932747118",
        "icon_url": "https://is1-ssl.mzstatic.com/image/thumb/Purple221/v4/74/c5/08/74c508c7-4491-1eb7-4e50-4de29c219386/AppIcon-0-0-1x_U007epad-0-1-0-sRGB-85-220.png/512x512bb.jpg",
        "repo": "",
        "file_available": False,
        "sort_order": 10,
        "remark": "App Store",
    },
    {
        "key": "stash_ios",
        "name": "Stash",
        "platform_code": "ios",
        "platform": "iOS",
        "version": "App Store",
        "link_url": "https://apps.apple.com/us/app/stash-rule-based-proxy/id1596063349",
        "icon_url": "https://is1-ssl.mzstatic.com/image/thumb/Purple221/v4/fc/64/5b/fc645bde-b87f-935c-0ee4-17826a9876dd/AppIcon-0-1x_U007epad-0-0-0-1-0-0-sRGB-85-220-0.png/512x512bb.jpg",
        "repo": "",
        "file_available": False,
        "sort_order": 20,
        "remark": "App Store",
    },
    {
        "key": "clash_verge_rev_mac",
        "name": "Clash Verge Rev",
        "platform_code": "mac",
        "platform": "macOS",
        "link_url": "https://github.com/clash-verge-rev/clash-verge-rev/releases/latest",
        "icon_url": "https://raw.githubusercontent.com/clash-verge-rev/clash-verge-rev/main/src-tauri/icons/128x128.png",
        "repo": "clash-verge-rev/clash-verge-rev",
        "file_available": True,
        "sort_order": 110,
        "remark": "macOS arm64",
    },
    {
        "key": "mihomo_party_mac",
        "name": "Mihomo Party",
        "platform_code": "mac",
        "platform": "macOS",
        "link_url": "https://github.com/mihomo-party-org/mihomo-party/releases/latest",
        "icon_url": "https://raw.githubusercontent.com/mihomo-party-org/clash-party/smart_core/build/icon.png",
        "repo": "mihomo-party-org/mihomo-party",
        "file_available": True,
        "sort_order": 120,
        "remark": "macOS arm64",
    },
    {
        "key": "clash_verge_rev_windows",
        "name": "Clash Verge Rev",
        "platform_code": "windows",
        "platform": "Windows",
        "link_url": "https://github.com/clash-verge-rev/clash-verge-rev/releases/latest",
        "icon_url": "https://raw.githubusercontent.com/clash-verge-rev/clash-verge-rev/main/src-tauri/icons/128x128.png",
        "repo": "clash-verge-rev/clash-verge-rev",
        "file_available": True,
        "sort_order": 210,
        "remark": "Windows amd64",
    },
    {
        "key": "mihomo_party_windows",
        "name": "Mihomo Party",
        "platform_code": "windows",
        "platform": "Windows",
        "link_url": "https://github.com/mihomo-party-org/mihomo-party/releases/latest",
        "icon_url": "https://raw.githubusercontent.com/mihomo-party-org/clash-party/smart_core/build/icon.png",
        "repo": "mihomo-party-org/mihomo-party",
        "file_available": True,
        "sort_order": 220,
        "remark": "Windows amd64",
    },
    {
        "key": "clash_verge_rev_linux",
        "name": "Clash Verge Rev",
        "platform_code": "linux",
        "platform": "Linux",
        "link_url": "https://github.com/clash-verge-rev/clash-verge-rev/releases/latest",
        "icon_url": "https://raw.githubusercontent.com/clash-verge-rev/clash-verge-rev/main/src-tauri/icons/128x128.png",
        "repo": "clash-verge-rev/clash-verge-rev",
        "file_available": True,
        "sort_order": 310,
        "remark": "Linux amd64",
    },
    {
        "key": "mihomo_party_linux",
        "name": "Mihomo Party",
        "platform_code": "linux",
        "platform": "Linux",
        "link_url": "https://github.com/mihomo-party-org/mihomo-party/releases/latest",
        "icon_url": "https://raw.githubusercontent.com/mihomo-party-org/clash-party/smart_core/build/icon.png",
        "repo": "mihomo-party-org/mihomo-party",
        "file_available": True,
        "sort_order": 320,
        "remark": "Linux amd64",
    },
    {
        "key": "v2rayng_android",
        "name": "v2rayNG",
        "platform_code": "android",
        "platform": "Android",
        "link_url": "https://github.com/2dust/v2rayNG/releases/latest",
        "icon_url": "https://raw.githubusercontent.com/2dust/v2rayNG/master/V2rayNG/app/src/main/ic_launcher-web.png",
        "repo": "2dust/v2rayNG",
        "file_available": True,
        "sort_order": 410,
        "remark": "APK",
    },
    {
        "key": "clash_meta_android",
        "name": "Clash Meta for Android",
        "platform_code": "android",
        "platform": "Android",
        "link_url": "https://github.com/MetaCubeX/ClashMetaForAndroid/releases/latest",
        "icon_url": "https://raw.githubusercontent.com/MetaCubeX/ClashMetaForAndroid/main/app/src/main/ic_launcher-playstore.png",
        "repo": "MetaCubeX/ClashMetaForAndroid",
        "file_available": True,
        "sort_order": 420,
        "remark": "APK",
    },
]


CATALOG_BY_KEY = {item["key"]: item for item in CLIENT_CATALOG}


def catalog_for(item):
    return CATALOG_BY_KEY.get(item.catalog_key or "")


def ensure_client_catalog():
    for entry in CLIENT_CATALOG:
        item = ClientDownload.objects.filter(catalog_key=entry["key"]).first()
        if not item:
            item = ClientDownload.objects.filter(
                catalog_key="",
                name=entry["name"],
                platform_code=entry["platform_code"],
            ).first()
        defaults = {
            "catalog_key": entry["key"],
            "name": entry["name"],
            "platform_code": entry["platform_code"],
            "platform": entry["platform"],
            "download_url": entry["link_url"],
            "release_url": entry["link_url"],
            "remote_url": "",
            "auto_update_latest": True,
            "sort_order": entry["sort_order"],
            "remark": entry["remark"],
        }
        if item:
            for field, value in defaults.items():
                setattr(item, field, value)
            if not item.version:
                item.version = entry.get("version", "")
            if item.local_file:
                item.delivery_mode = ClientDownload.DELIVERY_FILE
                item.source_type = ClientDownload.SOURCE_LOCAL_FILE
            else:
                item.delivery_mode = ClientDownload.DELIVERY_LINK
                item.source_type = ClientDownload.SOURCE_EXTERNAL_LINK
            item.save()
        else:
            ClientDownload.objects.create(
                **defaults,
                version=entry.get("version", ""),
                delivery_mode=ClientDownload.DELIVERY_LINK,
                source_type=ClientDownload.SOURCE_EXTERNAL_LINK,
                enabled=True,
            )


def asset_matches(catalog, filename):
    lower = filename.lower()
    if not catalog.get("file_available"):
        return False
    if catalog["platform_code"] == "android":
        return lower.endswith(".apk") and not any(token in lower for token in ["x86", "wear", "tv"])
    if catalog["platform_code"] == "mac":
        if any(token in lower for token in ["x64", "amd64", "x86_64", "intel"]):
            return False
        is_macos_asset = any(token in lower for token in ["darwin", "mac", "macos"]) or lower.endswith(".dmg")
        is_arm_asset = any(token in lower for token in ["arm64", "aarch64", "apple"])
        return is_macos_asset and is_arm_asset
    if catalog["platform_code"] == "linux":
        if any(token in lower for token in ["arm64", "aarch64", "armv7", "i386", "i686"]):
            return False
        return "linux" in lower and any(token in lower for token in ["x64", "amd64", "x86_64", ".appimage", ".deb"])
    if catalog["platform_code"] == "windows":
        if any(token in lower for token in ["arm64", "aarch64", "armv7", "i386", "i686"]):
            return False
        return any(token in lower for token in ["win", "windows"]) and any(
            token in lower for token in ["x64", "amd64", "x86_64", ".exe", ".msi"]
        )
    return False


def asset_score(catalog, filename):
    lower = filename.lower()
    score = 0
    for token in ["universal", "x64", "amd64", "x86_64", "arm64", "aarch64"]:
        if token in lower:
            score += 5
    for token in [".dmg", ".appimage", ".apk", ".deb"]:
        if token in lower:
            score += 3
    if catalog["key"].split("_")[0] in lower:
        score += 1
    return score
