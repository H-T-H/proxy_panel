from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

import requests
from django.core.files.base import ContentFile
from django.utils import timezone

from panel.models import ClientDownload
from panel.services.client_catalog import asset_matches, asset_score, catalog_for


def github_repo_from_url(url):
    parsed = urlparse(url or "")
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if parsed.netloc.lower() != "github.com" or len(parts) < 2:
        return None
    return parts[0], parts[1]


def filename_from_response(url, response):
    disposition = response.headers.get("content-disposition", "")
    for part in disposition.split(";"):
        part = part.strip()
        if part.lower().startswith("filename="):
            return part.split("=", 1)[1].strip('"') or "client-download"
    name = PurePosixPath(unquote(urlparse(response.url or url).path)).name
    return name or "client-download"


def latest_github_asset_url(item):
    catalog = catalog_for(item)
    if catalog:
        if not catalog.get("file_available") or not catalog.get("repo"):
            raise ValueError("该客户端不支持提供本地文件")
        owner, name = catalog["repo"].split("/", 1)
        response = requests.get(f"https://api.github.com/repos/{owner}/{name}/releases/latest", timeout=15)
        response.raise_for_status()
        data = response.json()
        assets = data.get("assets") or []
        matches = [
            asset
            for asset in assets
            if asset.get("browser_download_url") and asset_matches(catalog, asset.get("name", ""))
        ]
        if not matches:
            raise ValueError("最新 Release 没有匹配当前平台的 amd64 安装包")
        selected = sorted(
            matches,
            key=lambda asset: asset_score(catalog, asset.get("name", "")),
            reverse=True,
        )[0]
        return selected["browser_download_url"], data.get("tag_name") or ""

    repo = github_repo_from_url(item.release_url or item.remote_url)
    if not repo:
        return None, None
    owner, name = repo
    response = requests.get(f"https://api.github.com/repos/{owner}/{name}/releases/latest", timeout=15)
    response.raise_for_status()
    data = response.json()
    assets = data.get("assets") or []
    if not assets:
        raise ValueError("最新 Release 没有可下载文件")
    return assets[0]["browser_download_url"], data.get("tag_name") or ""


def fetch_client_download(item):
    if item.delivery_mode == ClientDownload.DELIVERY_FILE:
        item.source_type = ClientDownload.SOURCE_REMOTE_FETCH
        item.auto_update_latest = True
    if item.source_type != ClientDownload.SOURCE_REMOTE_FETCH:
        raise ValueError("只有远程拉取来源可以执行拉取")
    fetch_url = item.remote_url
    version = ""
    if item.auto_update_latest or item.catalog_key:
        latest_url, version = latest_github_asset_url(item)
        fetch_url = latest_url or fetch_url
    if not fetch_url:
        raise ValueError("请先填写远程拉取地址")

    response = requests.get(fetch_url, timeout=60)
    response.raise_for_status()
    filename = filename_from_response(fetch_url, response)
    if item.local_file:
        item.local_file.delete(save=False)
    item.local_file.save(filename, ContentFile(response.content), save=False)
    item.file_name = filename
    item.remote_url = fetch_url
    if version:
        item.version = version
    item.last_fetched_at = timezone.now()
    item.last_fetch_error = ""
    item.save(
        update_fields=[
            "local_file",
            "file_name",
            "remote_url",
            "source_type",
            "auto_update_latest",
            "version",
            "last_fetched_at",
            "last_fetch_error",
            "updated_at",
        ]
    )
    return item
