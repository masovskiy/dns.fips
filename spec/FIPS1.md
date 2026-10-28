# FIPS/1 — reference transport

FIPS/1 is the native transport for `.fips` sites. It uses plain TCP, not HTTPS. This makes native content delivery independent of browser TLS certificates, web PKI, or HTTPS hosting. Since TCP is not encrypted, the current network is intended for public static content only.

## Frame

Every message is a 4-byte unsigned big-endian payload length followed by UTF-8 JSON. Maximum frame size is 1 MiB. One request and one response are exchanged per TCP connection. Binary objects are transferred as base64 chunks of up to 192 KiB inside JSON frames.

## Core methods

- `node.info`: node version and feature list.
- `registry.get`: retrieve the current signed release wrapper.
- `dns.resolve`: return one record from the active release.
- `object.get`: read a content-addressed object by SHA-256 hash and byte offset.
- `publish.begin`: submit a signed release manifest; node verifies Ed25519 publisher key.
- `publish.put`: upload chunks for objects referenced by the verified manifest.
- `publish.commit`: verify every object's size/hash, store objects, then atomically activate the release.

## Signed release

A release wrapper has `{ "manifest": ..., "key_id": "...", "signature": "base64-ed25519" }`. The signature covers canonical JSON: UTF-8 JSON sorted by key, separators `(',', ':')`, no ASCII escaping, and one final newline. The client must be configured with the public key for `key_id` before trusting the release.

The manifest format is `FIPS-RELEASE/1` and includes `registry.entries`, `objects` (SHA-256 → byte length), `release_id`, and `created_at`. Every native site record lists the relative file path, digest, size, and MIME type. The client validates the signed manifest, fetches each object over FIPS/1, and checks the digest before serving it locally through the browser gateway.

## Security model

Ed25519 authenticates the manifest, SHA-256 authenticates object bytes against signed metadata, and local browser gateway binds only to loopback. The protocol does not encrypt data and does not hide names, request timing, peer IPs, or content. The publisher key is the root of trust; never commit its private half. Production versions still need robust peer discovery, anti-replay/rollback rules, rate limits, monitoring, and a tested update/revocation procedure.
