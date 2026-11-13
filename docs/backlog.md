# Complete project backlog

Status checked on 13 November 2026: published **video 0.17.4 / repository 0.2.0**.
The installation guide is merged in PR #27; its post-merge publication workflow
passed. **Implemented** means source and automated checks exist; **published** means
release bytes are hosted. Neither means tested on the TV or against a real account.
**Mocked/inactive** means service/player code is not wired into Kodi. **Pending**
means work or external evidence is still required. **Decision** needs a product,
provider or release choice. The current public add-on remains synthetic.

## Browsing and personal library

| ID | Item | Status | Remaining work / acceptance |
|---|---|---|---|
| B01 | Single repository, video add-on, Kodi 21 Python manifest | Implemented; TV reports Kodi 21.2 / Python 3.11.7 | 0.17.4 synthetic storage passed; broader device acceptance remains pending |
| B02 | Multiple selected list widgets and folder browsing | Implemented in demo; mixed-list reads and inactive account-bound widget rendering added (0.16) | Gated public dispatch, activation and widget-title click behavior need TV verification |
| B03 | Episode/season browser, watched counts, aired-unwatched filter | Implemented in demo; inactive opaque episode filters and season/progress display added (0.17) | Live episode identity/status and refresh behavior |
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
| T01 | Device login, refresh, protected token store, HTTPS/session guards | Mocked/inactive; storage hardened (0.13) | Owner confirms registered Development ID/redirect match GitHub variables; 0.17.4 synthetic storage passed; separate Development device test prepared, actual login/refresh/persistence/TLS acceptance pending |
| T02 | Account connect/cancel/switch/disconnect UI | Controller/dialog adapter implemented; separate explicit Development test prepared | Public preview UI stays inactive; test consent, cancellation, restart, disconnect/revocation and recovery on TV |
| T03 | Personal/liked lists and saved account-bound selections | Mocked/inactive; guarded chooser and persistent account-bound widget references added (0.16) | Choose lists privately after activation; verify live account isolation, paging and restart behavior |
| T04 | Complete movie watched snapshot and filtered joins | Mocked/inactive (0.8) | Bounded full snapshot; no missing-response-to-unwatched fallback; live validation still pending |
| T05 | Live Trakt read views | Pending | Enable after registration, transport and device checks |
| T06 | Live history/list actions | Pending | Separate consent/outcome checks after reads; no automatic write retries |
| T07 | Persistent metadata cache, shared rate limiting and performance | Invocation-memory cache implemented; shared request limits implemented/inactive (0.9), persistence guards hardened (0.14); persistent cache decision pending | Validate shared limits on TV; decide retention/invalidation and measure TV load times before live wiring |
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
| R01 | Reproducible manual ZIP and public Pages preview | Implemented; 0.17.4 publication and HTTP integrity verified | TV acceptance pending |
| R02 | Repository package/index/checksums, retained packages and verifier | Implemented; experimental repository channel published (0.9) | 0.17.4 deployed-byte verification passed; clean repository-first install still needs TV evidence |
| R03 | Repository hosting, upgrades and rollback | Experimental Pages channel, immutable history and local release preparation implemented; HTTP verification passed; TV acceptance pending | Verify each new publication; test clean install/upgrade and documented rollback on TV |
| Q01 | Python 3.11/3.12, manifests/XML, packaging/repeatability checks | Implemented; aggregate results, boundary regressions and whole-journey integration coverage | Continue regression coverage; cloud tests never replace TV tests |
| Q02 | Weekly security/dependency/Action update checks and SHA pins | Implemented; GitHub graph verified and offline inventory consistency guard added | Manual issue triage; no automatic update PRs or PR comments |
| Q03 | Full Kodi add-on checker, pinned linter, package hash lock | Pinned Ruff correctness gate and dependency hash locks implemented (0.9); source manifest contracts strengthened; official checker pending | Full checker blocked on reviewed secure/offline input and compatible repository schema; diagnostic schema checks are not a full pass |
| Q04 | Device readiness and sanitized test checklist | Implemented; 0.17.4 synthetic storage passed on TV | Actual test-addon account-store persistence, TLS and live authorization remain separate checks |
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

## Next checkpoint: bounded Development account test

Video 0.17.4 and repository 0.2.0 are the published preview. Start with the
[activation handoff checklist](activation-checklist.md), which separates demo TV
evidence from the later, explicitly authorized Development account test.
Keep the existing functionality and skin. Prioritize selected-list widgets, distinct
progress/next/upcoming views, remote navigation and repository-first installation.
Do not add options or integrations for feature parity, or claim a smaller scope
improves performance without measurements. No additional demo feature is needed
before the [bounded TV checklist](testing-on-tv.md).

| Priority | Backlog scope | Current status / next acceptance |
|---|---|---|
| 1 | R01–R03, Q04, B10 | 0.17.4 synthetic storage passed; installation/update path, navigation and restart acceptance remain open |
| 2 | B02, T07 | Measure one-row and multi-row first-open/reopen timings on TV; synthetic timings do not prove live network/cache performance |
| 3 | T01–T03, T05 | Owner confirms Development identity/redirect match; separate manually built device test prepared; real TLS, grant, restart persistence and refresh still unverified; Production not run |
| 4 | B02–B04, T03, T05 | Then validate one real personal or liked list, separate skin row assignment, details and restart persistence; inactive rendering is not tested by public demo routes |
| Ongoing | Q01–Q02, R01–R03 | Preserve automated checks, independent review and immutable publication |
| Later | Q03 | Official checker secure/offline input and schema compatibility remain unresolved |
| Deferred | T06, D01–D06, P01–P06 | Remote writes, Real-Debrid and playback; no expansion in this checkpoint |

Device and registration gates cannot be satisfied by cloud tests. Protected main
remains maintainer-merged after independent review and successful checks.

## External inputs and decisions

The next useful device evidence is the bounded Development login/refresh test,
plus the existing widget/navigation checklist. Registered Development values are
owner-confirmed; no app values need to be posted. Real lists/views,
movie release region/type, first playback path, source-provider choice, scrobbling
ownership, final original-code licence and TV acceptance of repository updates/rollback remain open.
Actual authentication and read-only device evidence still block public live activation. Playback, movie-region and licence decisions do not require another demo-feature batch; completed independent work does not satisfy the activation gates. Never send secrets,
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

## Prepared: isolated Development device-test artifact

The owner confirmed the registered Development ID and redirect match GitHub variables.
A separate **HomeFX Development Test** program add-on is prepared for explicit
storage, local status, device authorization, one refresh rotation and disconnect
checks. Its manually requested main-only workflow embeds public configuration in a
content-addressed artifact; it does not publish a Kodi repository package or activate
HomeFX Preview. See the [bounded test instructions](development-device-test.md).

The test uses its own profile, scoped by public app identity. Tokens never enter CI,
artifacts, logs or public reports. No list/account API reads, remote history/list
writes, playback, Real-Debrid or scrobbling are enabled. A reviewed implementation
and fabricated tests are not real login, TLS, refresh or TV evidence. After those
results, plan the smallest real read-only list/widget integration; do not add more
demo-only features to substitute for that acceptance.
