#!/usr/bin/env python3
"""A one-run encrypted Library-to-GitHub transfer. No download URLs are logged."""
import base64
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import import_study_bundle as importer

REPO = importer.REPO
ROOT = Path(__file__).resolve().parents[1]
RUN_ID = os.environ["GITHUB_RUN_ID"]
TOKEN = os.environ["GH_TOKEN"]

def api_get(path):
    request = urllib.request.Request(
        "https://api.github.com/repos/" + REPO + path,
        headers={"Accept": "application/vnd.github+json",
                 "Authorization": "Bearer " + TOKEN,
                 "User-Agent": "cpi-study-one-run-transfer"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise RuntimeError("GitHub transfer metadata request failed: " + str(error.code)) from None

def read_request(name):
    response = api_get("/contents/.transfer/" + name + "?ref=main")
    if response is None:
        return None
    return json.loads(base64.b64decode(response["content"]))

def git_commit(paths, message):
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], cwd=ROOT, check=True)
    subprocess.run(["git", "config", "user.email",
                    "41898282+github-actions[bot]@users.noreply.github.com"], cwd=ROOT, check=True)
    subprocess.run(["git", "add", "--", *paths], cwd=ROOT, check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode == 0:
        return
    subprocess.run(["git", "commit", "-m", message], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=ROOT, check=True)

def decrypt_request(envelope, private_key):
    if envelope.get("run_id") != RUN_ID or envelope.get("algorithm") != "RSA-OAEP-SHA256":
        raise ValueError("Wrong transfer run or encryption algorithm")
    if len(envelope.get("blocks", [])) > 4096:
        raise ValueError("Encrypted request is too large")
    pieces = []
    for encoded in envelope["blocks"]:
        block = base64.b64decode(encoded, validate=True)
        if len(block) != 256:
            raise ValueError("Invalid RSA block size")
        result = subprocess.run(
            ["openssl", "pkeyutl", "-decrypt", "-inkey", str(private_key),
             "-pkeyopt", "rsa_padding_mode:oaep", "-pkeyopt", "rsa_oaep_md:sha256",
             "-pkeyopt", "rsa_mgf1_md:sha256"],
            input=block, capture_output=True)
        if result.returncode:
            raise RuntimeError("Encrypted request validation failed")
        pieces.append(result.stdout)
    data = b"".join(pieces)
    if hashlib.sha256(data).hexdigest() != envelope.get("sha256"):
        raise ValueError("Transfer plaintext checksum mismatch")
    return data

def transfer_and_import(payload, private_folder):
    if payload.get("kind") != "library-transfer":
        raise ValueError("Unexpected transfer request kind")
    helper_text = payload["transfer_helper"]
    if hashlib.sha256(helper_text.encode("utf-8")).hexdigest() != payload["helper_sha256"]:
        raise ValueError("Library helper checksum mismatch")
    helper = private_folder / "library_file_transfer.py"
    helper.write_text(helper_text, encoding="utf-8")
    incoming = private_folder / "incoming"
    incoming.mkdir()
    expected = set(importer.DELIVERY_NAMES + [importer.BUNDLE_NAME])
    transfers = payload["transfers"]
    if len(transfers) != 10 or {transfer["file_name"] for transfer in transfers} != expected:
        raise ValueError("Expected exactly the ten requested delivery files")
    clean_environment = {key: value for key, value in os.environ.items()
                         if key not in {"GH_TOKEN", "GITHUB_TOKEN"}}
    for transfer in transfers:
        if transfer.get("workspace_path") or not transfer.get("download_url"):
            raise ValueError("Expected a resolved signed file transfer")
        destination = incoming / transfer["file_name"]
        result = subprocess.run(
            [sys.executable, str(helper), "materialize", str(destination)],
            input=json.dumps(transfer), capture_output=True, text=True,
            env=clean_environment)
        if result.returncode:
            raise RuntimeError("Library materialization failed for " + transfer["file_name"])
        if destination.stat().st_size != transfer["size_bytes"]:
            raise ValueError("Download byte count differs for " + transfer["file_name"])
        print("Downloaded and checked: " + transfer["file_name"], flush=True)
    importer.import_bundle(incoming / importer.BUNDLE_NAME, ROOT)

    # Preserve the exact current individual deliveries, including Library PDF exports.
    delivery = ROOT / "deliverables"
    import shutil
    for name in importer.DELIVERY_NAMES + [importer.BUNDLE_NAME]:
        shutil.copyfile(incoming / name, delivery / name)
    manifest = [{
        "path": "deliverables/" + name,
        "bytes": (delivery / name).stat().st_size,
        "sha256": hashlib.sha256((delivery / name).read_bytes()).hexdigest()
    } for name in importer.DELIVERY_NAMES + [importer.BUNDLE_NAME]]
    (ROOT / "DELIVERABLES_SHA256.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (delivery / "CPI_4指标完整事件数据库.csv").open(encoding="utf-8-sig", newline="") as stream:
        events = list(csv.DictReader(stream))
    with (delivery / "CPI_第一波与反杀策略回测.csv").open(encoding="utf-8-sig", newline="") as stream:
        trades = sum(1 for _ in csv.DictReader(stream))
    if len(events) != 92 or trades != 5322:
        raise ValueError("Individual delivery row counts do not match the verified archive")
    audit_path = ROOT / "UPLOAD_AUDIT.json"
    audit = json.loads(audit_path.read_text())
    audit.update({
        "transfer_method": "one-run RSA-OAEP encrypted Library materialization",
        "individual_deliveries_checked": 10,
        "current_individual_exports_preserved": True,
        "download_urls_published": False,
        "event_fields": len(events[0]),
        "backtest_rerun_in_this_import": False,
    })
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name in ["public-key.json", "probe.json", "probe-ok.json", "request.json"]:
        path = ROOT / ".transfer" / name
        if path.exists():
            path.unlink()
    git_commit(["deliverables", "cpi_upgrade", "figures", "README.md",
                "DELIVERABLES_SHA256.json", "UPLOAD_AUDIT.json", ".transfer"],
               "Upload all CPI delivery files, full source, raw data and tests")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write("### Completed CPI file import\n\n")
            stream.write(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print("Completed: ten deliveries, 92 events, 5322 trade scenarios, full source/data/tests.", flush=True)

def main():
    with tempfile.TemporaryDirectory(prefix="cpi-private-transfer-", dir=os.environ.get("RUNNER_TEMP")) as folder:
        private_folder = Path(folder)
        private_key = private_folder / "key.pem"
        public_key = private_folder / "public.pem"
        subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt",
                        "rsa_keygen_bits:2048", "-pkeyopt", "rsa_keygen_pubexp:65537",
                        "-out", str(private_key)], check=True, capture_output=True)
        private_key.chmod(0o600)
        subprocess.run(["openssl", "pkey", "-in", str(private_key), "-pubout",
                        "-out", str(public_key)], check=True, capture_output=True)
        modulus = subprocess.check_output(
            ["openssl", "rsa", "-pubin", "-in", str(public_key), "-noout", "-modulus"],
            text=True).strip().split("=", 1)[1]
        transfer_dir = ROOT / ".transfer"
        transfer_dir.mkdir(exist_ok=True)
        (transfer_dir / "public-key.json").write_text(json.dumps({
            "run_id": RUN_ID, "algorithm": "RSA-OAEP-SHA256", "exponent": 65537,
            "modulus_hex": modulus,
        }, indent=2) + "\n")
        git_commit([".transfer/public-key.json"], "Publish one-run CPI file transfer public key")
        deadline = time.monotonic() + 25 * 60
        probe_done = False
        print("One-run transfer is ready.", flush=True)
        while time.monotonic() < deadline:
            if not probe_done:
                probe = read_request("probe.json")
                if probe and probe.get("run_id") == RUN_ID:
                    message = decrypt_request(probe, private_key)
                    if message != b"cpi-transfer-probe/v1":
                        raise ValueError("Encryption compatibility probe mismatch")
                    # Sync the probe commit before recording acknowledgement.
                    subprocess.run(["git", "pull", "--ff-only", "origin", "main"], cwd=ROOT, check=True)
                    (transfer_dir / "probe-ok.json").write_text(json.dumps({
                        "run_id": RUN_ID, "rsa_oaep_sha256_probe": "passed",
                    }) + "\n")
                    git_commit([".transfer/probe-ok.json"], "Verify encrypted CPI transfer compatibility")
                    probe_done = True
            request = read_request("request.json")
            if request and request.get("run_id") == RUN_ID:
                if not probe_done:
                    raise ValueError("Compatibility probe must pass before file transfer")
                payload = json.loads(decrypt_request(request, private_key))
                subprocess.run(["git", "pull", "--ff-only", "origin", "main"], cwd=ROOT, check=True)
                transfer_and_import(payload, private_folder)
                return
            time.sleep(5)
        raise RuntimeError("One-run transfer timed out without an encrypted file request")

if __name__ == "__main__":
    main()
