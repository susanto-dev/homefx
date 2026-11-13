# HomeFX

A personal Kodi video add-on project targeting Kodi 21.2, with configurable
home-screen widgets and standard folder browsing. The Python target follows the
official Kodi 21.2 Android build (Python 3.11); development checks also cover 3.12.

## Install on Android or Google TV

Start with the [step-by-step installation and first-use guide](docs/install.md),
or use the [phone-friendly guide on GitHub Pages](https://susanto-dev.github.io/homefx/install.html).
It covers repository-first installation, a full Kodi restart, safe readiness/storage
checks and demo widget setup with your existing skin. Updates to the Pages guide are published by the normal checked deployment after
changes merge to main.

For the next device and account checkpoint, use the
[activation handoff checklist](docs/activation-checklist.md). It separates safe demo
observations from the gates required before any live connection.

For the separately installed test add-on and its HomeFX source installation steps, see the
[bounded Development device test](docs/development-device-test.md). It does not
activate live routes in HomeFX Preview or join the public repository channel.

## Published preview: 0.17.6

HomeFX Preview 0.17.6 and repository 0.2.0 are published. PR #34 post-merge
validation, security, publication and deployed-byte checks passed. The owner has
reported passing private storage checks, **Connection test: authorized** and
**Refresh rotation: passed** in the separate Development program add-on on TV.
No list or history request was made by that refresh test.

These are real device observations, not cloud test results. The owner also confirmed restart persistence, cancellation/disconnect and responsive
offline failure followed by code issuance after networking recovered. Live list/widget
acceptance remains unverified; offline wait duration was not measured. The
public video preview still uses demo data and does not inherit the test's tokens.
See [what to do after successful login](docs/development-device-test.md#after-successful-authorization-and-refresh)
and [why the test is separate](docs/development-device-test.md#why-a-program-add-on).

The **0.17.7 candidate** joins shared login, selection and directory components in
one [video dispatcher](docs/video-integration.md). Public live routes remain inactive;
no program credentials are migrated. Automated crash/reopen recovery tests use
synthetic tokens, not a destructive real-account experiment.

**Synthetic data only. No account login, network calls, source resolution, or playback.**
The preview supplies four selectable demo lists, a series episode browser,
continue-watching, next aired unwatched episodes, and a seven-day upcoming view.
Widget sources groups the content folders for skin configuration. List context menus
filter all, unwatched, released unwatched or upcoming titles. Series context menus
open season folders with watched and aired-unwatched counts. Upcoming saved movies
have their own folder; release dates do not establish playable availability.
Movie context menus offer related demo movies, editable title search, and add/remove
actions for My movie list—including upcoming movies. Episode menus offer all
episodes or aired unwatched episodes in narrative order. Watch-state
changes are local demonstration overrides, never Trakt updates. A separate episode
context action previews the next-episode choice without starting media.

Movies/episodes open an explanatory dialog when selected. Shows open their episodes.
Version 0.17.4 contains inactive Trakt authentication, token-storage, HTTPS transport,
account/session coordination, a cancellable account-flow controller, saved account-list
preferences and explicit action contracts tested with fabricated responses. These are not connected to the
Kodi account actions and do not enable real accounts. The connection-setup menu is
information only. Playback and Real-Debrid setup explains the remaining source/account
gates. Inactive Real-Debrid and playback modules use injected callbacks in tests; no
provider transport, credentials or player is connected to the preview. The provider foundation
adds a separate private provider store, bounded HTTPS/session coordination, and complete
movie watched-state joins, exercised with fabricated responses. Device readiness displays bounded local runtime capabilities
without reading account profiles or making network requests. The 0.9 preview adds inactive title-search and similar-movie contracts.
An experimental Kodi repository supplies installation and updates after the reviewed
Pages deployment; retained packages are checksum-pinned and immutable. HTTP integrity
and device acceptance are separate checks. Existing profiles keep their selected lists;
open My movie list from a movie context menu or enable it in list selection.

Original geometric placeholder artwork is included; no third-party skin or artwork
is bundled. The current skin stays installed separately.

## Build and try

```sh
python3 -m pip install --require-hashes -r tools/build-requirements.txt
python3 -m unittest discover -s tests -v
python3 tools/package.py
```

The ZIP and SHA-256 sidecar appear in `dist/`.
The experimental preview page is https://susanto-dev.github.io/homefx/. After the
reviewed deployment, add that URL in Kodi File manager, install
`repository.homefx-0.2.0.zip`, then choose **Install from repository → HomeFX Preview
Repository → Video add-ons → HomeFX Preview**. A manual video ZIP remains available.
See [TV testing](docs/testing-on-tv.md) for installation and widget checks.
Repository installation and upgrades on the TV are not yet verified.

## Development

- [Contributing and review](CONTRIBUTING.md)
- [Development](docs/development.md) and [testing](docs/testing.md)
- [Account setup and activation gates](docs/account-setup.md)
- [Trakt authentication contracts](docs/trakt-authentication.md)
- [Real-Debrid and playback plan](docs/playback-plan.md)
- [Architecture](docs/architecture.md), [decisions](docs/decisions.md), [backlog](docs/backlog.md)
- [Security reporting](SECURITY.md) and [weekly scanning / manual triage](docs/security.md)
- [Packaging and preview releases](docs/releases.md)

Original code currently carries the existing MIT licence. The owner's final licence
preference remains pending. No third-party code reuse is authorized by that licence.
NBA and a separate Android application are outside scope.


The 0.10 preview adds **Widget setup** guidance and the installed HomeFX repository
version to **Device readiness**. See [widget setup](docs/widget-setup.md). Complete-series
Trakt views and playback event observation are inactive foundations tested with
fabricated responses, not live account or player features.


The 0.11 foundations add bounded enrichment for resume entries that lack release
metadata, plus upcoming episodes from Trakt's personal calendar. A show filter narrows
that calendar; it does not guarantee a complete schedule for arbitrary selected lists.
These contracts remain inactive for real accounts. See the [backlog](docs/backlog.md)
for remaining activation, provider, playback and TV acceptance work.


The 0.12 foundations assemble the Trakt and Real-Debrid components with shared request
limits and add a reusable device-login dialog adapter. They remain inactive: the
preview still shows synthetic data and does not offer live account connection or
playback. Device registration, private storage, authorization and cancellation need
actual TV validation before activation.


For the next device check, run **Test private storage** from the HomeFX root. It uses
synthetic temporary SQLite data after confirmation and reports private-file and
cleanup results without exposing account data. See the [TV checklist](docs/testing-on-tv.md).
This check does not connect accounts or prove live token storage/recovery.

The 0.13 preview hardens saved demo state and the inactive Trakt stores. Valid
existing credentials and list selections remain compatible; malformed private
stores are not silently reset. See [storage boundaries](docs/storage-boundaries.md).

The 0.14 preview extends storage checks to the inactive Real-Debrid credential
store and shared request limits. Refresh expiry is checked after acquiring the
database write lock; missing stores are not recreated during later operations.
Live account and playback activation gates remain unchanged.
