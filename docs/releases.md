# Packaging and future releases

Current command: `python3 tools/package.py`. Output is a local candidate ZIP plus
SHA-256 sidecar, not itself a published release. Version comes from addon.xml. Runtime files
are explicitly enumerated; adding a dependency/file requires updating the allowlist.
Fixed timestamps and ordering make repeated builds reproducible within the toolchain.

Before future publication: review the source revision, run checks, record the candidate
hash and TV acceptance, verify notices and scan coverage, then obtain publication
approval. Do not describe code merged or built as installed, tested on TV, or published.

## Local repository candidate

`python3 tools/repository.py` builds both reviewed add-on packages, reads their
packaged manifests and generates `dist/repository/addons.xml` with a SHA-256 change
marker. Versioned ZIPs and SHA-256 sidecars live beneath each add-on ID. The repository
add-on points to the reserved HTTPS path `https://susanto-dev.github.io/homefx/repository/`.
**That path is not published by this batch.** The candidate includes CANDIDATE.txt and
is useful for inspection; installing its repository ZIP now does not create a working
update channel. Validation retains it as a seven-day review artifact, not a release.

The manifest uses Kodi 21's SHA-256 index verification and ZIP sidecar verification.
These detect corruption, not authenticity if the host itself is compromised. The
repository relies on HTTPS and review of what is published; no signing infrastructure
is claimed. Contracts were checked against the [official repository guide](https://kodi.wiki/view/Add-on_repositories)
and [Kodi 21.2 implementation](https://github.com/xbmc/xbmc/blob/21.2-Omega/xbmc/addons/Repository.cpp).
No upstream implementation or artwork is copied.

Before activation, choose retained-version/rollback policy and publish immutable
versioned packages before the index. Preserve known-good packages and check saved
widget/profile compatibility; a downgrade after a migration is not presumed safe.
Then validate fresh repository installation, video installation, upgrade, checksum
failure, offline behavior and rollback on the actual Kodi device. The generator's
success is not a device acceptance result. Repository activation remains separate
from authorization to publish the synthetic manual-download preview.

## Public preview publishing

The Publish preview workflow tests and builds the candidate, then deploys only
`dist/site` to GitHub Pages on pushes to main or manual dispatch from main.
Merging a PR into protected main therefore publishes a preview after checks pass. The build
job has read-only repository access; only deployment receives Pages write and
OIDC permissions. Official Actions are commit-pinned. Artifacts expire after one
day. `python3 tools/build_site.py` reproduces the download directory locally.

Publication is authorized for the synthetic preview. It is not a TV acceptance
result. The page exposes the ZIP, checksum, original MIT notice and installation
steps, without accounts, analytics or external assets. GitHub Pages/standard
public-repository runners require no paid plan; account storage limits still apply.
No paid services, custom domain or larger runners are provisioned.

Version 0.3.0 adds inactive transport/session/library foundations and setup guidance. Existing demo data and widget routes
are unchanged; there is no credential migration or automatic account connection.
The Validation workflow performs tests/package checks on PRs and main pushes without
publication. On merge, Security scans and the existing managed CodeQL checks also
run, and Publish preview builds/deploys the 0.3.0 video download only. Runner images and package
registries remain external mutable inputs even though Action commits and dependency
versions are pinned. No automatic update PRs, account writes or new hosting are added.
