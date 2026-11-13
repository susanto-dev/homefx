# Packaging and preview releases

This change prepares `plugin.video.homefx` 0.10.0 alongside
`repository.homefx` 0.2.0. The owner authorized repository-first publication on the
existing GitHub Pages site. Protected main remains PR-only; the maintainer merges.
A merge publishes only after workflow checks pass. This does not establish TV
acceptance or enable live accounts, sources or playback. No skin is redistributed.

## Build and verify

`python tools/package.py` creates a local video ZIP and SHA-256 sidecar. Runtime
files are allowlisted; version comes from addon.xml. Fixed timestamps and ordering
support repeatability in the same toolchain. Inspect the source revision, notices,
scan coverage and package hashes before merging. Preserve explicit pending device
gates rather than describing a cloud build as a successful Kodi installation.

`python tools/repository.py --retain-manifest releases/inventory.json` builds a local
candidate under `dist/repository`, including both current packages, addons.xml,
SHA-256 markers and retained archives. Its CANDIDATE.txt distinguishes this review
artifact from the public preview. Verify it with
`python tools/verify_repository.py dist/repository`.

`python tools/build_site.py` stages a complete site, including the verified preview
repository at `repository/`, its CHANNEL.txt notice, and root bootstrap/video ZIPs
with sidecars. The root ZIPs must exactly match the indexed packages. It uses
`releases/inventory.json` by default when present. Verify the embedded tree with
`python tools/verify_repository.py dist/site/repository --channel preview`.
Builders accept fresh or byte-identical destinations and refuse differing output;
use a fresh directory for changed source. Failed staging does not replace the site.

Kodi's repository manifest uses SHA-256 index and ZIP verification, checked against
the [official repository guide](https://kodi.wiki/view/Add-on_repositories) and
[Kodi 21.2 implementation](https://github.com/xbmc/xbmc/blob/21.2-Omega/xbmc/addons/Repository.cpp).
These checks detect corruption, not authenticity if hosting is compromised. HTTPS,
reviewed source and restricted deployment permissions remain trust boundaries; no
package-signing infrastructure or upstream code reuse is claimed.

## Immutable release history

`releases/inventory.json` is the reviewed local history. Each record contains exactly
`id`, `version`, relative `path` and `sha256`, within a schema-1 object with `packages`.
Both current package versions must be present and byte-identical to fresh builds.
Run `python tools/release_history.py releases/inventory.json --base-ref BASE_SHA`
against the reviewed base revision. CI compares prior records so removing or changing
an existing identity, path or hash fails. An initial base without an inventory has no
prior records to compare. No build downloads or executes retained archive code.

Retain every recorded version at its immutable path. Only current versions enter
addons.xml; older packages do not become update targets. Publish the complete staged
site, never an index assembled separately from its packages. Conflicting bytes at an
existing version require a new version, not replacement. History checks establish
consistency, not independent source approval or provenance.

Bounds fail closed: 64 KiB inventory, at most 32 total current/retained packages and
64 MiB aggregate retained ZIP input, plus per-package/content limits. Reaching a bound
requires a reviewed policy/tooling change; do not silently prune history. The generated
release-inventory.json describes the complete tree. Keeping a ZIP is not automatic
rollback: an explicit Kodi downgrade still needs saved-widget/profile compatibility
checks, especially after migrations.

## Publication and HTTP verification

Publish preview builds and deploys `dist/site` on main pushes or manual dispatch from
main. PR events validate without deploying. Build access is read-only; deployment
alone receives Pages write and OIDC permissions. External Actions use reviewed full
commit SHAs, and Python tooling installs use pinned artifact hashes. Runner images
and package registries remain external inputs. Weekly discovery produces reports for
manual triage, not automatic update PRs or discussion comments. GitHub-managed
security checks may independently annotate PR findings; these workflows do not post
comments. The deployment guard rejects a run that no longer matches current main.
Do not rerun historical deployment workflows predating that guard.

The postdeployment check uses the exact downloaded Pages build artifact, not a fresh
rebuild. `tools/unpack_site.py` rejects unsafe archive members, bounds reads and
validates the complete site before making a new staging directory available. It never
executes archived files or uses unrestricted extraction. Then
`python tools/check_published.py PATH_TO_EXTRACTED_SITE` verifies
local topology, repository and root-package equivalence, then compares every expected
file byte-for-byte over HTTPS at `https://susanto-dev.github.io/homefx/`. Redirects,
HTTP failures and mismatches fail the check. It does not enumerate unexpected remote
files. Propagation failures need investigation and an explicit rerun; a successful
check proves HTTP integrity only, never Kodi installation, updates or playback.

The page exposes repository-first instructions, manual video download, SHA-256
sidecars and the existing MIT notice. It uses no accounts, analytics or external
assets. Public GitHub Pages and standard public-repository runners require no paid
plan; account quotas still apply. No custom domain, paid service or larger runner is
provisioned. Development tooling is separate from the standard-library-only add-on.

## Repeatability and acceptance

`python tools/check_reproducibility.py` creates two isolated complete site/candidate
builds using the reviewed inventory. It verifies both repository channel types,
compares all paths and bytes, and confirms root bootstrap/video archives and sidecars
match the repository packages. Validation runs under Python 3.8 and 3.12 independently;
it does not establish cross-toolchain byte identity, signatures or provenance.

The official Kodi add-on checker remains an explicit coverage gap; project manifest,
XML and archive validators do not substitute for it. Fresh repository installation,
video installation, upgrade, offline behavior, checksum rejection and rollback remain
pending on the actual device; follow [TV testing](testing-on-tv.md). Account activation,
playback, subtitles, resume and scrobbling require separate evidence and are not enabled
by publishing this synthetic channel.


## Observed repository publication

Video 0.9.0 and repository 0.2.0 were deployed from merge commit
`5a53a26ffec91178d491c5f27b1b354459755ae5`.
[Publish preview run 43336830315](https://github.com/susanto-dev/homefx/actions/runs/43336830315)
passed build, deployment, safe artifact staging and public-byte verification.
Validation and security runs also passed at that merge. This is not evidence of
Kodi installation, updates or playback. Version 0.10.0 remains pending its own merge
and publication; previously indexed archives remain immutable.
