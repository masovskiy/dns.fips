#!/usr/bin/env python3
"""Publish a signed snapshot to a FIPS/1 node over raw TCP (no HTTPS)."""
from __future__ import annotations
import argparse, base64, json, os, socket, struct, zipfile
from pathlib import Path

MAX_FRAME = 1024 * 1024
CHUNK = 192 * 1024

def encode(obj):
    body = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(body) > MAX_FRAME:
        raise ValueError("FIPS/1 frame exceeds 1 MiB; release metadata is too large")
    return struct.pack("!I", len(body)) + body

def read_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        part = sock.recv(n-len(buf))
        if not part:
            raise ConnectionError("FIPS/1 node closed the connection")
        buf.extend(part)
    return bytes(buf)

def rpc(host, port, method, params):
    import uuid
    request_id = uuid.uuid4().hex
    frame = encode({"protocol":"FIPS/1", "id":request_id, "method":method, "params":params})
    with socket.create_connection((host, port), timeout=20) as sock:
        sock.settimeout(20)
        sock.sendall(frame)
        size = struct.unpack("!I", read_exact(sock,4))[0]
        if size < 1 or size > MAX_FRAME:
            raise ValueError("Invalid FIPS/1 response size")
        response = json.loads(read_exact(sock,size).decode("utf-8"))
    if response.get("id") != request_id or response.get("protocol") != "FIPS/1":
        raise ValueError("Mismatched FIPS/1 response")
    if response.get("error"):
        raise RuntimeError(response["error"])
    return response.get("result", {})

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--host", default=os.environ.get("FIPS_NODE_HOST"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("FIPS_NODE_PORT") or "8789"))
    args = parser.parse_args()
    if not args.host:
        parser.error("set --host or FIPS_NODE_HOST")
    with zipfile.ZipFile(args.snapshot) as archive:
        release = json.loads(archive.read("release.json"))
        if not release.get("key_id") or not release.get("signature"):
            raise SystemExit("Snapshot release is unsigned; set FIPS_SIGNING_PRIVATE_KEY_B64 in the build environment")
        start = rpc(args.host, args.port, "publish.begin", {"release": release})
        if start.get("already_current"):
            print("This release is already current on the FIPS node; nothing to upload.")
            return
        upload_id = start["upload_id"]
        missing = start.get("missing", [])
        print(f"FIPS node accepted signed metadata; {len(missing)} objects need uploading")
        for idx, digest in enumerate(missing, 1):
            path = f"objects/{digest}"
            payload = archive.read(path)
            for offset in range(0, max(1, len(payload)), CHUNK):
                chunk = payload[offset:offset+CHUNK]
                response = rpc(args.host, args.port, "publish.put", {
                    "upload_id": upload_id,
                    "sha256": digest,
                    "offset": offset,
                    "data_b64": base64.b64encode(chunk).decode("ascii"),
                })
            print(f"[{idx}/{len(missing)}] {digest[:12]}… ({len(payload)} bytes)")
        result = rpc(args.host, args.port, "publish.commit", {"upload_id": upload_id})
        print(json.dumps(result, indent=2))
        print("Published over FIPS/1 TCP; native FIPS-Net site delivery does not use HTTPS.")

if __name__ == "__main__":
    main()
