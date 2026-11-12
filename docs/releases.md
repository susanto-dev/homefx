# Packaging and future releases

Current command: `python3 tools/package.py`. Output is a local candidate ZIP plus
SHA-256 sidecar, not itself a published release. Version comes from addon.xml. Runtime files
are explicitly enumerated; adding a dependency/file requires updating the allowlist.
Fixed timestamps and ordering make repeated builds reproducible within the toolchain.

Before future publication: review the source revision, run checks, record the candidate
hash and TV acceptance, verify notices and scan coverage, then obtain publication
approval. Do not describe code merged or built as installed, tested on TV, or published.

Future repository work: separately version repository.homefx; generate addons.xml and
its change checksum from packaged manifests; host immutable versioned ZIPs over HTTPS;
make packages available before updating the index. Validate fresh install and upgrade.
The Kodi index checksum is a change detector, not an authenticity signature.

Retain known-good packages. Document manual recovery and local-data compatibility;
a downgrade is not assumed safe after data migrations. No index generator, Kodi automatic updater, or signing infrastructure exists yet.

## Public preview publishing

The Publish preview workflow tests and builds the candidate, then deploys only
`dist/site` to GitHub Pages on pushes to main or manual dispatch from main.
Merging/pushing main therefore publishes a preview after checks pass. The build
job has read-only repository access; only deployment receives Pages write and
OIDC permissions. Official Actions are commit-pinned. Artifacts expire after one
day. `python3 tools/build_site.py` reproduces the download directory locally.

Publication is authorized for the synthetic preview. It is not a TV acceptance
result. The page exposes the ZIP, checksum, original MIT notice and installation
steps, without accounts, analytics or external assets. GitHub Pages/standard
public-repository runners require no paid plan; account storage limits still apply.
No paid services, custom domain or larger runners are provisioned.

Version 0.2.0 adds inactive Trakt foundations. Existing demo data and widget routes
are unchanged; there is no credential migration or automatic account connection.
The Validation workflow performs tests/package checks on PRs and main pushes without
publication. On merge, Security scans and the existing managed CodeQL checks also
run, and Publish preview builds/deploys the 0.2.0 download. Runner images and package
registries remain external mutable inputs even though Action commits and dependency
versions are pinned. No automatic update PRs, account writes or new hosting are added.
