#!/usr/bin/env python3
"""Import the original, frozen delivery archive; this does not rerun the study."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import unittest
import urllib.parse
import urllib.request
import zipfile

REPO = "Lammmmm/cpi-btc-study"
EXPECTED_BYTES = 41961194
EXPECTED_GIT_BLOB_SHA1 = "9504ecba47e6a4ffa6f83e9e5c694c71a3173cfe"
BUNDLE_NAME = "CPI_BTC_完整代码数据与测试.zip"
DELIVERY_NAMES = [
    "CPI_BTC_Final_Report.md", "CPI_BTC_Final_Report.pdf",
    "CPI_4指标完整事件数据库.csv", "CPI_总体核心交叉矩阵.xlsx",
    "CPI_暴热暴冷专项研究.csv", "CPI_第一波与反杀策略回测.csv",
    "CPI_交易规律速查表.pdf", "CPI_回测复现_README.md",
    "CPI_数据来源与完整性审计.csv",
]

def safe_member(info, root):
    name = info.filename
    path = PurePosixPath(name)
    if "\\" in name or path.is_absolute() or ".." in path.parts:
        raise ValueError("Unsafe archive path: " + name)
    if not path.parts or path.parts[0] != "cpi_upgrade" or ".git" in path.parts:
        raise ValueError("Unexpected archive path: " + name)
    if stat.S_ISLNK(info.external_attr >> 16):
        raise ValueError("Archive symlink is forbidden: " + name)
    target = root.joinpath(*path.parts)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("Archive path escapes the repository: " + name)
    return target

def verify_bundle(path):
    if path.stat().st_size != EXPECTED_BYTES:
        raise ValueError("Archive byte count differs from the original delivery")
    digest = hashlib.sha1(b"blob " + str(EXPECTED_BYTES).encode() + b"\0")
    sha256 = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
            sha256.update(block)
    if digest.hexdigest() != EXPECTED_GIT_BLOB_SHA1:
        raise ValueError("Archive hash differs from the original frozen delivery")
    return sha256.hexdigest()

def fetch_release_bundle(tag, destination):
    if not tag:
        raise ValueError("A published release tag is required")
    url = "https://api.github.com/repos/" + REPO + "/releases/tags/" + urllib.parse.quote(tag, safe="")
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "cpi-btc-study-importer",
    })
    with urllib.request.urlopen(request, timeout=60) as response:
        release = json.load(response)
    assets = [
        asset for asset in release.get("assets", [])
        if asset.get("size") == EXPECTED_BYTES
        and asset.get("name", "").lower().endswith(".zip")
        and asset.get("state") == "uploaded"
    ]
    if len(assets) != 1:
        raise ValueError("Attach exactly one original 41,961,194-byte ZIP before publishing the release")
    source_url = assets[0]["browser_download_url"]
    if not source_url.startswith("https://github.com/" + REPO + "/releases/download/"):
        raise ValueError("The bundle must be a release asset of this repository")
    with urllib.request.urlopen(source_url, timeout=120) as response, destination.open("wb") as stream:
        written = 0
        for block in iter(lambda: response.read(1024 * 1024), b""):
            written += len(block)
            if written > EXPECTED_BYTES:
                raise ValueError("Downloaded archive exceeds the original size")
            stream.write(block)
    return release["tag_name"]

def import_bundle(bundle, root, release_tag=None):
    root = root.resolve()
    bundle_sha256 = verify_bundle(bundle)
    with zipfile.ZipFile(bundle) as archive:
        entries = archive.infolist()
        if sum(info.file_size for info in entries) > 512 * 1024 * 1024:
            raise ValueError("Unexpected expanded archive size")
        targets = [(info, safe_member(info, root)) for info in entries]
        bad = archive.testzip()
        if bad is not None:
            raise ValueError("Archive CRC check failed: " + bad)
        for info, target in targets:
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
    project = root / "cpi_upgrade"
    delivery = root / "deliverables"
    delivery.mkdir(exist_ok=True)
    for name in DELIVERY_NAMES:
        source = project / "deliverables" / name
        if not source.is_file():
            raise ValueError("Missing archived deliverable: " + name)
        shutil.copyfile(source, delivery / name)
    if bundle.resolve() != (delivery / BUNDLE_NAME).resolve():
        shutil.copyfile(bundle, delivery / BUNDLE_NAME)
    shutil.copytree(project / "figures", root / "figures", dirs_exist_ok=True)

    with (delivery / "CPI_4指标完整事件数据库.csv").open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        events = list(reader)
    if len(events) != 92 or len({event["date"] for event in events}) != 92:
        raise ValueError("Event CSV must contain exactly 92 unique CPI dates")
    if min(event["date"] for event in events) != "2019-01-11" or max(event["date"] for event in events) != "2026-09-11":
        raise ValueError("Event date bounds differ from the frozen study")
    for prefix in ["headline_mom", "core_mom", "headline_yoy", "core_yoy"]:
        for suffix in ["actual", "forecast"]:
            if prefix + "_" + suffix not in fields:
                raise ValueError("Missing CPI indicator field: " + prefix + "_" + suffix)
    december = next(event for event in events if event["date"] == "2025-12-18")
    if december["headline_mom_actual"] or december["core_mom_actual"]:
        raise ValueError("Unavailable December 2025 monthly CPI must remain missing")
    with (delivery / "CPI_第一波与反杀策略回测.csv").open(encoding="utf-8-sig", newline="") as stream:
        trades = sum(1 for _ in csv.DictReader(stream))
    if trades != 5322:
        raise ValueError("Trade scenario count differs from the frozen study")
    with zipfile.ZipFile(delivery / "CPI_总体核心交叉矩阵.xlsx") as workbook:
        sheets = [name for name in workbook.namelist()
                  if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name)]
    if len(sheets) != 11:
        raise ValueError("Workbook must contain 11 worksheets")
    for name in ["trading.py", "test_upgrade.py", "paths_upgrade.py", "groups.py"]:
        if not (project / "src" / name).is_file():
            raise ValueError("Missing original source file: " + name)
    if not (project / "original").is_dir():
        raise ValueError("Original source/data project is missing")
    minute_zips = list((project / "original").rglob("BTCUSDT-1m-*.zip"))
    if len(minute_zips) != 184:
        raise ValueError("Expected 184 original Binance daily minute-data ZIPs")

    manifest = []
    for name in DELIVERY_NAMES + [BUNDLE_NAME]:
        path = delivery / name
        manifest.append({
            "path": "deliverables/" + name,
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    (root / "DELIVERABLES_SHA256.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    audit = {
        "import_status": "complete",
        "source_release_tag": release_tag,
        "archive_bytes": EXPECTED_BYTES,
        "archive_git_blob_sha1": EXPECTED_GIT_BLOB_SHA1,
        "archive_sha256": bundle_sha256,
        "archive_crc_verified": True,
        "deliverables": len(manifest),
        "event_rows": len(events),
        "trade_scenarios": trades,
        "workbook_sheets": len(sheets),
        "original_binance_daily_zips": len(minute_zips),
        "source_files": len(list((project / "src").glob("*"))),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "backtest_rerun_in_this_import": False,
        "note": "This verifies upload integrity and row counts; it does not independently rerun the 92-event backtest.",
    }
    (root / "UPLOAD_AUDIT.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    readme = root / "README.md"
    if readme.exists():
        text = readme.read_text(encoding="utf-8")
        text = re.sub(r"\*\*上传状态：[^\n]*\*\*\n\n", "", text, count=1)
        status = "**上传状态：10份交付文件及完整展开的源码、原始数据、测试包已导入。文件哈希与92行事件/5322条交易情景已核对；此次导入没有重新运行历史回测。详见 UPLOAD_AUDIT.json。**\n\n"
        if text.startswith("# ") and "\n\n" in text:
            heading, body = text.split("\n\n", 1)
            text = heading + "\n\n" + status + body
        readme.write_text(text, encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))

class ImportSafetyTests(unittest.TestCase):
    def test_regular_member(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertEqual(safe_member(zipfile.ZipInfo("cpi_upgrade/src/trading.py"), root),
                             root / "cpi_upgrade/src/trading.py")
    def test_unsafe_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ["/cpi_upgrade/file", "cpi_upgrade/../file",
                         "other/file", "cpi_upgrade/.git/config", "cpi_upgrade/a\\b"]:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    safe_member(zipfile.ZipInfo(name), Path(folder))
    def test_symlinks(self):
        info = zipfile.ZipInfo("cpi_upgrade/link")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(ValueError):
            safe_member(info, Path(folder))
    def test_reject_wrong_bundle(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "fake.zip"
            path.write_bytes(b"fake")
            with self.assertRaises(ValueError):
                verify_bundle(path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", nargs="?")
    parser.add_argument("--release-tag")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        unittest.main(argv=["import_safety"], exit=True)
        return
    root = Path(__file__).resolve().parents[1]
    if args.bundle:
        import_bundle(Path(args.bundle).resolve(), root)
    elif args.release_tag:
        with tempfile.TemporaryDirectory() as folder:
            bundle = Path(folder) / "delivery.zip"
            tag = fetch_release_bundle(args.release_tag, bundle)
            import_bundle(bundle, root, tag)
    else:
        parser.error("Supply a local archive or --release-tag")

if __name__ == "__main__":
    main()
