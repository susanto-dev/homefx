# Packaging and preview releases

This journey integration repair prepares `plugin.video.homefx` 0.16.1 alongside
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
Kodi installation, updates or playback. Video 0.10.0 later deployed from merge commit
`8ed762417e3573b29629896b35b0fcdcf694244b`;
[publication run 43338722387](https://github.com/susanto-dev/homefx/actions/runs/43338722387)
also passed build, deployment and hosted-byte verification. The following 0.11.0 release was merged at
`96f2e307db4d5e9bffd0d8b7937d619816dd99e8`; its
[publication run 43341996914](https://github.com/susanto-dev/homefx/actions/runs/43341996914)
passed build, deployment and hosted-byte verification. Video 0.12.0 deployed from merge commit
`4fbc5b3a34bfb76c5aac3fce5646814b82f7a7b0`;
[publication run 43349117123](https://github.com/susanto-dev/homefx/actions/runs/43349117123)
passed build, deployment and hosted-byte verification. Video 0.13.0 deployed from merge commit
`66ad23d0b43ba2fa3be2a00a5036e0ffadc7a669`;
[publication run 43353289076](https://github.com/susanto-dev/homefx/actions/runs/43353289076)
passed build, deployment and hosted-byte verification. The following test-quality
batch changes no package bytes or versions. Previously indexed archives remain immutable.


## Local preparation

The [release-preparation helper](release-preparation.md) builds a complete verified
proposal without changing authoritative release inputs. It preserves current and
review-base records, stages only validated bytes and fails rather than replacing
a published version. A proposal is neither publication nor permission to merge.

The subsequent test-reporting batch published unchanged package bytes from
`50047325a8ee3ec02d705770bb83948f66609649`;
[publication run 43354769976](https://github.com/susanto-dev/homefx/actions/runs/43354769976)
passed build, deployment and hosted-byte verification. The dependency/manifest
validation batch also changes no package versions or retained archive bytes.

The dependency/manifest batch deployed unchanged video 0.13.0/repository 0.2.0
packages from `a7fb4fbe1639a32de4f56f3dbc57b77e552ca234`.
[Publication run 43356354268](https://github.com/susanto-dev/homefx/actions/runs/43356354268)
passed build, deployment and hosted-byte verification. The subsequent 0.14.0 merge
`e33edc02e72dbc52df058a7ac76bc0948baa2a5f` failed its Python 3.12 validation
[run](https://github.com/susanto-dev/homefx/actions/runs/43359581622) and preview
[build](https://github.com/susanto-dev/homefx/actions/runs/43359581727) in the same
concurrent preferences test. Deployment and hosted-byte verification were skipped.

Direct HTTPS inspection on 2026-11-13 found the index still advertising video
0.13.0/repository 0.2.0. The root 0.13.0 ZIP matches its retained SHA-256; root and
repository 0.14.0 ZIP URLs returned 404. This does not assert that every hosted file
was checked. Failure-report artifacts were listed but downloading them was blocked;
the complete failed-step logs and aggregate test counts were inspected instead.

The repair publishes video 0.14.1 as the current update target, with unchanged
repository 0.2.0. All eight records already merged into history remain byte-for-byte
unchanged, including the superseded 0.14.0 archive. The repository will retain that
archive at its versioned path, but will not advertise it as the current version.
No merged or published version is rebuilt with different bytes. Publication occurs only after
the maintainer merges and the ordinary preview workflow succeeds.

## Confirmed repair publication and follow-up

The 0.14.1 repair merged at `1ad8df1f50111cc0d8a2c155b3cae030f9bbb83a`.
[Validation 43363067295](https://github.com/susanto-dev/homefx/actions/runs/43363067295)
passed on Python 3.8 and 3.12.
[Publication 43363067248](https://github.com/susanto-dev/homefx/actions/runs/43363067248)
passed build, deployment and hosted-byte verification. Direct HTTPS checks also
confirmed the current 0.14.1 index and matching root/repository video ZIP SHA-256
`24deadbcfd6fae2d5c6a0c77ee21dce13c4e634e84ff0041e5391284d8280f9e`.

The 0.14.2 follow-up applies the same transient-journal distinction to credential
and request-limit stores. It preserves all nine prior records and ZIP bytes. Only
a successful ordinary post-merge publication will advertise 0.14.2 as current;
repository 0.2.0 is unchanged. TV acceptance is still separate.


## Read-only list journey preparation (0.15.0)

The 0.14.2 follow-up merged at `c5a54e4655d19f6ba729e7fcd89ebe64edad407b`.
[Validation 43366073716](https://github.com/susanto-dev/homefx/actions/runs/43366073716)
and [publication 43366073709](https://github.com/susanto-dev/homefx/actions/runs/43366073709)
passed, including deployed-byte verification. Direct HTTPS checks confirmed the
0.14.2 index and both root/repository video ZIPs with SHA-256
`ff6f12515fc1ab7751629f8d9f80fa94791ebbc92c023ca59a34d99fa7065932`.

This batch prepares video 0.15.0 and retains all ten previous archive records and
bytes. Repository 0.2.0 is unchanged. The usual successful post-merge Pages workflow
would advertise 0.15.0; no independent deployment is required. Public browsing
remains synthetic: the packaged list interaction is inactive until registration,
account-bound route design and device acceptance gates are completed. No paid
service, dependency, account registration or new hosting is provisioned.


## Account-bound widget preparation (0.16.0)

The 0.15.0 preparation merged at `b3fd8af2422d78fc467750eac9a9a885c163a5be`.
[Validation 43368695530](https://github.com/susanto-dev/homefx/actions/runs/43368695530)
and [publication 43368695517](https://github.com/susanto-dev/homefx/actions/runs/43368695517)
passed, including deployed-byte verification. Direct HTTPS checks confirmed the
0.15.0 index and both root/repository video ZIPs with SHA-256
`c3b500261578d62d84f8ab3c8b8c7baf2cd979ea1b57a4fe950dccedd43c7e6e`.

This batch prepares video 0.16.0, preserving all eleven earlier package records and
bytes; repository 0.2.0 is unchanged. Only the ordinary successful post-merge Pages
workflow would advertise the new video version. Public routes remain synthetic.
No account, paid service, dependency or new hosting is provisioned.

Opening the inactive preference store in this version migrates its private schema
to version 3. Existing selections and clear epoch are preserved. Older runtimes
reject that newer schema: retained ZIP availability does not imply a safe downgrade
of a migrated profile. Installing the public preview does not itself open the real
account store. Never delete private storage or restore a backup merely to make a
downgrade pass; use a separate test profile for older releases.

## Verified 0.16.0 publication and journey validation

The 0.16.0 preparation merged at `df2ce7a36157e4ab90b360e78047b27d069007a8`.
[Validation 43371278475](https://github.com/susanto-dev/homefx/actions/runs/43371278475)
and [publication 43371278409](https://github.com/susanto-dev/homefx/actions/runs/43371278409)
passed, including build, deployment and deployed-byte verification. Direct HTTPS
checks confirmed video 0.16.0/repository 0.2.0 in the index and both video ZIP paths
with SHA-256 `2eaac9f49b747577e1b8f14d01382b56d4f4c3c7ceeb48ec6b45158db49bdca9`.

The whole-journey validation exposed lost cancellation state during renderer
cleanup. The small runtime correction requires video 0.16.1; published 0.16.0
remains unchanged. All twelve earlier archive records and bytes are retained,
with repository 0.2.0 unchanged. Only the ordinary successful post-merge Pages
workflow would advertise 0.16.1. This validation is not real-account, network/TLS
or TV acceptance.
