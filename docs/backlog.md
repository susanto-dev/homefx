# Complete project backlog

Status checked on 14 November 2026: published **video 0.17.16 / repository 0.2.0**.
PR #51 merged as `db9db3b8aae80f2b1b116ad55d927835aa735a0a`; Validation,
Security, configuration and [publication/hosted-byte verification](https://github.com/susanto-dev/homefx/actions/runs/43597291985)
passed. Its per-show Continue/Next/Upcoming folders are published; their live TV
acceptance remains pending. Real saved-list selection and 100+ movie browsing passed
on TV. Direct TMDB and public/Production activation remain deferred.
**Implemented** means source and automated checks exist; **published** means
release bytes are hosted. Neither means tested on the TV or against a real account.
**Mocked/inactive** means service/player code is not wired into Kodi. **Pending**
means work or external evidence is still required. **Decision** needs a product,
provider or release choice. The current public add-on remains synthetic.

## Browsing and personal library

| ID | Item | Status | Remaining work / acceptance |
|---|---|---|---|
| B01 | Single repository, video add-on, Kodi 21 Python manifest | Implemented; TV reports Kodi 21.2 / Python 3.11.7 | 0.17.4 synthetic storage passed; broader device acceptance remains pending |
| B02 | Multiple selected list widgets and folder browsing | Published in Development Video; unified widget folder picker published; public Preview remains demo-only | Real list selection/save and 100+ movie browsing passed; separate skin-row assignment, widget access and restart acceptance pending |
| B03 | Episode/season browser, watched counts, aired-unwatched filter | Published Development season and cross-season read-only browser; picker published | Live episode identity/status, season navigation and refresh behavior on TV |
| B04 | Continue watching, unfinished first, next aired unwatched | Published Development selected-list unfinished movie rows; per-show episode Continue/Next/Upcoming published; account-wide Continue candidate; global Next/Upcoming inactive | New movie-progress TV acceptance; later episode continuation, resume and performance |
| B05 | Save movies including unreleased titles, upcoming view | Implemented locally; Trakt list-add mocked | Live owned-list selection/write outcomes; regional release semantics |
| B06 | Manual mark watched | Implemented locally; remote add-history mocked | Explicit live writes and uncertain-result reconciliation; remote unwatched/history deletion needs separate semantics |
| B07 | Title search | Demo implemented; Trakt title-search contracts mocked/inactive (0.9) | Live literal-query behavior, entitlement, keyboard/context-menu UI and TV integration |
| B08 | Similar movies | Demo implemented; Trakt related-movie contracts mocked/inactive (0.9) | Live relevance and UI integration; results establish neither watch state nor playable sources |
| B09 | Release dates and sorting | Provisional rules implemented | Choose movie region/release type and confirm ordering; dates never prove source availability |
| B10 | Skin and home layout | Existing skin retained | TV navigation/focus/widget headers; separate skin only if demonstrated necessary |
| B11 | Upcoming personal episode calendar | Mocked/inactive (0.11) | Confirm live personal-calendar coverage and entitlement; a selected-show filter is only an intersection, not a complete selected-list schedule |

### Concurrent local demo edits (published in 0.17.2)

The reproduced stale-dialog lost-update bug is repaired with serialized, field-scoped
mutations. A selection save retains unrelated watched and movie-list changes made
while its dialog was open. Cancellation performs no edit, and reset deliberately
clears all demo fields. Backend contention and unsafe-path checks plus adapter
interleaving tests cover fabricated data. Actual TV behavior remains pending.
The JSON format is unchanged; all writing invocations must use the updated runtime.
This repair does not alter private account stores or enable live services.

## Trakt and account data

| ID | Item | Status | Remaining work / acceptance |
|---|---|---|---|
| T01 | Device login, refresh, protected token store, HTTPS/session guards | Shared implementation; program lifecycle passed on TV; Development identity/redirect owner-confirmed | Video selected-list browsing owner-confirmed; video restart acceptance pending; denial/expiry and interrupted refresh use automated evidence, with live outcomes unclaimed. Do not repeat completed program checks |
| T02 | Account connect/cancel/switch/disconnect UI | Shared UI and Development video entry published | Program consent/cancellation/restart/disconnect passed; video-profile UI/account switching and service-side revocation remain separate acceptance |
| T03 | Personal/liked lists and saved account-bound selections | Published in Development Video; synthetic end-to-end acceptance passed | Selection/save and opening a real 100+ movie list passed; verify widget and saved selection after restart on TV |
| T04 | Complete movie watched snapshot and filtered joins | Published Development movie-progress views; synthetic adapter tests passed | Actual endpoint/entitlement, filter and performance acceptance on TV; failed snapshots never mean unwatched |
| T05 | Live Trakt read views | Read-only selected-list Development candidate published; public/Production inactive | Validate candidate on TV; per-show episode progress candidate; global feeds need separate integration |
| T06 | Live history/list actions | Pending | Separate consent/outcome checks after reads; no automatic write retries |
| T07 | Persistent metadata cache, shared rate limiting and performance | Invocation-memory cache and shared request limits wired in Development Video; persistent metadata cache pending | Validate shared limits and cold/warm/multiple-row load times on TV; use measurements to decide cache retention/invalidation |
| T08 | Wider public Trakt application access | Pending external approval | Service registration/Production requirements and current terms review |

## Real-Debrid

| ID | Item | Status | Remaining work / acceptance |
|---|---|---|---|
| D01 | Open-source device authorization and refresh contracts | Mocked/inactive | Register application; verify exact pending-authorization response on device; no bundled shared secret |
| D02 | Account/download/link-resolution contracts | Mocked/inactive | Validate service responses/entitlement with own account on TV; no title catalogue or discovery claim |
| D03 | Separate private credential store and durable refresh claims | Mocked/inactive; lock deadlines and persistence guards hardened (0.14) | Private SQLite and account-generation tests; actual Android permissions and recovery pending |
| D04 | Fixed-host bounded HTTPS/form transport | Mocked/inactive (0.8) | Injected connection tests; actual TLS/DNS/cancellation behavior pending |
| D05 | Session/login/refresh/read/resolve coordination | Mocked/inactive (0.8) | Joined store/transport tests and stale-response rejection; live activation pending |
| D06 | Real account UI and activation | Assembly, flow and dialog adapter inactive (0.12); live menu pending | Wire only after D01–D05 validation; cross-device quota coordination and disconnect/revocation UX remain |

## Sources and playback

| ID | Item | Status | Remaining work / acceptance |
|---|---|---|---|
| P01 | Authorized source input/discovery | Decision | Choose explicit supplied links and/or a reviewed source provider; metadata cannot substitute for sources |
| P02 | Umbrella handoff experiment | Pinned source/route/licence inspection complete (0.9); device handoff unverified | Verify installed version/provenance and supported interface, then movie/episode, cancellation, subtitles, resume and ownership tests; no adapter enabled |
| P03 | Native playback coordination | Mocked/inactive; event observer added (0.10) | Single-attempt dispatch and AV-start evidence separated; real Kodi adapter and dispatch/account ownership remain |
| P04 | Playback, subtitles, seek/resume, cancellation/errors | Pending TV validation | Validate actual AV start and end-to-end behavior with authorized media |
| P05 | Resume and Trakt scrobbling ownership | Decision / pending | Exactly one owner; start/pause/stop/completion and manual correction tests |
| P06 | Next aired episode / offer next aired unwatched | Demo choice implemented | Actual end-of-playback sequencing, watched reconciliation and cancellation |

## Distribution, quality and governance

| ID | Item | Status | Remaining work / acceptance |
|---|---|---|---|
| R01 | Reproducible manual ZIP and public Pages preview | Published 0.17.14; Development video/program downloads byte-verified | Development video TV acceptance pending |
| R02 | Repository package/index/checksums, retained packages and verifier | Implemented; experimental repository channel published (0.9) | Current deployed-byte verification passed; clean repository-first install still needs TV evidence |
| R03 | Repository hosting, upgrades and rollback | Experimental Pages channel, immutable history and local release preparation implemented; HTTP verification passed; TV acceptance pending | Verify each new publication; test clean install/upgrade and documented rollback on TV |
| Q01 | Python 3.11/3.12, manifests/XML, packaging/repeatability checks | Implemented; aggregate results, boundary regressions and whole-journey integration coverage | Continue regression coverage; cloud tests never replace TV tests |
| Q02 | Weekly security/dependency/Action update checks and SHA pins | Implemented; GitHub graph verified and offline inventory consistency guard added | Manual issue triage; no automatic update PRs or PR comments |
| Q03 | Full Kodi add-on checker, pinned linter, package hash lock | Pinned Ruff correctness gate and dependency hash locks implemented (0.9); source manifest contracts strengthened; official checker pending | Full checker blocked on reviewed secure/offline input and compatible repository schema; diagnostic schema checks are not a full pass |
| Q04 | Device readiness and sanitized test checklist | Implemented; 0.17.4 synthetic storage passed on TV | Development storage, authorization/refresh, restart and responsive offline handling passed; video-profile and live widget acceptance remain |
| G01 | Original-code licence | Decision | Existing MIT remains; final owner preference still unconfirmed |
| G02 | Third-party source/assets and service compliance | Ongoing gate | Verify exact licence/compatibility before reuse; no upstream source/assets copied |
| G03 | Public repository neutrality and secret hygiene | Implemented practice | Keep credentials/private watch data out of source, artifacts, logs and public discussion |

## Completed: Python target and installation guide

Python 3.11 is the source/runtime target following the official Kodi 21.2 Android
build; CI also checks 3.12. Retained archives keep their historical syntax contract.
The Python-target change did not change runtime files or package bytes.

PR #27 merged as `d3d8658b3e1869de9bad62eb18d4c18ce47636d5` and adds the
[installation guide](install.md), linked from the README and Pages landing page.
The [post-merge publication workflow](https://github.com/susanto-dev/homefx/actions/runs/43404543315)
passed, including deployed-byte verification. A separate hosted check matched all
44 public files; see [publication evidence](releases.md#verified-installation-guide-publication-after-pr-27).
Video 0.17.2, repository 0.2.0 and
retained archives are unchanged. Security and the Development configuration
preflight also passed. The guide explicitly marks installation and skin steps as
unverified on TV; publication does not establish device acceptance.

## Historical milestone: configuration preflight and local-edit repair

PR #24 merged as `32afae7023430492c3b787ca7acae420d4fc2e40`; its validation,
security, CodeQL, publication and Development configuration preflight passed.
At that checkpoint, hosted video 0.17.1 root/indexed ZIPs matched the inventory.
The subsequent 0.17.2 release contains the concurrent demo-state lost-update
correction described above. Public configuration syntax acceptance does not prove
registered identity, actual login/refresh or device readiness.

## Published diagnostic checkpoint: 0.17.3

The TV reports HomeFX 0.17.2, repository 0.2.0, Kodi 21.2 and Python 3.11.7.
Private file permissions failed, SQLite commit/rollback did not run, temporary
cleanup passed and the overall result did not pass. Only version fields were
visible in the supplied readiness result, so SQLite/TLS capability evidence is
still missing. The precise storage failure cause remains unknown.

Version 0.17.3 added scrollable diagnostics and a fixed **Failure stage** label.
Its subsequent TV storage report identified **directory permissions**, with SQLite
not run and cleanup passed. The underlying filesystem cause remains unknown;
see the published 0.17.4 checkpoint below. No path, token or private account data is required.

## Next checkpoint: one real list in Development Video

Video 0.17.8 and repository 0.2.0 are the published preview. Start with the
[activation handoff checklist](activation-checklist.md), which separates demo TV
evidence from the later, explicitly authorized Development account test.
Keep the existing functionality and skin. Prioritize selected-list widgets, distinct
progress/next/upcoming views, remote navigation and repository-first installation.
Do not add options or integrations for feature parity, or claim a smaller scope
improves performance without measurements. No additional demo feature is needed
before the [bounded TV checklist](testing-on-tv.md).

| Priority | Backlog scope | Current status / next acceptance |
|---|---|---|
| 1 | B02–B03, T01–T03, T05 | Install the published Development video candidate, check its own storage, authorize fresh, select one real list and browse title/season details |
| 2 | B02, B10, T03, T07 | Assign one skin row separately; verify focus/Back/return position and selection persistence after restart; measure cold/warm and then multiple-row loading |
| 3 | R02–R03 | Verify repository-first installation and update behavior for public Preview; the experimental video candidate remains deliberate ZIP installation |
| 4 | B04, B11, T04–T05 | After selected-list acceptance, choose one bounded read-only progress row; keep Continue Watching, Next aired and Upcoming distinct |
| Ongoing | Q01–Q02, R01–R03, G02–G03 | Preserve tests, security/manual triage, independent review, privacy and immutable publication |
| Later | Q03, T07 | Official checker secure/offline input; persistent cache only after device measurements justify it |
| Deferred | T06, D01–D06, P01–P06 | Remote writes, Real-Debrid, sources/playback and scrobbling require separate decisions and gates |

Device and registration gates cannot be satisfied by cloud tests. Protected main
remains maintainer-merged after independent review and successful checks.

## External inputs and decisions

The next useful device evidence is the deliberately enabled video-profile list
journey and widget/navigation using the published, verified Development candidate. Completed
Development lifecycle checks need not be repeated. Registered Development values are
owner-confirmed; no app values need to be posted. Real lists/views,
movie release region/type, first playback path, source-provider choice, scrobbling
ownership, final original-code licence and TV acceptance of repository updates/rollback remain open.
Remaining account-lifecycle and read-only device evidence still block public live activation. Playback, movie-region and licence decisions do not require another demo-feature batch; completed independent work does not satisfy the activation gates. Never send secrets,
account exports, watch history or a full Kodi backup.

NBA, a separate Android app and an always-on server are outside scope. A new skin is
a conditional future option, not a required component. See [playback plan](playback-plan.md),
[account gates](account-setup.md), [handoff evidence](umbrella-feasibility.md),
[metadata contracts](metadata-contract.md) and [TV checklist](testing-on-tv.md).

## Published 0.17.4: directory setup and update recovery

The owner reported 0.17.3 stopping at **directory permissions**, SQLite **not run**,
cleanup **passed**, overall **not passed**. The complete storage report is now
visible. The underlying filesystem cause is not established. Version 0.17.4
explicitly sets and strictly verifies permissions on only the probe's fresh
synthetic directory, matching private-store setup, and adds a fixed initial
`Directory check` result. It does not activate accounts or weaken permissions.

The hosted 0.17.3/repository 0.2.0 index and SHA-256/package paths were verified.
No repository format defect was found. Kodi refresh timing, update settings and
manual ZIP origin are separate from publication: use the documented repository
refresh/version-selection steps. Auto-update on the TV remains unverified.
The owner subsequently reported all 0.17.4 synthetic storage checks passed, including
cleanup, with failure stage none. This does not establish live account acceptance. No source-provider, playback, scrobbling or custom-skin expansion is included.

## Published: isolated Development device-test artifact

The owner confirmed the registered Development ID and redirect match GitHub variables.
A separate **HomeFX Development Test** program add-on is prepared for explicit
storage, local status, device authorization, one refresh rotation and disconnect
checks. Its main-only Pages build lists a content-addressed test ZIP in the existing
HomeFX File manager source. The redundant manual artifact workflow is now removed. It does
not add a Kodi repository index entry or activate
HomeFX Preview. See the [bounded test instructions](development-device-test.md).

The test uses its own profile, scoped by public app identity. Tokens never enter CI,
artifacts, logs or public reports. No list/account API reads, remote history/list
writes, playback, Real-Debrid or scrobbling are enabled. A reviewed implementation
and fabricated tests are not real login, TLS, refresh or TV evidence. After those
results, plan the smallest real read-only list/widget integration; do not add more
demo-only features to substitute for that acceptance.

## Verified delivery: install the Development test from HomeFX

PR #32 merged and its post-merge validation/publication passed. The hosted test ZIP
and checksum were verified. The owner installed it directly from **Install from zip
file → HomeFX**, then passed its own permissions, directory, SQLite and cleanup
checks. Local status disconnected was the expected pre-login result. Connecting
failed before any code appeared; the remaining account tests were not run.

## Published 0.17.5: activation-address compatibility and safe diagnostics

The current Trakt documentation names `https://auth.trakt.tv/activate`, which the
earlier parser/dialog rejected. A fabricated response reproduces that bug. The
repair accepts that exact address and the legacy exact address, without broader
URL trust. This fixes a reproduced compatibility bug. The later TV result is a 403 request
rejection before activation-address validation.
The separate test now reports fixed Last stage, Category and Response status on failure;
no response body, code, token or exception text is exposed.

PR #33 merged and post-merge validation, security and publication passed for video
0.17.5. Repository 0.2.0 and all 18 prior archive records/bytes were preserved. The script keeps harness
version 0.1.0 with a new checksum filename. Reinstall it directly from the HomeFX
source after verification; it is not automatically updated. The first bounded retry
is code display followed by cancellation before authorization, or fixed failure
categories if it still fails. No live list, playback or provider scope is added.

## Published 0.17.6: required Trakt request headers (historical repair)

Before the header repair, the Development attempt reported device response validation, request status
rejected, response 403. No code appeared, and the owner stopped. The local limiter
only generates 429, so this rejection came from the HTTP response path; successful
authorization was unverified at that checkpoint.

Current Trakt documentation requires headers missing from earlier OAuth requests.
The candidate adds the request's own public client ID as API key, API version 2 and
an identifying HomeFX user agent; existing API helpers gain the same user agent.
No secret, foreign identity, endpoint change, retry or TLS relaxation is introduced.
The confirmed contract mismatch is not yet a proven diagnosis of the TV's 403.

The release preserved all 19 prior records/archives, including 0.17.5, and kept
repository 0.2.0 unchanged. Its original retry checklist is superseded by the
post-login checks below. No list/playback scope was added.

## Current checkpoint: Development authorization and refresh passed

This records the completed program-test checkpoint. The current product acceptance
is the Development Video list/widget journey described below.

PR #34 merged as `e860684c06551de7fd203096f9e4f0816fe0a531`. Validation,
Security, configuration preflight and Pages publication/deployed-byte checks passed.
Video 0.17.6 and repository 0.2.0 are published; all 19 preceding archive records
were preserved. The owner supplied successful authorization and refresh-rotation
reports from the separately installed program add-on; the refresh made no list/history request.

| Next bounded item | Status | Evidence still needed |
|---|---|---|
| Development login and one refresh | Passed on target TV | Broader failure paths remain separate |
| Restart persistence | Passed on TV after full restart | Local status reported credentials stored |
| Local disconnect and code-dialog cancellation | Passed on TV | Disconnect and post-cancel status disconnected; cancellation reported cancelled |
| Offline failure and recovery | Passed on TV | Kodi remained responsive during request; error dismissed with Back; network restoration allowed code issuance; elapsed time unmeasured |
| Denial/expiry and interrupted-refresh recovery | Automated failure evidence; not live-tested | See testing.md; no destructive real-token test requested |
| Read-only connection/list/widget in the video add-on | Development candidate published; public Preview inactive | Own-profile login/storage, one list and restart acceptance |
| Live performance and skin navigation | Not measured | Cold/warm, multiple rows, focus/Back/return position |

The program is a temporary authentication test, not the intended product interface.
Do not migrate its tokens into the video profile or add more demo features to avoid
these acceptance steps. Follow the [post-login checklist](development-device-test.md#after-successful-authorization-and-refresh).
Writes, playback, Real-Debrid and scrobbling remain outside this milestone.

## Completed in PR #36: joined video entry

The authentication implementation is already shared: the Development ZIP bundles
modules from the video add-on source. The missing adapter joins those modules with
list selection and widget rendering for a future gated Kodi entry point. This batch
adds that adapter and process-interruption recovery regressions with synthetic tokens.
It does not activate the public preview, import program credentials, add a provider,
or change stable demo/widget routes. No repeated successful owner test is required.

Published video 0.17.7 kept repository 0.2.0 unchanged and preserved all 20 prior
archive records. The following candidate resolves Development configuration delivery
with a distinct video ID and immutable checksum-named download; it does not replace
a published package. Existing variables supply only public Development configuration.
A general public connection must not presume Production approval from owner tests.

## Published candidate: one real list in Development Video

The dispatcher and synthetic abrupt-process recovery regression from PR #36 are
complete, merged and independently reviewed. They are reused without duplication.
The published 0.17.8 release adds a distinct, deliberately installed Development video ID,
shared public-configuration validation, candidate-specific widget links and checked
content-addressed delivery on the existing source. The program is not a dependency;
the candidate has a fresh own-profile login. Public Preview and Production stay inactive.

| Item | State |
|---|---|
| Development auth/refresh/restart/disconnect/cancel/offline responsiveness | Owner-confirmed; do not repeat |
| Shared dispatcher and synthetic process interruption | Complete in PR #36 |
| Development video configuration and package delivery | Published and byte-verified after PR #37; ready for deliberate TV installation |
| One real personal/liked list, seasons, saved selection after restart | Selection/save and 100+ movie list opening owner-confirmed; season browsing and restart acceptance pending |
| Existing-skin row, focus/Back, cold/warm and multiple-row loading | Pending actual-device measurements |
| Public/Production connection, writes, playback, Real-Debrid, scrobbling | Inactive; outside milestone |

The [short candidate checklist](development-video.md) needs only deliberate install,
new profile storage check, fresh owner login and private selection of one list. No
keys, secrets, list names, raw logs or profile files should be supplied in chat.

## Publication diagnostics follow-up

The first PR #37 post-deploy byte check failed with a generic request error. Fresh
root-package checks and a verification-only rerun against the original uploaded
artifact passed; no build or deployment was repeated. The initial file/status/cause
was not recorded, so it is not labelled a proven cache, propagation or service bug.

The follow-up adds a verified public relative filename and fixed request category /
bounded HTTP status to failures, plus the filename for byte mismatches. Bodies,
headers, redirects and raw exception text remain private. There are no added retries,
sleeps, relaxed checks or changed add-on archives. No additional feature code is
needed before the existing candidate's first real-list/widget TV test.

## Development delivery cleanup

The separate manual Actions artifact workflow and its transfer instructions are
removed; the normal Pages source supplies both experimental ZIPs. Validation,
Security (including weekly dependency/Action discovery), configuration preflight
and Pages publishing remain required. No release archive or package changes.

Program add-on retirement is deferred until the Development Video real-list/widget
journey is accepted on TV and its own-profile disconnect/recovery is covered. Keep
its completed device evidence, current download, shared implementation and local
disconnect access. No credentials are migrated or deleted by this cleanup. The next
owner action remains the [video checklist](development-video.md#smallest-tv-checklist).

## Current batch and next implementation boundary

PR #39 removed the redundant manual Development artifact workflow. Required
Validation, Security, configuration preflight and Pages publishing remain. The
program add-on and shared builder are retained until the video candidate has device
acceptance and sufficient own-profile disconnect/recovery coverage.

No additional feature code is required before the
[existing six-step video test](development-video.md#smallest-tv-checklist). A concrete
failure from that journey takes priority over broader integrations. If it passes,
the next bounded implementation is one agreed read-only progress row, preceded by
measurement of real widget loading. No completed program test must be repeated just
because this backlog was reconciled. No account details or private lists are needed
in a report; fixed outcomes, navigation observations and timings are sufficient.

## Change-aware CI batch

Implementation selects documentation link/render checks for allowlisted Markdown-only
changes while retaining stable required checks. Code, workflow, dependency and release
changes run full validation; scheduled/manual security scans remain full. Pages uses
the last successful publication as its test-selection baseline and always retains
archive/artifact/deployment verification. See [policy and limits](development.md#change-aware-checks).
No add-on or activation change and no new TV test are required for this batch.

## Source clarity and HomeFX icon candidate

The owner successfully selected/saved a real Development list and opened over 100
movies. Do not relabel this as widget, season, restart or performance acceptance.
The next source layout lists repository + Development Video only; advanced/ holds
manual Preview/program diagnostics. Existing release archives and root aliases are
preserved byte-for-byte, not deleted to shorten the picker.

Original house/TV artwork prepares video 0.17.9; repository 0.2.0 stays unchanged.
The icon is a 512×512 opaque RGB PNG with no third-party logo or new paid asset.
Normal post-merge publication and TV icon/folder navigation remain to be verified.
List loading/pagination is unchanged; measure first/warm loads before tuning it.

## Verified PR #42 and next metadata batch

PR #42 merged as `22b5f8ae87fcdab6bf1c6cdcc85d1e368b58495b`.
Validation, Security, configuration preflight and publication passed, including
[deployed-byte verification](https://github.com/susanto-dev/homefx/actions/runs/43552506209).
Fresh HTTP checks confirmed source/advanced folder access, indexed video 0.17.9 /
repository 0.2.0, and both current root ZIPs matching retained archive bytes.
The source layout and icon remain unverified on TV.

The next candidate adds existing Trakt synopsis/community-rating fields to selected
movie/show list cards and movie details, with no extra requests. Public Preview
remains synthetic; Development Video receives the behavior through its normal
content-addressed package. Artwork-provider registration/terms and Real-Debrid
activation remain separate gates; see [metadata provider decisions](metadata-contract.md#next-metadata-provider-decision).
No new login or repeat of completed lifecycle checks is required solely for this
metadata update. Saved-list restart/widget acceptance and timings remain pending.

## TMDB artwork preparation

The owner selected TMDB and requested bounded caching, but has not registered the
application or accepted its terms. The next candidate supplies an inactive fixed-host
client and private artwork-path cache, with seven-day freshness, one-day negative
cache, thirty-day hard expiry, 1,000-row / 1 MiB database bounds, request coordination
and fabricated workload measurements. Optional TMDB IDs are retained from selected
list metadata; there is no title guessing or additional list request.

See [implementation and remaining gates](tmdb-artwork.md). No current Kodi route
opens this cache or calls TMDB, and no remote image is displayed. Owner registration,
private credential delivery, required attribution, image/texture retention and
cancellable first-load UI remain the next bounded activation work. No further
provider-only infrastructure should be added as a substitute for those decisions.
Current saved-list/widget acceptance remains useful; no completed auth test must
be repeated for this inactive cache batch.

## Current direction: Trakt movie progress, no TMDB wait

The owner deferred TMDB/provider selection and requested the next workable item.
Retain Trakt synopsis/ratings, original placeholder artwork and the current skin.
The inactive TMDB foundation is preserved but no longer blocks other progress.
Real-Debrid still requires its registered device-flow and authorized source-input
checks. No demonstrated skin limitation justifies starting a new skin now.

The [movie-progress candidate](movie-progress.md) adds all/progress, unwatched,
released-unwatched, unfinished-released and upcoming movie views within each saved
list. These reuse existing complete history/paused joins and account-bound refs.
They are not the global Continue Watching feed, next episodes or a personal calendar.
Existing mixed-list/series widgets are unchanged. No playback, remote write or
provider activation is included. Next owner acceptance is one movie view and one
skin row using the existing Development account, not another login/storage test.

## Native Kodi identity candidate

The owner identified installed TMDb Helper 5.4.16. Its official archive was inspected
read-only; no source/assets or credentials were reused. The next candidate exposes
Trakt/TMDB IDs and parent-show identity using Kodi's standard metadata tags. It
adds no HomeFX network requests and does not enable the Helper service or replace
whole-row artwork. See [evidence and acceptance](kodi-metadata.md). Current Trakt
views remain usable, direct TMDB integration deferred, and Real-Debrid/skin work
subject to their existing gates. Helper/skin behavior and performance need TV evidence.

## Selected-show cross-season unwatched candidate

The Development context menu now offers aired, known-unwatched episodes across one
selected show's regular seasons. It reuses the bounded complete series join, keeps
unfinished-first/newest-air-date ordering and retains account/selection guards.
See [scope, request costs and TV acceptance](show-unwatched.md). This advances B03;
it does not complete global Continue Watching, narrative Next aired, playback or
skin-widget acceptance. No new account setup is required. Large-show load times
and the new context-menu path remain unverified on TV.

## Development package cleanup

Remove Preview-only catalogue/state/routes modules from Development ZIPs, retaining
their source, public Preview behavior, synthetic tests and published archives.
Both packages receive isolated complete-runtime import checks. This avoids shipping
unused demo behavior without deleting shared inactive integrations or retiring the
program test add-on before its existing gates. No runtime feature, public package
version, credential or skin change. TV speed benefits are not claimed.

## Current MVP batch: widget picker, local build information and skin guide

This batch joins three implementation tracks into one candidate and one reviewed
release. It keeps the current Python add-on and installed skin; it does not create
a skin or activate public service access.

| Work item | Current status | Evidence still needed |
|---|---|---|
| B02/T03: real personal/liked list selection and folder browsing | Published; owner-reported saved selection and 100+ movie browsing passed | Saved video selection after full restart and actual skin row |
| B02/B10: unified skin-selectable widget folders | Published in 0.17.15 with static menu and selected-list/show choices | Choose terminal folder with Use as widget on TV |
| B03: seasons and all-regular-season aired unwatched | Published; now reachable through published picker without context menus | Correct live statuses, Back and return position |
| T04: selected-list movie progress views | Published; picker reuses stable routes | Actual watched/paused endpoint and filtering on TV |
| Q04: Development build/device information | Published local-only source version/fingerprint and Kodi/skin report | Installed display; no storage/auth test implied |
| B10/Q04: exact-skin setup guide | Source-verified 3.0.3 navigation; published guide | Actual remote labels, focus, heading behavior |
| T07: cold/warm and multiple-row performance | Request limits and invocation cache implemented | TV timings; no speed or cross-row cache claim |
| R01–R03: installation/update | Public Preview repository and experimental Development ZIP paths published | Development remains deliberate ZIP update; not repository auto-update |
| T08: general public live access | Inactive, external approval/configuration gate | Owner/service requirements; do not infer from Development tests |
| B04/B11: episode progress | Per-show Continue Watching / narrative Next aired / Upcoming candidate; global feeds and personal calendar inactive | Per-show TV acceptance; separate global-feed integration |
| B05–B08/T06: remote list/history writes, live search/related UI | Demo/local or inactive contracts | Separate consent, service and UI gates |
| D01–D06/P01–P06: Real-Debrid, sources, playback and scrobbling | Inactive; no playable source catalogue assumed | Registration, authorized source decision, single-owner playback/device checks |
| Artwork | Trakt text/ratings and local placeholders; native Kodi IDs published | Skin/Helper behavior on TV; direct TMDB deferred |

The detailed tables above remain the complete backlog. No completed account test
must be repeated solely for this batch. Start with one selected list and one skin
row using the [MVP acceptance guide](widget-mvp.md), then measure a second row.
A successful synthetic test or source inspection is not a TV pass.

## Test maintenance batch

PR #49 merged as `1ddc26eb15c4ca0e08a94e401c748f17c1049fa4`; post-merge
Validation and publication passed. The publication verifier compared all 133 hosted
files with its uploaded artifact. Preview 0.17.15 and repository 0.2.0 are published;
this does not establish the outstanding widget TV checks above.

Published PR #50 separates shared widget stand-ins from test case modules,
removes redundant per-test verifier package builds using isolated copies, and supports
multiple focused discovery patterns without duplicate execution. Existing regression
cases remain; no obsolete boundary coverage was identified for deletion. Full-suite
and independent review gates remain required. No runtime, archive or version change
is needed; existing installations require no update solely for this cleanup.

## Selected-show progress batch and completion milestones

The [selected-show progress candidate](show-progress.md) adds three distinct terminal
widget folders to the existing show picker. It uses complete bounded series reads,
regular seasons only, and existing account/selection guards. No new endpoint, remote
write, provider, persistent cache or player activation is introduced. The older
all-episodes and aired-unwatched routes remain unchanged.

| Milestone | Status | Completion evidence / remaining work |
|---|---|---|
| Read-only Development library | Real list selection/save and browsing passed; season/progress implementation published or candidate | Season/progress correctness, selected video list after restart |
| Existing-skin widget MVP | Picker and guide published; three per-show progress folders candidate | One real row, remote focus/Back, restart, cold/warm and multiple-row times on TV |
| Usable personal playback add-on | Not complete; provider/player contracts inactive | Choose and verify authorized source path, provider login, real playback, subtitles, seek/resume, next episode and scrobbling ownership |
| Public live release | Not complete; public Preview still synthetic | Service/public registration gates, repository delivery of live build, tested updates and release acceptance |

There is no meaningful percentage complete: synthetic contracts are not device
acceptance or playable source integration. Finish the read-only widget milestone
before claiming the personal playback milestone. Related/search and remote watched
correction remain separate backlog items; artwork provider selection is deferred.
Current authentication evidence is retained and does not need repeating solely for
this batch. No replacement skin is planned.

## Account-wide Continue Watching candidate

[Account-wide Continue Watching](continue-widget.md) adds a single mixed movie/episode
widget independent of saved lists. Its source chooser reads account identity only;
opening the terminal feed explicitly uses the existing bounded paused/detail/watched
join. Known watched entries are excluded, unknown episode watched status is preserved,
and incomplete or failed reads never become an empty successful feed. Details
revalidate current membership. Opaque references use the existing private key and
clear epoch, with no schema migration or saved history.

| Work item | Status | Remaining acceptance |
|---|---|---|
| Account-wide Continue Watching | Candidate implemented across reference, library and UI layers | Real mixed-feed correctness, details/Back, restart and load times |
| Per-show Continue / Next / Upcoming | Published in 0.17.16 | Existing TV checklist, no repeat login |
| Global Next aired / personal calendar | Inactive | Separate bounded integration; calendar is not a complete selected-list schedule |
| Playback and public live release | Inactive | Source/provider decisions, device playback/state checks and public service gates |

This advances the read-only widget milestone. It does not complete a playable video
add-on. No new provider registration, credentials, remote writes or skin change is
needed for the candidate. Current account tests remain valid.
