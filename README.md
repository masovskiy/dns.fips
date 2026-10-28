# FIPS DNS Registry

**The source registry and publishing workflow for FIPS-Net.**

FIPS DNS Registry is the authoring, review, and release repository for the public `.fips` namespace. It contains site source files, registry records, validation tools, and the workflow used to build signed releases for FIPS-Net nodes.

Contributors can propose new sites through pull requests. After changes are reviewed and merged into `main`, GitHub Actions validates the repository and builds a release. If publishing is configured, the workflow can also send that release to a designated FIPS/1 node.

> **Important:** A Git commit does not automatically make a site available on FIPS-Net. A reachable FIPS node, a trusted signing key, and a correctly configured publishing workflow are required for live deployment.

## Contents

- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Adding a site](#adding-a-site)
- [Local validation](#local-validation)
- [Infrastructure setup](#infrastructure-setup)
- [GitHub Actions publishing](#github-actions-publishing)
- [Release format](#release-format)
- [Trust and security](#trust-and-security)
- [Current limitations](#current-limitations)
- [Contributing](#contributing)

## Architecture

FIPS DNS Registry separates site development from site delivery.

```text
Contributor
    |
    v
GitHub pull request
    |
    v
Review and merge into main
    |
    v
GitHub Actions
    |
    +--> Validate registry and site files
    |
    +--> Build signed release
    |
    +--> Optional: publish over FIPS/1 TCP
                    |
                    v
                FIPS node
                    |
                    v
             FIPS-Net clients
```

### GitHub is not the runtime web server

GitHub stores the source repository and provides the review and automation workflow. It is not the runtime server for native `.fips` websites.

Once a release has been accepted by a FIPS node, clients can retrieve its site files through the FIPS/1 protocol.

The intended native-site delivery path uses FIPS/1 over TCP rather than HTTPS. Git operations and GitHub Actions still use GitHub's own infrastructure and transport security; these are separate from site delivery.

A site is available to clients only when the required node, registry, release, and trust configuration are in place.

## Repository layout

```text
dns.fips/
├── README.md
├── registry.json
├── sites/
│   ├── first.fips/
│   │   ├── index.html
│   │   └── style.css
│   └── hello.fips/
│       ├── index.html
│       └── style.css
├── schemas/
│   └── registry.schema.json
├── spec/
│   └── FIPS1.md
├── tools/
│   ├── validate_registry.py
│   ├── build_snapshot.py
│   └── publish_snapshot.py
└── .github/
    └── workflows/
        └── validate-publish.yml
```

The exact files included may change as the implementation evolves. Refer to the current repository for the authoritative layout.

| Path | Purpose |
|---|---|
| `registry.json` | Site names and their registry records |
| `sites/` | Native static website source files |
| `sites/first.fips/` | Reserved FIPS-Net home page |
| `schemas/` | Registry validation schema |
| `spec/FIPS1.md` | FIPS/1 protocol documentation |
| `tools/validate_registry.py` | Registry and file validation |
| `tools/build_snapshot.py` | Release and manifest generation |
| `tools/publish_snapshot.py` | Release publication to a configured node |
| `.github/workflows/` | Automated validation and publishing |

## Adding a site

### 1. Create the site directory

For example, create:

```text
sites/my-site.fips/
├── index.html
├── style.css
└── images/
    └── logo.svg
```

Use relative paths for local assets:

```html
<link rel="stylesheet" href="./style.css">
<img src="./images/logo.svg" alt="Site logo">
```

Native `.fips` sites are intended for static content. Python, Node.js, PHP, and other server-side programs do not execute merely because their files are included in a site directory.

Do not include private keys, passwords, API tokens, private user data, or other secrets in published files.

### 2. Add a registry record

Add the site to the `entries` object in `registry.json`, following the existing schema and formatting:

```json
{
  "entries": {
    "my-site.fips": {
      "type": "site",
      "path": "sites/my-site.fips",
      "owner": "your-github-name",
      "description": "A short description of the site"
    }
  }
}
```

This is an illustrative record. Preserve any other existing entries and follow the actual schema in `schemas/registry.schema.json`.

The registry's validation rules determine which names and paths are accepted. Do not assume that every syntactically valid name is automatically authorized for publication.

### 3. Validate the repository

From the repository root, run:

```bash
python3 tools/validate_registry.py
```

Resolve validation errors before submitting a pull request.

If the validator requires additional dependencies or command-line arguments, follow the instructions provided by the current implementation.

### 4. Open a pull request

Create a branch, commit the site files and registry changes, and open a pull request against `main`.

Include a short description of the site and any relevant changes to its assets or registry metadata.

The repository maintainers review the changes before merging.

### 5. Publish the release

After a change is merged, the configured workflow validates the repository and builds a release.

- If publishing is not configured, the workflow can produce a build artifact without deploying it.
- If publishing is configured correctly, the workflow can send the release to the designated FIPS node.
- A successful build alone does not prove that a remote node accepted the release or that clients can retrieve the site.

Check the workflow result and the node's deployment status before announcing a site as live.

## External redirects

A registry may support redirect records for links to external websites. For example:

```json
{
  "type": "redirect",
  "target": "https://example.com/"
}
```

Use this format only if it is supported by the current registry schema.

An external redirect leaves the native FIPS-Net content path. The destination website is operated under its own infrastructure and security policies; it is not hosted as a native `.fips` site.

## Infrastructure setup

Live deployment requires a FIPS/1 node that is reachable by the relevant clients and publishing workflow.

Before exposing a node publicly:

1. Install a compatible FIPS release.
2. Configure its profile and network settings.
3. Establish the publisher trust configuration required by the implemented protocol.
4. Configure the publishing client or workflow.
5. Allow only the necessary network traffic.
6. Run the service under a dedicated, unprivileged account and a process supervisor.
7. Verify that the node accepts valid releases and rejects invalid ones.

The example below illustrates the expected shape of a node startup command:

```bash
fips node serve --host 0.0.0.0 --port 8789
```

Use this command only if it is supported by the version you have installed. Binding to `0.0.0.0` exposes the service on all network interfaces; firewall rules should restrict access to the intended service and publishing clients where practical.

Do not expose the node's configuration directory or private signing keys through the network.

### Publisher keys

The publisher's private key signs releases. The corresponding public key is used to verify signatures and establish trust.

Keep the private key in a secure location or an appropriately protected CI secret. Never commit it to this repository.

Distribute the public key through a trusted channel. Do not trust a key merely because it was downloaded from the same unauthenticated connection whose contents it is supposed to authenticate.

**Trust configuration is implementation-dependent.** Verify the behavior of the installed FIPS version before assuming that adding a key authorizes a node to accept releases, configures client verification, or performs both functions.

## GitHub Actions publishing

Automatic publishing is optional. It is intended for repository maintainers who operate or administer a reachable FIPS/1 publishing node.

Regular contributors do not need to configure repository secrets.

Without the required signing configuration and a reachable publishing node, the workflow should validate and build the release without deploying it.

### Repository configuration

In GitHub, open:

**Settings → Secrets and variables → Actions**

Configure the following values only if the repository's current workflow expects them.

| Name | Type | Purpose |
|---|---|---|
| `FIPS_SIGNING_PRIVATE_KEY_B64` | Secret | Private signing key material in the format expected by the publisher |
| `FIPS_SIGNING_KEY_ID` | Variable | Identifier of the signing key |
| `FIPS_NODE_HOST` | Variable | Reachable hostname or IP address of the publishing node |
| `FIPS_NODE_PORT` | Variable | Publishing node's TCP port, for example `8789` |

The variable names above are configuration conventions, not automatic GitHub features. They must match the names actually referenced in `.github/workflows/validate-publish.yml`.

Before configuring the workflow, verify:

- The key encoding and length expected by `build_snapshot.py`.
- The key identifier format expected by the release verifier.
- The authentication and authorization requirements of the node.
- The node address and port used by `publish_snapshot.py`.
- The exact events and branches allowed to trigger deployment.

Do not assume that a key generated by `fips keygen` can be inserted directly into the secret without checking its file format. If the command writes a base64-encoded file, determine whether the publisher expects the encoded text or the decoded key bytes.

### Workflow security

Production publishing should run only in a trusted context, such as after a reviewed change is merged into a protected `main` branch.

Do not expose signing secrets to untrusted pull-request code. Restrict workflow permissions to the minimum necessary, pin third-party actions appropriately, and review any scripts that run while signing credentials are available.

The workflow should fail closed if signature creation, release validation, or node publication fails.

## Release format

The reference implementation describes a signed `FIPS-RELEASE/1` manifest and content-addressed site objects.

A release may contain:

- A manifest describing sites and their files.
- Relative file paths, SHA-256 digests, sizes, and MIME types.
- An object map identifying content by hash.
- A signature produced by the publisher's Ed25519 private key.
- A snapshot archive for transfer or archival, if supported by the build tool.

The expected build outputs include:

```text
dist/
├── release.json
└── snapshot.zip
```

The archive may contain the manifest and objects stored under their content hashes. Refer to `spec/FIPS1.md` and the actual build tool for the authoritative format.

The intended verification sequence is:

1. Validate the release manifest.
2. Verify the signature against an explicitly trusted public key.
3. Verify each received object's hash and size.
4. Reject malformed or unauthorized releases.
5. Activate an accepted release without exposing a partially written deployment.
6. Have clients verify the manifest and the objects they retrieve.

These are security requirements for the implementation, not guarantees provided merely by this README. Test the release builder, node, and client together before relying on them.

## Trust and security

FIPS DNS Registry is an experimental network project. Treat all public site content and registry contributions as untrusted input until they have been validated and reviewed.

### No confidentiality on the native content path

The described FIPS/1 transport uses unencrypted TCP.

Ed25519 signatures can authenticate a release when the public key is trusted, and SHA-256 can detect changes to content whose expected digest is authenticated. These mechanisms do **not** encrypt traffic.

Observers may be able to read transmitted content and analyze connection metadata. Signatures also do not prevent denial-of-service attacks or make an untrusted publisher trustworthy.

Use native FIPS-Net sites for public static content only. Do not use the experimental transport for passwords, payment information, private sessions, or other sensitive data.

### Key management

- Keep private signing keys secret.
- Distribute public keys through an authenticated, trusted channel.
- Protect the workflow that can access signing secrets.
- Rotate compromised keys and update trust configuration when required.
- Do not accept an unknown key solely because a remote registry recommends it.

### Browser and site safety

Static HTML, CSS, JavaScript, and images can still contain malicious content. Validate and review contributions, use browser security controls, and avoid granting native FIPS pages access to sensitive application data.

The browser integration and URL handling must also be tested independently; registering or configuring a custom scheme does not guarantee support in every browser.

## Current limitations

FIPS-Net is an experimental reference implementation, not a hardened production network.

Current design limitations include:

- FIPS/1 content delivery does not provide transport encryption.
- A selected node's acceptance of a release determines whether that release is live there.
- Decentralized consensus and a distributed authority system are not provided by the registry repository alone.
- Replication, high availability, key revocation, namespace dispute resolution, and governance require additional infrastructure and protocol design.
- A local offline copy of `first.fips`, if included in the client, does not prove that the client is connected to a live public network.
- Browser integration, DNS resolution, node availability, and publication must be tested as separate components.

Do not describe a site as publicly available until the deployment has been verified from a client outside the publishing environment.

## Contributing

Contributions to the registry and site collection are welcome through pull requests, subject to the repository's review policy.

Before submitting:

1. Validate the registry.
2. Check all asset paths.
3. Remove private or sensitive information.
4. Confirm that the site follows the repository's content and security rules.
5. Describe any changes to registry records in the pull request.

By contributing a site, you acknowledge that its published content may be publicly accessible and transferred without encryption through the experimental FIPS/1 transport.

---

**FIPS DNS Registry is the source and review layer for FIPS-Net.** GitHub manages the source workflow; trusted signing keys authenticate releases; and configured FIPS nodes deliver accepted content to clients.
