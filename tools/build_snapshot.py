#!/usr/bin/env python3
"""Build FIPS-RELEASE/1 content objects and optionally sign the release."""
from __future__ import annotations
import base64, hashlib, json, mimetypes, os, shutil, time, zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
MAX_FILE = 5 * 1024 * 1024

def canonical_json(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def mime(path: str) -> str:
    kind, _ = mimetypes.guess_type(path)
    if not kind:
        kind = "application/octet-stream"
    if kind.startswith("text/") or kind in {"application/javascript", "application/json", "application/xml"}:
        return kind + "; charset=utf-8"
    return kind

def sign_manifest(manifest):
    encoded = os.environ.get("FIPS_SIGNING_PRIVATE_KEY_B64", "").strip()
    if not encoded:
        return None, None
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) != 32:
            raise ValueError("private key must be base64-encoded 32-byte Ed25519 raw key")
        private = Ed25519PrivateKey.from_private_bytes(raw)
        public_raw = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        key_id = hashlib.sha256(public_raw).hexdigest()[:16]
        requested_id = os.environ.get("FIPS_SIGNING_KEY_ID", "").strip()
        if requested_id and requested_id != key_id:
            raise ValueError(f"FIPS_SIGNING_KEY_ID does not match key; expected {key_id}")
        signature = base64.b64encode(private.sign(canonical_json(manifest))).decode("ascii")
        return key_id, signature
    except Exception as exc:
        raise SystemExit(f"Could not sign release: {exc}")

def main():
    registry = json.loads((ROOT / "registry.json").read_text(encoding="utf-8"))
    out_entries, objects = {}, {}
    for name, record in sorted(registry["entries"].items()):
        base = {"type": record["type"], "owner": record.get("owner", "community"), "description": record.get("description", "")}
        if record["type"] == "redirect":
            base["target"] = record["target"]
        else:
            site_root = (ROOT / record["path"]).resolve()
            site_root.relative_to((ROOT / "sites").resolve())
            files = {}
            for source in sorted(site_root.rglob("*")):
                if source.is_symlink():
                    raise SystemExit(f"Symlinks are forbidden: {source}")
                if not source.is_file():
                    continue
                rel = PurePosixPath(source.relative_to(site_root).as_posix()).as_posix()
                if PurePosixPath(rel).is_absolute() or ".." in PurePosixPath(rel).parts:
                    raise SystemExit(f"Unsafe site path: {rel}")
                payload = source.read_bytes()
                if len(payload) > MAX_FILE:
                    raise SystemExit(f"File exceeds 5 MiB: {source}")
                h = digest(payload)
                objects.setdefault(h, payload)
                files[rel] = {"sha256": h, "size": len(payload), "mime": mime(rel)}
            if "index.html" not in files:
                raise SystemExit(f"{name} is missing index.html")
            base["entrypoint"] = "index.html"
            base["files"] = files
        out_entries[name] = base
    if out_entries.get("first.fips", {}).get("type") != "site":
        raise SystemExit("first.fips must be a static site record")
    manifest = {
        "format": "FIPS-RELEASE/1",
        "release_id": os.environ.get("GITHUB_SHA", f"local-{int(time.time())}"),
        "created_at": time.time_ns(),
        "registry": {"schema_version": 1, "registry_name": registry.get("registry_name", "FIPS-Net Public Registry"), "entries": out_entries},
        "objects": {h: len(data) for h, data in sorted(objects.items())},
    }
    manifest_bytes = canonical_json(manifest)
    if len(manifest_bytes) > 800 * 1024:
        raise SystemExit("Manifest exceeds 800 KiB FIPS/1 metadata limit; split the registry into smaller releases")
    if sum(len(payload) for payload in objects.values()) > 250 * 1024 * 1024:
        raise SystemExit("Unique release objects exceed 250 MiB")
    key_id, signature = sign_manifest(manifest)
    release = {"manifest": manifest, "key_id": key_id, "signature": signature}
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "objects").mkdir(parents=True)
    (DIST / "release.json").write_text(json.dumps(release, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for h, payload in objects.items():
        (DIST / "objects" / h).write_bytes(payload)
    with zipfile.ZipFile(DIST / "snapshot.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(DIST / "release.json", "release.json")
        for h in sorted(objects):
            archive.write(DIST / "objects" / h, f"objects/{h}")
    snap = (DIST / "snapshot.zip").read_bytes()
    (DIST / "snapshot.sha256").write_text(f"{digest(snap)}  snapshot.zip\n", encoding="ascii")
    if signature:
        print(f"Signed release {manifest['release_id']} with key {key_id}: {len(out_entries)} names, {len(objects)} objects")
    else:
        print(f"Built unsigned validation snapshot: {len(out_entries)} names, {len(objects)} objects (not publishable until signed)")

if __name__ == "__main__":
    main()
