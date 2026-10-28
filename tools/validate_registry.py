#!/usr/bin/env python3
"""Validate registry.json and static sites before a FIPS-Net release is built."""
from __future__ import annotations
import json, re, sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+fips$")
MAX_FILE = 5 * 1024 * 1024
MAX_SITE = 25 * 1024 * 1024
RESERVED = {"first.fips"}

def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)

def main() -> None:
    try:
        doc = json.loads((ROOT / "registry.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot parse registry.json: {exc}")
    if not isinstance(doc, dict) or doc.get("schema_version") != 1:
        fail("registry.json must have schema_version: 1")
    entries = doc.get("entries")
    if not isinstance(entries, dict) or not 1 <= len(entries) <= 10000:
        fail("entries must be an object containing between 1 and 10,000 records")
    if entries.get("first.fips", {}).get("type") != "site":
        fail("first.fips is reserved and must be a site record")
    count = 0
    for name, record in sorted(entries.items()):
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            fail(f"invalid .fips name: {name!r}")
        if name in RESERVED and name != "first.fips":
            fail(f"reserved name: {name}")
        if not isinstance(record, dict):
            fail(f"{name}: record must be an object")
        owner = record.get("owner", "community")
        description = record.get("description", "")
        if not isinstance(owner, str) or not owner or len(owner) > 120:
            fail(f"{name}: owner must be a non-empty string up to 120 characters")
        if not isinstance(description, str) or len(description) > 500:
            fail(f"{name}: description must be a string up to 500 characters")
        kind = record.get("type")
        if kind == "redirect":
            target = record.get("target")
            parsed = urlsplit(target) if isinstance(target, str) else None
            if not parsed or parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                fail(f"{name}: redirect target must be an absolute http(s) URL without credentials")
            continue
        if kind != "site":
            fail(f"{name}: type must be 'site' or 'redirect'")
        rel = record.get("path")
        if not isinstance(rel, str) or not rel.startswith("sites/") or ".." in Path(rel).parts:
            fail(f"{name}: site path must be safely rooted under sites/")
        site_root = (ROOT / rel).resolve()
        try:
            site_root.relative_to((ROOT / "sites").resolve())
        except ValueError:
            fail(f"{name}: site path escapes sites/")
        if not site_root.is_dir() or not (site_root / "index.html").is_file():
            fail(f"{name}: directory must contain index.html")
        total = 0
        for item in site_root.rglob("*"):
            if item.is_symlink():
                fail(f"{name}: symlinks are not allowed ({item})")
            if item.is_file():
                size = item.stat().st_size
                count += 1
                total += size
                if size > MAX_FILE:
                    fail(f"{name}: file exceeds 5 MiB ({item.relative_to(ROOT)})")
        if total > MAX_SITE:
            fail(f"{name}: total site size exceeds 25 MiB")
    print(f"OK: {len(entries)} names and {count} site files validated; first.fips is present.")

if __name__ == "__main__":
    main()
