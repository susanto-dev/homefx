# Complete project backlog

Status at the 0.8 development batch. **Implemented** means source and automated
checks exist; it never means tested on the TV or against a real account.
**Mocked/inactive** means service/player code is not wired into Kodi. **Pending**
means work or external evidence is still required. **Decision** needs a product,
provider or release choice. The current public add-on remains synthetic.

## Browsing and personal library

| ID | Item | Status | Remaining work / acceptance |
|---|---|---|---|
| B01 | Single repository, video add-on, Kodi 21 Python manifest | Implemented | Actual Android/Google TV compatibility pending |
| B02 | Multiple selected list widgets and folder browsing | Implemented in demo | Choose actual personal/liked lists; live wiring and widget-title click behavior need TV verification |
| B03 | Episode/season browser, watched counts, aired-unwatched filter | Implemented in demo; Trakt views mocked | Live episode identity/status and refresh behavior |
| B04 | Continue watching, unfinished first, next aired unwatched | Implemented in demo; Trakt joins mocked | Complete live metadata, resume reconciliation and performance |
| B05 | Save movies including unreleased titles, upcoming view | Implemented locally; Trakt list-add mocked | Live owned-list selection/write outcomes; regional release semantics |
| B06 | Manual mark watched | Implemented locally; remote add-history mocked | Explicit live writes and uncertain-result reconciliation; remote unwatched/history deletion needs separate semantics |
| B07 | Title search | Demo implemented | Real metadata search provider, terms and integration |
| B08 | Similar movies | Fictional demo only | Recommendation provider and relevance behavior decision |
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
| T07 | Persistent metadata cache, shared rate limiting and performance | Pending | Invocation-memory cache exists; choose retention/invalidation, cross-invocation quotas and measure TV load times |
| T08 | Wider public Trakt application access | Pending external approval | Service registration/Production requirements and current terms review |

## Real-Debrid

| ID | Item | Status | Remaining work / acceptance |
|---|---|---|---|
| D01 | Open-source device authorization and refresh contracts | Mocked/inactive | Register application; verify exact pending-authorization response on device; no bundled shared secret |
| D02 | Account/download/link-resolution contracts | Mocked/inactive | Validate service responses/entitlement with own account on TV; no title catalogue or discovery claim |
| D03 | Separate private credential store and durable refresh claims | Mocked/inactive (0.8) | Private SQLite and account-generation tests; actual Android permissions and recovery pending |
| D04 | Fixed-host bounded HTTPS/form transport | Mocked/inactive (0.8) | Injected connection tests; actual TLS/DNS/cancellation behavior pending |
| D05 | Session/login/refresh/read/resolve coordination | Mocked/inactive (0.8) | Joined store/transport tests and stale-response rejection; live activation pending |
| D06 | Real account UI and activation | Pending | Wire only after D01–D05 validation; shared quota policy and disconnect/revocation UX remain |

## Sources and playback

| ID | Item | Status | Remaining work / acceptance |
|---|---|---|---|
| P01 | Authorized source input/discovery | Decision | Choose explicit supplied links and/or a reviewed source provider; metadata cannot substitute for sources |
| P02 | Umbrella handoff experiment | Unverified | Installed interface/version and exact licence review, then movie/episode device tests |
| P03 | Native playback coordination | Mocked/inactive | Single-attempt coordinator exists; real Kodi adapter and dispatch/account ownership remain |
| P04 | Playback, subtitles, seek/resume, cancellation/errors | Pending TV validation | Validate actual AV start and end-to-end behavior with authorized media |
| P05 | Resume and Trakt scrobbling ownership | Decision / pending | Exactly one owner; start/pause/stop/completion and manual correction tests |
| P06 | Next aired episode / offer next aired unwatched | Demo choice implemented | Actual end-of-playback sequencing, watched reconciliation and cancellation |

## Distribution, quality and governance

| ID | Item | Status | Remaining work / acceptance |
|---|---|---|---|
| R01 | Reproducible manual ZIP and public Pages preview | Implemented | Each merge publishes synthetic preview; not a device-installation pass |
| R02 | Repository package/index/checksums, retained packages and verifier | Implemented locally | No operational update endpoint; retained artifacts still require source review |
| R03 | Repository hosting, upgrades and rollback | Decision / pending | Choose retention/rollback policy, test clean install/upgrade on TV, then activate channel separately |
| Q01 | Python 3.8/3.12, manifests/XML, packaging/repeatability checks | Implemented | Continue regression coverage; cloud tests never replace TV tests |
| Q02 | Weekly security/dependency/Action update checks and SHA pins | Implemented | Manual issue triage; no automatic update PRs or PR comments |
| Q03 | Full Kodi add-on checker, pinned linter, package hash lock | Pending | Review tooling/dependencies/licences and add proportionate checks |
| Q04 | Device readiness and sanitized test checklist | Implemented; TV results pending | Provide safe version fields and observations; no full backup or secrets needed |
| G01 | Original-code licence | Decision | Existing MIT remains; final owner preference still unconfirmed |
| G02 | Third-party source/assets and service compliance | Ongoing gate | Verify exact licence/compatibility before reuse; no upstream source/assets copied |
| G03 | Public repository neutrality and secret hygiene | Implemented practice | Keep credentials/private watch data out of source, artifacts, logs and public discussion |

## Current combined batch: 0.8

Parallel scope: D03 private storage, D04 transport, D05 session coordination and T04
movie watched snapshots, plus integrated regression tests and this complete backlog.
No live route, source provider, player, scrobbler, new paid service or repository
hosting activation is included. The maintainer merges after independent review and
passing final-head checks; that merge publishes only the synthetic manual preview.

## External inputs and decisions

The next useful device evidence is the readiness report and existing widget/navigation
checklist, followed by service-registration details (public IDs only). Real lists/views,
movie release region/type, first playback path, source-provider choice, scrobbling
ownership, final original-code licence and repository retention policy remain open.
These inputs do not block the current mocked foundation work. Never send secrets,
account exports, watch history or a full Kodi backup.

NBA, a separate Android app and an always-on server are outside scope. A new skin is
a conditional future option, not a required component. See [playback plan](playback-plan.md),
[account gates](account-setup.md) and [TV checklist](testing-on-tv.md).
