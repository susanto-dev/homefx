# Complete project backlog

Status checked on 14 November 2026: published **video 0.17.8 / repository 0.2.0**.
PR #39 is merged as `238bc3b86888d21e2dd688257196fbced8bf49f9`; its post-merge
validation, Security, CodeQL, Development preflight and
[publication / hosted-byte verification](https://github.com/susanto-dev/homefx/actions/runs/43545085858)
passed. Fresh hosted index/package checks matched video 0.17.8, repository 0.2.0
and both Development downloads. No version or archive bytes changed. **Implemented** means source and automated checks exist; **published** means
release bytes are hosted. Neither means tested on the TV or against a real account.
**Mocked/inactive** means service/player code is not wired into Kodi. **Pending**
means work or external evidence is still required. **Decision** needs a product,
provider or release choice. The current public add-on remains synthetic.

## Browsing and personal library

| ID | Item | Status | Remaining work / acceptance |
|---|---|---|---|
| B01 | Single repository, video add-on, Kodi 21 Python manifest | Implemented; TV reports Kodi 21.2 / Python 3.11.7 | 0.17.4 synthetic storage passed; broader device acceptance remains pending |
| B02 | Multiple selected list widgets and folder browsing | Published in Development Video; public Preview remains demo-only | One real list, separate skin-row assignment, widget heading/full-list access and restart acceptance on TV |
| B03 | Episode/season browser, watched counts, aired-unwatched filter | Published Development read-only browser; synthetic integration tests passed | Live episode identity/status, season navigation and refresh behavior on TV |
| B04 | Continue watching, unfinished first, next aired unwatched | Implemented in demo; bounded series joins, continuation candidates and enriched paused metadata mocked (0.11) | Live metadata, resume reconciliation and performance |
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
| T01 | Device login, refresh, protected token store, HTTPS/session guards | Shared implementation; program lifecycle passed on TV; Development identity/redirect owner-confirmed | Fresh video-profile login/storage acceptance; denial/expiry and interrupted refresh use automated evidence, with live outcomes unclaimed. Do not repeat completed program checks |
| T02 | Account connect/cancel/switch/disconnect UI | Shared UI and Development video entry published | Program consent/cancellation/restart/disconnect passed; video-profile UI/account switching and service-side revocation remain separate acceptance |
| T03 | Personal/liked lists and saved account-bound selections | Published in Development Video; synthetic end-to-end acceptance passed | Owner privately chooses one real list; verify paging, widget and saved selection after restart on TV |
| T04 | Complete movie watched snapshot and filtered joins | Mocked/inactive (0.8) | Bounded full snapshot; no missing-response-to-unwatched fallback; live validation still pending |
| T05 | Live Trakt read views | Read-only selected-list Development candidate published; public/Production inactive | Validate candidate on TV; Continue Watching, Next aired and Upcoming need separate future integration |
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
| R01 | Reproducible manual ZIP and public Pages preview | Published 0.17.8; Development video/program downloads byte-verified | Development video TV acceptance pending |
| R02 | Repository package/index/checksums, retained packages and verifier | Implemented; experimental repository channel published (0.9) | 0.17.8 deployed-byte verification passed; clean repository-first install still needs TV evidence |
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
| One real personal/liked list, seasons, saved selection after restart | Synthetic end-to-end tests; pending owner video-candidate acceptance |
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
