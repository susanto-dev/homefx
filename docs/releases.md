# Packaging and preview releases

This concurrent local-edit repair prepares `plugin.video.homefx` 0.17.2 alongside
`repository.homefx` 0.2.0. The owner authorized repository-first publication on the
existing GitHub Pages site. Protected main remains PR-only; the maintainer merges.
A merge publishes only after workflow checks pass. This does not establish TV
acceptance or enable live accounts, sources or playback. No skin is redistributed.

## Verified 0.17.0 publication

Checked on 2026-11-13: [PR #21](https://github.com/susanto-dev/homefx/pull/21)
merged as `6d744f54184784699ae6ce117a547b9ee66c5e62`.
[Validation](https://github.com/susanto-dev/homefx/actions/runs/43375911008),
[security](https://github.com/susanto-dev/homefx/actions/runs/43375910934),
[CodeQL](https://github.com/susanto-dev/homefx/actions/runs/43375910706) and
[publication](https://github.com/susanto-dev/homefx/actions/runs/43375910984)
passed on that merge. Publication includes build, deploy and published-byte verification.

An independent HTTPS read of `repository/addons.xml` advertised video 0.17.0 and
repository 0.2.0. Both the root video ZIP and indexed video ZIP matched the inventory
SHA-256 `c24b704af1812487f9a31fc1a4d3a2e1e334c8c6ec3ca973d094b88d3d738126`.
The root repository ZIP matched
`3b61f6e8771c1c3fa77cff09a3d4e98c2871c7181f0fe9193b2deba60abeaef9`.
This establishes publication, not TV installation or real-account acceptance.

The device-checkpoint documentation update changes no runtime, manifest, archive
or inventory. Its merge runs the normal publication workflow with the same package
versions and bytes; it does not introduce a Kodi update or activate live services.

## Verified 0.17.1 publication after configuration preflight

PR #24 merged as `32afae7023430492c3b787ca7acae420d4fc2e40`.
[Validation](https://github.com/susanto-dev/homefx/actions/runs/43387046582),
[security](https://github.com/susanto-dev/homefx/actions/runs/43387046612),
[CodeQL](https://github.com/susanto-dev/homefx/actions/runs/43387045415),
[publication](https://github.com/susanto-dev/homefx/actions/runs/43387046581) and
[Development configuration preflight](https://github.com/susanto-dev/homefx/actions/runs/43387046615)
passed. Publication's build, deploy and published-byte verification all completed.
Direct HTTPS checks confirmed video 0.17.1 / repository 0.2.0 in the hosted index;
both video ZIP paths matched SHA-256
`704224f23c5225c956a553bb84d896513222aca4dcf8e41c5c7cbbd13dc2455a`.
Configuration success establishes syntax only. Production was not dispatched;
registration, TV installation and live-account acceptance remain unverified.

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
match the repository packages. Validation runs under Python 3.11 and 3.12 independently;
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

## Episode watch-progress preparation (0.17.0)

The 0.16.1 repair merged at `ffc6b572166634ffdfcc1f5c3bac3e6d22f82f65`.
[Validation 43373871821](https://github.com/susanto-dev/homefx/actions/runs/43373871821)
and [publication 43373871771](https://github.com/susanto-dev/homefx/actions/runs/43373871771)
passed. Direct HTTPS checks confirmed video 0.16.1/repository 0.2.0 in the index
and both video ZIP paths with SHA-256
`458f3f6618fed4f153fb5d3cef44cfcd05d3496011332c96d9f5485b7394874b`.

Video 0.17.0 adds an inactive episode-view filter and watch-progress presentation.
All thirteen earlier archive records and ZIP bytes remain unchanged; repository
0.2.0 and preference schema 3 are unchanged. Only the ordinary successful post-merge
Pages workflow would advertise the new version. Public preview routes remain
synthetic, and existing saved URLs retain their default All-episodes behavior.
No paid service, new dependency, remote write or playback action is added.

## Navigation and standalone packaging repair (0.17.1)

The public adapter now stops adding rows when Kodi rejects a directory item and
finishes the listing unsuccessfully with disk caching disabled. It does not show an
error dialog for that interruption. Successful root, list and season routes remain
unchanged. Kodi's [21.2 directory API](https://github.com/xbmc/xbmc/blob/21.2-Omega/xbmc/interfaces/legacy/ModuleXbmcplugin.h)
returns submission success; rejecting a row must not be reported as a complete list.
This does not establish that Kodi removes already submitted rows or preserves focus:
Back, cancellation and return position still need actual-device checks.

Standalone package creation also refuses conflicting existing package/checksum bytes
and unsafe filesystem paths. A failed build must preserve prior outputs. This closes
a local tooling gap; it is not evidence of past hosted archive replacement. Existing
repository and site verification remain required. Source and destination trees must
remain quiescent during builds; this is not protection against an active filesystem
attacker or a multi-file filesystem transaction. Packaging requires filesystem
hard-link support and fails safely if unavailable. A process crash can leave an
incomplete ZIP/checksum pair; use a fresh output directory rather than expecting
a later build to repair that pair.

0.17.0 is already published and remains immutable. After review and main merge,
the normal workflow would publish video 0.17.1 with repository 0.2.0 unchanged,
retaining all previous archives. No live provider routes, credentials, remote writes,
playback or skin changes are introduced. The official checker limitations remain.

## Environment configuration preflight

The separate Trakt configuration workflow checks the selected environment's public
configuration offline. It does not alter video 0.17.1, repository 0.2.0, their ZIP
bytes, the inventory or Pages inputs. Merging this tooling change runs the ordinary
publication path with identical packages and starts a separate Development
configuration check. Production requires a manual main-branch selection. A green
configuration check establishes syntax only; live activation gates remain unchanged.

## Concurrent local-edit repair (0.17.2)

Video 0.17.2 prepares serialized, field-scoped demo mutations. Finishing list
selection after another invocation changes a watched flag or saves a movie retains
those unrelated changes. Movie removal confirms the explicit remove action even
when the initial snapshot did not contain the movie, so a concurrent addition is
not removed without confirmation. Cancelling a dialog performs no mutation; reset
remains an explicit all-field operation. Locks are acquired only after dialogs close.

The existing demo.json format and widget routes remain unchanged. A separate local
SQLite lock coordinates cooperating updated invocations; browsing remains JSON-only.
Bounded lock contention fails without reporting a successful edit. No private Trakt
or Real-Debrid store or account operation is changed. SQLite/filesystem behavior,
remote navigation and restart persistence remain TV acceptance items.

After review and merge, the normal publication workflow would index video 0.17.2,
keep repository 0.2.0 unchanged, and retain all older archives. Never replace the
already published 0.17.1 ZIP. Restart Kodi after upgrading so old invocations that
do not participate in the lock cannot write concurrently. A downgrade to older
code does not preserve this concurrency guarantee.

## Kodi 21.2 Python target alignment

Current source validation and Ruff target Python 3.11, matching the official Kodi
21.2 Android dependency line; CI covers 3.11 and 3.12. Retained video archives through
0.17.2 keep their original Python 3.8 syntax contract. Later video versions use the
3.11 syntax contract, and future syntax above 3.11 remains rejected. Historical
archive shape, hashes and contents are unchanged; this policy does not repackage
old releases or imply their device acceptance.

This tooling/documentation change does not modify runtime files, manifests or
release inventory. The normal merge-triggered publication rebuilds identical video
0.17.2 / repository 0.2.0 packages; no new Kodi update or live activation is created.
The runtime minimum is a project support policy, not a change to the `xbmc.python`
API requirement. See [development policy](development.md) for exact upstream evidence.

## Installation guide on the existing Pages site

The documentation batch adds `install.html`, generated from `docs/install.md`, and
a prominent landing-page link. All existing source, repository index, ZIP, checksum
and licence URLs are retained. Only the fixed additional guide file is accepted by
site/artifact validators; it is included in the exact published-byte comparison.
No runtime, add-on manifest, release inventory or archive changes are required.

Merging the reviewed PR runs the existing automatic Pages build/deploy/verification
workflow with identical video 0.17.2 and repository 0.2.0 packages. The guide is a
local candidate before merge; check its hosted response, links and layout after
that deployment succeeds. Do not independently dispatch or force publication.
Installation, skin-menu labels and device behavior remain unverified on the TV.

## Verified installation guide publication after PR 27

PR #27 merged as `d3d8658b3e1869de9bad62eb18d4c18ce47636d5` on 13 November
2026. Its [Publish preview run](https://github.com/susanto-dev/homefx/actions/runs/43404543315)
completed successfully, including deployment and published-byte verification.
Post-merge validation, security and the Development configuration preflight also
passed. The preflight establishes public configuration syntax, not registered
identity or live-account acceptance.

A separate hosted-byte check against the exact reviewed build matched **44 public
files, 1,547,638 bytes**, including the new
[installation guide](https://susanto-dev.github.io/homefx/install.html), landing
page, repository index, checksums and retained packages. Video **0.17.2** and
repository **0.2.0**, including root and indexed ZIP copies, retain the same bytes;
this publication creates no new Kodi add-on version. Existing release/archive URLs
remain available. These checks establish publication integrity, not successful
installation, widget behavior, private storage, TLS or live Trakt on the TV.

## 0.17.3 diagnostic candidate

The 0.17.2 TV report showed private permissions failed, SQLite not run and cleanup
passed. Its readiness dialog showed versions only. This candidate uses Kodi's
[native text viewer](https://github.com/xbmc/xbmc/blob/d1a1d48c3cb3722d39264ffdd8132f755ffecd27/xbmc/interfaces/legacy/Dialog.h)
for complete readiness/storage reports and adds a fixed storage failure-stage label.
The exact Android filesystem cause and actual TV scrolling remain unverified.
Permission requirements, cleanup and account activation gates are unchanged.

Because runtime bytes change, this proposal adds video **0.17.3** instead of replacing
0.17.2. Repository **0.2.0** and every existing archive/inventory record remain
byte-identical. The normal checked Pages deployment after merge will advertise
0.17.3, update the manual video download and installation guide, and retain older
indexed archives. Nothing is published independently; check post-merge publication
before updating the TV. This is a diagnostic release, not a storage compatibility
fix or live-account activation. Follow the [bounded rerun](testing-on-tv.md#observed-device-diagnostics-and-0173-rerun).

## 0.17.4 directory setup candidate

The 0.17.3 storage result stopped at directory permissions before SQLite; cleanup
passed. This candidate aligns the synthetic probe with explicit private-directory
setup: it sets `0700` on only the fresh test directory through a verified descriptor
and strictly checks the resulting mode. It distinguishes setting/inspection/mode
failures without exposing paths. Ignored or rejected permission changes still fail.
This is not a demonstrated Android filesystem fix; the TV rerun remains required.

The current 0.17.3 index/checksum and indexed video/repository package/checksum pairs
were verified. No repository-format defect was found. Documentation now covers
refresh timing, update settings and reselecting the latest HomeFX repository version
after a manual ZIP install. Automatic update delivery on the TV remains unverified.

Runtime changes require a new video **0.17.4** archive. Both new download URLs were
absent before preparation. All 17 prior inventory records and archive bytes are
preserved, including repository **0.2.0**. Merging uses the normal checked Pages
workflow to advertise 0.17.4 and update the guide; prior indexed video archives
remain available. No independent deployment, new dependency, account activation,
profile migration or storage-permission exemption is included.

## Development test ZIP in the existing source

The source-install candidate adds the separate `script.homefx.development` ZIP and
checksum to the existing Pages root listing, labeled Development test. It does not
add the script to `addons.xml`, provide repository auto-updates or activate live
routes in HomeFX Preview. The normal checked main-merge Pages workflow is the only
publisher; no separate deployment is required. Its build selects Development and
embeds only the public client ID/redirect in this test ZIP. Both become publicly
downloadable by design; no secret, credential or provider request belongs in the build.

Video 0.17.4, repository 0.2.0 and all 18 recorded archive bytes remain unchanged.
The extra test ZIP uses a full SHA-256 filename: different bytes require a different
URL. It is a current experimental candidate outside `releases/inventory.json`, so
older Development test URLs may disappear on a later merge. This does not relax
retention of any recorded video/repository release. Existing site validation,
bounded artifact staging and exact postdeployment byte comparison include the test
download pair and fail on partial, malformed or mismatched content.

After PR #32 merged, the normal publication passed and the hosted ZIP/checksum
were verified. The owner installed it through the source and passed its own
synthetic storage check. Connection failed before any authorization code appeared;
successful delivery and storage are not login acceptance.


## Published 0.17.5 activation-address compatibility repair

The shared parser and dialog now accept the exact current Trakt activation address
`https://auth.trakt.tv/activate` as well as legacy `https://trakt.tv/activate`.
A fabricated response reproduces the earlier rejection before code display. The
actual TV failure remains unproven; the separate Development test adds fixed failure
stages/categories and a bounded response status to support a safe rerun.

Because shared packaged runtime bytes change, prepare a new video **0.17.5** archive.
Do not overwrite 0.17.4. Repository **0.2.0**, all 18 prior inventory records and their
archive bytes remain unchanged. PR #33 subsequently merged and its post-merge validation, security and publication
passed. The existing Pages workflow advertises 0.17.5 and builds a new content-addressed Development
script ZIP with harness version 0.1.0. No independent deployment is required.

The test ZIP is not in the repository auto-update channel. Reinstall the newly
listed script ZIP from the existing source and fully restart Kodi before the
[bounded retry](development-device-test.md#retry-after-the-0176-candidate-is-published).
No registration changes, client secret, TLS relaxation, live preview activation,
list access, playback or new dependency is included. Device authorization,
persistence and refresh remain acceptance gates.

## Verified 0.17.6 publication and device follow-up

PR #34 merged as `e860684c06551de7fd203096f9e4f0816fe0a531`.
[Publish preview run 43485800643](https://github.com/susanto-dev/homefx/actions/runs/43485800643)
passed build, deployment and verification of deployed bytes against its uploaded
artifact. Post-merge Validation, Security and Development configuration preflight
also passed. The hosted index advertises video **0.17.6** and repository **0.2.0**.

A fresh hosted check matched the video and repository root ZIPs to the recorded
archives and their hosted checksums, and the Development ZIP to its checksum filename.
A local attempt to download the Pages run artifact was denied by its storage host;
the complete deployed-artifact comparison is evidenced by the successful workflow
step above, not a repeated local full-site check.

The release adds the required OAuth API-key/version and identifying user-agent
headers without changing TLS, fixed hosts or retry policy. All 19 preceding archive
records/bytes were preserved. The owner subsequently reported **Connection test:
authorized** and **Refresh rotation: passed** in the separate Development program
add-on. No list/history request was made by the refresh test; this is not video
live activation or proof of restart persistence and all failure paths.

The follow-up documentation batch changes no manifest, runtime, inventory or archive.
Merge will refresh the Pages installation guide through the existing checked
workflow. Video 0.17.6, repository 0.2.0 and the Development script bytes remain
unchanged for unchanged public configuration. No new ZIP installation is required
for the [post-login checklist](development-device-test.md#after-successful-authorization-and-refresh).
No independent dispatch/deployment is needed.

## 0.17.7 joined video entry candidate

The proposed release adds the shared read-only video dispatcher, while the public
entry point and live configuration stay inactive. The separate program builder
bundles shared runtime source, so its digest filename changes as well; it does not
enable new program actions. Existing successful device checks need no reinstall.

Prepare a new video 0.17.7 archive and preserve all 20 previous records and bytes.
Repository 0.2.0 remains unchanged. Merge uses the existing checked Pages workflow;
no independent deployment or workflow dispatch is required. Current hosted video
0.17.6 and repository 0.2.0 hashes match the retained inventory. PR #35 post-merge
validation, security and publication passed. This candidate is not yet published.

The additional recovery test uses synthetic token stores and actual child-process
exit. It does not contact Trakt or establish live interrupted-refresh acceptance.
See [video integration](video-integration.md) for the remaining configuration-delivery
and deliberate real-list TV acceptance work.

## 0.17.8 Development video candidate

PR #36 merged as `5338ef6e6ca30eaecc69c7a984a8c308a73d333f`; post-merge Validation,
Security, configuration preflight and normal Pages publication passed for video
0.17.7. The new proposal preserves all 21 prior archive records and adds video
0.17.8 for shared configuration/routing changes. Repository 0.2.0 stays unchanged.
The public preview's entry point remains synthetic and keeps its existing URLs.

After a reviewed merge, the existing Development-bound Pages build will publish
both program and video experimental ZIP/checksum pairs. No workflow dispatch or
independent deployment is needed. Each uses a separate add-on ID and content-addressed
filename; neither enters the repository index or auto-updates. The video candidate
is labelled owner/invited-user testing and requires fresh own-profile login plus
list-read consent. Publishing or installing does not start login. Production is not
selected. Real accounts remain outside CI; PR builds use fabricated public config.

The artifact verifier compares every candidate member with the reviewed source and
canonical public configuration, and the normal hosted-byte check covers both pairs.
No previous recorded release is rebuilt or overwritten. Experimental candidate
URLs may be retired; the same digest URL must never serve different bytes.

## Verified Development video delivery after PR #37

PR #37 merged as `a28ad740458a363e48fae0c6f4284cd179195bb5`. Validation, Security,
CodeQL and Development configuration preflight passed. In [publication run
43538312664](https://github.com/susanto-dev/homefx/actions/runs/43538312664), build
and deploy succeeded, but the first `verify-published` attempt failed with
`published request failed`. Its redacted log did not identify the file or HTTP status;
the underlying cause is unknown. This is not evidence of a reproduced byte mismatch.

Only the final read-only verification job was rerun, against that run's original
uploaded artifact. The rerun checked 60 public files (2,425,114 bytes) successfully;
the original build/deploy start times remained
unchanged. No new build, deployment, workflow dispatch, account access or package
replacement occurred. A local artifact-download attempt was denied by its storage
host; the complete uploaded-artifact comparison is evidenced by the successful
GitHub verification job, not an independently downloaded local artifact.

Fresh hosted reads also verified index versions video 0.17.8 / repository 0.2.0,
root ZIP/checksum equality with recorded archives, and both experimental Development
ZIPs against their full expected source/schema and content-addressed checksums.
The video candidate's digest is
`bab63c56e240bc3bcb0f579b3021d03245f90d6bac7bc8de4071f847cdf70d5b`.
See the [exact download and next TV steps](development-video.md).

The diagnostic follow-up identifies only a validated public relative file, a fixed
request category and a bounded HTTP status (when available), or a mismatch file.
It adds no retry/sleep, keeps exact-byte comparison/TLS/budgets intact, and never
prints response bodies, headers, raw exceptions or redirect destinations. An HTTP
status alone does not identify which network hop produced it.

No add-on source, manifest, inventory or archive changes are required. Merging the
follow-up updates the verifier and Pages guide through the normal workflow; current
video/repository and experimental ZIP bytes stay unchanged for unchanged public
Development configuration. No new installation is needed for diagnostics alone.

## 0.17.9 source and artwork proposal

The new original house/TV icon changes video package bytes, so video advances from
0.17.8 to 0.17.9. Repository 0.2.0 is unchanged; all 22 preceding inventory records
remain. Development ZIPs use their existing content-addressed scheme and get new
digest filenames, without changing their addon IDs or moving any account data.
Nothing is published until the reviewed merge and normal workflow succeed.

The source's main listing offers repository + Development Video. The advanced/
folder supplies byte-identical copies of the current manual Preview and program
diagnostics ZIPs. Every indexed archive also retains its root filename/checksum URL;
older releases are hidden from the install picker, not overwritten or deleted.
Artifact topology, duplicate-byte equality, links, archive history and exact hosted
verification cover the new folder and retained aliases. Kodi navigation of the new
folder remains a device check, independent of parser-oriented tests.

The icon follows [Kodi artwork guidance](https://kodi.wiki/view/Add-on_structure#icon_specifications):
512×512 PNG, fully opaque, generous padding, simple house/television silhouette and
no Kodi/third-party logo. The existing manifest asset path is retained. Build checks
validate dimensions, RGB opacity, PNG chunks/checksums and bounded image data;
historical archive artwork policy remains unchanged. No new paid asset/library or
licence change is introduced. Other title placeholders are unchanged.

## 0.17.10 list-description proposal

PR #42 publication passed for video 0.17.9 / repository 0.2.0, including hosted-byte
verification. The next candidate changes runtime metadata display and therefore
prepares video 0.17.10 without replacing 0.17.9. All 23 previous package records and
bytes remain; repository 0.2.0 is unchanged. Normal merge publication creates new
Development digest ZIPs because shared runtime bytes change. Add-on IDs/profiles
remain the same; no credential migration or fresh login is needed solely for this
update. Public Preview stays synthetic. No new provider is activated or artwork
redistributed. Publication and TV presentation of this candidate remain pending.

## 0.17.11 inactive artwork-cache proposal

PR #43 published video 0.17.10 / repository 0.2.0; all post-merge checks and deployed
artifact verification passed. The next proposal adds packaged inactive TMDB client/
cache modules and retains optional list TMDB IDs, so video advances to 0.17.11.
All 24 prior records/bytes remain and repository 0.2.0 is unchanged. Normal merge
publication generates new Development digest ZIPs; no publication is dispatched.
Neither Kodi entry point constructs the provider or cache. No new TV test, login,
credential migration or paid provider is required for this inactive preparation.
Actual artwork integration remains gated as described in [TMDB artwork](tmdb-artwork.md).

## 0.17.12 selected-list movie-progress proposal

PR #44 published video 0.17.11 / repository 0.2.0 with successful post-merge and
hosted-byte checks. The next proposal changes shared runtime code and the
Development video menu, preparing video 0.17.12 plus new content-addressed
Development ZIPs. All 25 prior inventory records/archive bytes remain; repository
0.2.0 is unchanged. Normal publication occurs after maintainer merge and checks;
no independent dispatch or deployment is requested.

Only the deliberately installed Development Video gains the new read-only movie
progress views. Public Preview and Production remain inactive. Existing profile,
account, selected-list refs and normal widget URLs remain; no credential migration
or fresh login is required solely for this update. New movie-history/filter/skin
behavior needs TV acceptance. See [movie progress](movie-progress.md).

## Native Kodi identity proposal (0.17.13)

This candidate exposes existing public media IDs through Kodi tags and preserves
selected parent-show identity for season/episode rows. It adds no provider calls,
Helper dependency or activation. The normal merge-triggered Pages workflow will
publish video 0.17.13 and new checksum-named Development packages after its gates.
Repository 0.2.0 and all 26 prior package records/bytes remain unchanged.
No independent deployment is authorized. Verify the uploaded artifact against
hosted bytes after merge. Existing video-profile credentials and saved routes are
retained; update Development Video and restart Kodi for the bounded
[metadata compatibility check](kodi-metadata.md).

## Selected-show unwatched proposal (0.17.14)

The candidate adds a read-only cross-season context route to Development Video.
Normal merge-triggered Pages publication prepares video 0.17.14 and new
checksum-named Development downloads; repository 0.2.0 and all 27 prior package
records/bytes remain unchanged. No independent publication or public/Production
activation. Verify hosted bytes after merge, then update Development Video and
restart Kodi for the [bounded TV check](show-unwatched.md); retain current login/lists.

## Development-only demo packaging cleanup

The Development builder omits three unused public-Preview demo modules from its
video and program ZIPs. No public video/repository source or release inventory
changes: video 0.17.14 and repository 0.2.0 remain byte-identical. No version bump or
new retained archive is needed. Normal merge-triggered Pages publication creates
new content-addressed Development filenames; it never overwrites a digest filename
with different bytes. Prior experimental URLs may disappear under the existing
Development retention policy; retained Preview/repository archives remain present.

After merge, verify hosted bytes against the uploaded artifact as usual. No
independent deployment. Updating Development Video from the current source ZIP and
restarting Kodi is sufficient to receive the leaner package; no login reset,
profile cleanup or repeat of completed account tests is requested. This cleanup
introduces no new product flow or TV performance claim.

## Widget MVP setup proposal (0.17.15)

One candidate combines a skin-browsable widget folder tree, Development on-screen
setup/help and local build information, and a source-verified guide for the existing
Arctic Zephyr Reloaded 3.0.3 layout. Existing terminal widget URLs, account profiles
and saved selections are preserved. Static setup menus do not read accounts; real
list/show choices retain membership and final-render guards. No skin settings are
modified. Public/Production live activation, playback and new providers stay inactive.

Normal merge-triggered Pages publication prepares video 0.17.15 and new
content-addressed Development ZIPs. Repository 0.2.0 and all 28 prior package
records/bytes remain unchanged. The Development video package adds a deterministic
public build record, excluding app configuration from its runtime fingerprint;
this is descriptive identity, not a signature or a check of installed files.
The diagnostic program remains separate and receives shared-runtime changes only.
No credentials are migrated or embedded and no new paid dependency is introduced.

Verify the actual uploaded artifact against hosted bytes after merge. Then update
Development Video from the existing HomeFX source and fully restart Kodi, retaining
current login/selections. Follow [one list and one skin row](widget-mvp.md) before
adding a second row. Source inspection and synthetic tests do not establish TV
navigation, persistence, artwork or performance. No independent deployment or
repeat of completed account tests is requested.

## Selected-show progress proposal (0.17.16)

Development Video adds separate Continue watching, Next aired unwatched and Upcoming
terminal folders for one selected show's regular seasons. Existing routes, private
account storage and saved selections are preserved. Public Preview remains synthetic;
no playback, remote writes, scrobbling or provider activation is added.

Normal merge-triggered Pages publication prepares video 0.17.16 and content-addressed
Development downloads after its gates. Repository 0.2.0 and all 29 prior archive
records/bytes remain unchanged. No independent publication or overwrite is authorized.
Verify the deployed artifact and hosted bytes after merge before using a new filename.
Then update Development Video from the existing source and fully restart Kodi, keeping
the existing login. See the [short progress-row check](show-progress.md). No repeat
authentication test is required; skin behavior, live progress and timing need TV
evidence. Unknown dates/watch state do not become playable or unwatched claims.

## Account-wide Continue Watching proposal (0.17.17)

Normal merge-triggered publication prepares video 0.17.17 and new content-addressed
Development downloads after tests and package gates. All 30 prior archive records
and bytes remain unchanged, as does repository 0.2.0. Public Preview stays synthetic.
The account-wide widget uses existing read-only endpoints and private account storage;
there is no schema migration, credential transfer or public/Production activation.
No independent publication is authorized. Verify the hosted artifact after merge,
then update Development Video and fully restart Kodi while retaining the existing
login and lists. Follow the [short feed check](continue-widget.md); no repeated
authentication test is needed solely for this change.

## Personal calendar widget proposal (0.17.18)

Normal merge-triggered Pages publication prepares video 0.17.18 and content-addressed
Development downloads after all gates. Repository 0.2.0 and all 31 prior package
records/bytes remain unchanged. The calendar uses the existing read-only endpoint;
public Preview stays synthetic, with no public/Production activation or independent
deployment. No schema migration, credential transfer or new provider is introduced.

After verified publication, update Development Video from the current source ZIP and
fully restart Kodi, retaining the existing login/lists. Follow the [calendar TV
check](calendar-widget.md). Calendar scope, service entitlement, navigation and timing
remain unverified on TV; a date never establishes playable availability.
