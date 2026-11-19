#!/usr/bin/env python3
"""Publish standalone NGi provider files and regenerate the searchable catalog."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from zipfile import BadZipFile, ZipFile

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install"
PLUGINS = ROOT / "plugins"
LIMIT = 256 * 1024
CATEGORIES = {"jav_censored", "jav_uncensored", "jav_amateur", "jav_fc2", "cn", "ea"}


def load_plugin(filename, data):
    suffix = Path(filename).suffix
    if suffix not in {".json", ".js"} or len(data) > LIMIT:
        raise ValueError("需要不超过 256 KiB 的 JSON 或 JS 插件文件")
    text = data.decode("utf-8").strip()
    if suffix == ".js":
        header, end, script = text.removeprefix("/* NGi-provider").partition("*/")
        if not text.startswith("/* NGi-provider") or not end or not script.strip():
            raise ValueError("JS 插件缺少 NGi-provider 元数据或脚本")
        text = header
    meta = json.loads(text)
    if not isinstance(meta, dict) or type(meta.get("api_version")) is not int or meta["api_version"] != 1:
        raise ValueError("需要 api_version 为 1 的插件元数据")
    plugin_id = meta.get("id")
    if not isinstance(plugin_id, str) or not re.fullmatch(r"javarchive|plugin_[a-z0-9_]{1,57}", plugin_id):
        raise ValueError("插件 ID 无效")
    if filename != f"{plugin_id}{suffix}":
        raise ValueError("插件文件名必须与 ID 一致")
    version = meta.get("version")
    if not isinstance(version, str) or len(version) > 32 or not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*)){2}", version):
        raise ValueError("版本需为三段数字，例如 1.0.0")
    name = meta.get("name")
    description = meta.get("description", "")
    if not isinstance(name, str) or not name.strip() or len(name.encode()) > 100:
        raise ValueError("插件名称无效")
    if not isinstance(description, str) or len(description.encode()) > 2000:
        raise ValueError("插件说明无效")
    categories = meta.get("categories")
    if not isinstance(categories, list) or not 1 <= len(categories) <= 6 or any(
        not isinstance(category, str) or category not in CATEGORIES for category in categories
    ):
        raise ValueError("影片分类无效")
    return {
        "id": plugin_id,
        "name": name,
        "version": version,
        "api_version": 1,
        "description": description,
        "categories": categories,
        "format": suffix[1:],
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def read_archive(archive):
    if archive.is_symlink() or not archive.is_file() or archive.stat().st_size > 2 * LIMIT:
        raise ValueError("ZIP 必须是普通文件，大小不超过 512 KiB")
    with ZipFile(archive) as bundle:
        entries = bundle.infolist()
        if len(entries) > 32:
            raise ValueError("ZIP 内的项目过多")
        plugins = []
        paths = set()
        for entry in entries:
            name = entry.orig_filename
            path = PurePosixPath(name)
            mode = stat.S_IFMT(entry.external_attr >> 16)
            parts = name.removesuffix("/").split("/")
            if any(part in {"", ".", ".."} or ":" in part for part in parts) or "\\" in name or "\0" in name:
                raise ValueError("ZIP 内含无效路径")
            if path in paths or mode not in ({0, stat.S_IFDIR} if entry.is_dir() else {0, stat.S_IFREG}):
                raise ValueError("ZIP 内含重复路径或非普通文件")
            paths.add(path)
            if entry.is_dir() or "__MACOSX" in path.parts or path.name in {".DS_Store", "Thumbs.db"}:
                continue
            plugins.append(entry)
        if len(plugins) != 1:
            raise ValueError("每个 ZIP 须包含一个插件文件")
        entry = plugins[0]
        if entry.file_size > LIMIT:
            raise ValueError("插件文件超过 256 KiB")
        data = bundle.read(entry)
    filename = PurePosixPath(entry.filename).name
    return filename, data, load_plugin(filename, data)


def scan_releases():
    latest = {}
    for file in sorted(PLUGINS.glob("*/*/*")):
        if file.is_symlink() or file.parent.is_symlink() or file.parent.parent.is_symlink():
            raise ValueError(f"{file.relative_to(ROOT)} 必须使用普通目录和文件")
        if not file.is_file():
            raise ValueError(f"{file.relative_to(ROOT)} 不是插件文件")
        with file.open("rb") as reader:
            meta = load_plugin(file.name, reader.read(LIMIT + 1))
        plugin_id = meta["id"]
        if file.parent.name != meta["version"] or file.parent.parent.name != plugin_id:
            raise ValueError(f"{file.relative_to(ROOT)} 与插件的 ID 或版本不符")
        version = version_key(meta)
        current = latest.get(plugin_id)
        if current and version == version_key(current):
            raise ValueError(f"{plugin_id} {meta['version']} 版本重复")
        if not current or version > version_key(current):
            latest[plugin_id] = meta
    return latest


def version_key(meta):
    return tuple(map(int, meta["version"].split(".")))


def deploy():
    latest = scan_releases()
    errors = []
    for archive in sorted(INSTALL.iterdir()):
        if archive.suffix.lower() != ".zip":
            continue
        try:
            filename, data, meta = read_archive(archive)
            folder = PLUGINS / meta["id"] / meta["version"]
            target = folder / filename
            if folder.exists() and (list(folder.iterdir()) != [target] or target.read_bytes() != data):
                raise ValueError("该版本已发布其他内容，请提高版本号后重新上传")
        except (ValueError, BadZipFile, RuntimeError, NotImplementedError) as error:
            errors.append(f"{archive.name!r}：{error}")
            continue

        if not folder.exists():
            folder.mkdir(parents=True)
            target.write_bytes(data)
        current = latest.get(meta["id"])
        if not current or version_key(meta) > version_key(current):
            latest[meta["id"]] = meta
        archive.unlink()
        print(f"已部署 {target.relative_to(ROOT)}")
    catalog = {"schema_version": 1, "plugins": [latest[key] for key in sorted(latest)]}
    (ROOT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return errors


if __name__ == "__main__":
    # Report ZIP failures only after the workflow pushes all valid packages.
    errors = deploy()
    Path(sys.argv[1]).write_text("\n".join(errors) + "\n" if errors else "", encoding="utf-8")
