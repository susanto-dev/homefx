# Complete project backlog

Status at the 0.10 development batch (video add-on 0.10.0, repository add-on 0.2.0). **Implemented** means source and automated
checks exist; it never means tested on the TV or against a real account.
**Mocked/inactive** means service/player code is not wired into Kodi. **Pending**
means work or external evidence is still required. **Decision** needs a product,
provider or release choice. The current public add-on remains synthetic.

## Browsing and personal library

| ID | Item | Status | Remaining work / acceptance |
|---|---|---|---|
| B01 | Single repository, video add-on, Kodi 21 Python manifest | Implemented | Actual Android/Google TV compatibility pending |
| B02 | Multiple selected list widgets and folder browsing | Implemented in demo | Choose actual personal/liked lists; live wiring and widget-title click behavior need TV verification |
| B03 | Episode/season browser, watched counts, aired-unwatched filter | Implemented in demo; complete-series/season summaries mocked (0.10) | Live episode identity/status and refresh behavior |
| B04 | Continue watching, unfinished first, next aired unwatched | Implemented in demo; bounded series joins and continuation candidates mocked (0.10) | Live metadata, resume reconciliation and performance |
| B05 | Save movies including unreleased titles, upcoming view | Implemented locally; Trakt list-add mocked | Live owned-list selection/write outcomes; regional release semantics |
| B06 | Manual mark watched | Implemented locally; remote add-history mocked | Explicit live writes and uncertain-result reconciliation; remote unwatched/history deletion needs separate semantics |
| B07 | Title search | Demo implemented; Trakt title-search contracts mocked/inactive (0.9) | Live literal-query behavior, entitlement, keyboard/context-menu UI and TV integration |
| B08 | Similar movies | Demo implemented; Trakt related-movie contracts mocked/inactive (0.9) | Live relevance and UI integration; results establish neither watch state nor playable sources |
| B09 | Release dates and sorting | Provisional rules implemented | Choose movie region/release type and confirm ordering; dates never prove source availability |
| B10 | Skin and home layout | Existing skin retained | TV navigation/focus/widget headers; separate skin only if demonstrated necessary |

## Trakt and account data

| ID | Item | Status | Remaining work / acceptance |
|---|---|---|---|
| T01 | Device login, refresh, protected token store, HTTPS/session guards | Mocked/inactive | Application registration, public ID/redirect URI, actual login/refresh and TV storage/TLS verification |
| T02 | Account connect/cancel/switch/disconnect UI | Controller mocked; setup guidance implemented | Wire UI only after activation gates; verify revocation/privacy wording and recovery on TV |
| T03 | Personal/liked lists and saved account-bound selections | Mocked/inactive | Choose real lists and verify live account isolation, paging and restart behavior |
| T04 | Complete movie watched snapshot and filtered joins | Mocked/inactive (0.8) | Bounded full snapshot; no missing-response-to-unwatched fallback; live validation still pending |
| T05 | Live Trakt read views | Pending | Enable after registration, transport and device checks |
| T06 | Live history/list actions | Pending | Separate consent/outcome checks after reads; no automatic write retries |
| T07 | Persistent metadata cache, shared rate limiting and performance | Invocation-memory cache implemented; shared request limits implemented/inactive (0.9); persistent cache decision pending | Validate shared limits on TV; decide retention/invalidation and measure TV load times before live wiring |
| T08 | Wider public Trakt application access | Pending external approval | Service registration/Production requirements and current terms review |

## Real-Debrid

| ID | Item | Status | Remaining work / acceptance |
|---|---|---|---|
| D01 | Open-source device authorization and refresh contracts | Mocked/inactive | Register application; verify exact pending-authorization response on device; no bundled shared secret |
| D02 | Account/download/link-resolution contracts | Mocked/inactive | Validate service responses/entitlement with own account on TV; no title catalogue or discovery claim |
| D03 | Separate private credential store and durable refresh claims | Mocked/inactive (0.8) | Private SQLite and account-generation tests; actual Android permissions and recovery pending |
| D04 | Fixed-host bounded HTTPS/form transport | Mocked/inactive (0.8) | Injected connection tests; actual TLS/DNS/cancellation behavior pending |
| D05 | Session/login/refresh/read/resolve coordination | Mocked/inactive (0.8) | Joined store/transport tests and stale-response rejection; live activation pending |
| D06 | Real account UI and activation | Pending | Wire only after D01–D05 validation; cross-device quota coordination and disconnect/revocation UX remain |

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
| R01 | Reproducible manual ZIP and public Pages preview | Implemented; 0.9 publication and HTTP integrity verified | 0.10 publication follows merge; cloud checks do not prove TV installation |
| R02 | Repository package/index/checksums, retained packages and verifier | Implemented; experimental repository channel published (0.9) | 0.9 deployed-byte verification passed; clean repository-first install still needs TV evidence |
| R03 | Repository hosting, upgrades and rollback | Experimental Pages channel and immutable release history implemented; HTTP verification passed; TV acceptance pending | Verify each new publication; test clean install/upgrade and documented rollback on TV |
| Q01 | Python 3.8/3.12, manifests/XML, packaging/repeatability checks | Implemented | Continue regression coverage; cloud tests never replace TV tests |
| Q02 | Weekly security/dependency/Action update checks and SHA pins | Implemented | Manual issue triage; no automatic update PRs or PR comments |
| Q03 | Full Kodi add-on checker, pinned linter, package hash lock | Pinned Ruff correctness gate and dependency hash locks implemented (0.9); official checker pending | Full checker blocked on reviewed secure/offline input and compatible repository schema; diagnostic schema checks are not a full pass |
| Q04 | Device readiness and sanitized test checklist | Implemented; repository-version diagnostics and widget setup added (0.10); TV results pending | Provide safe version fields and observations; no full backup or secrets needed |
| G01 | Original-code licence | Decision | Existing MIT remains; final owner preference still unconfirmed |
| G02 | Third-party source/assets and service compliance | Ongoing gate | Verify exact licence/compatibility before reuse; no upstream source/assets copied |
| G03 | Public repository neutrality and secret hygiene | Implemented practice | Keep credentials/private watch data out of source, artifacts, logs and public discussion |

## Current combined batch: 0.10

Parallel scope: complete-series Trakt metadata and watched-state views, bounded
playback event observation without scrobbling or automatic playback, and on-device
widget/repository setup guidance. These foundations remain inactive for real accounts;
the Kodi preview continues using synthetic browsing data.

The 0.9 release and repository 0.2.0 deployed successfully at merge commit
`5a53a26ffec91178d491c5f27b1b354459755ae5`. The
[publication run](https://github.com/susanto-dev/homefx/actions/runs/43336830315)
passed build, deployment and comparison of public bytes against the uploaded artifact.
That is HTTP distribution evidence, not a Kodi installation or upgrade test.
This batch prepares video 0.10.0 for the same experimental channel, retaining previous
archives. The repository bootstrap version remains 0.2.0.

## External inputs and decisions

The next useful device evidence is the readiness report and existing widget/navigation
checklist, followed by service-registration details (public IDs only). Real lists/views,
movie release region/type, first playback path, source-provider choice, scrobbling
ownership, final original-code licence and TV acceptance of repository updates/rollback remain open.
These inputs do not block the current mocked foundation work. Never send secrets,
account exports, watch history or a full Kodi backup.

NBA, a separate Android app and an always-on server are outside scope. A new skin is
a conditional future option, not a required component. See [playback plan](playback-plan.md),
[account gates](account-setup.md), [handoff evidence](umbrella-feasibility.md),
[metadata contracts](metadata-contract.md) and [TV checklist](testing-on-tv.md).
