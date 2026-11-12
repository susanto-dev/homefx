# HomeFX

A personal Kodi video add-on project targeting Kodi 21.2, with configurable
home-screen widgets and standard folder browsing.

## Current preview: 0.4.0

**Synthetic data only. No account login, network calls, source resolution, or playback.**
The preview supplies four selectable demo lists, a series episode browser,
continue-watching, next aired unwatched episodes, and a seven-day upcoming view.
Movie context menus offer related demo movies, editable title search, and add/remove
actions for My movie list—including upcoming movies. Episode menus offer all
episodes or aired unwatched episodes in narrative order. Watch-state
changes are local demonstration overrides, never Trakt updates. A separate episode
context action previews the next-episode choice without starting media.

Movies/episodes open an explanatory dialog when selected. Shows open their episodes.
Version 0.4.0 contains inactive Trakt authentication, token-storage, HTTPS transport,
account/session coordination, saved account-list preferences and explicit action
contracts tested with fabricated responses. These are not connected to the
Kodi account actions and do not enable real accounts. The connection-setup menu is
information only. A local Kodi repository generator produces review artifacts; it
supports checksum-pinned retention of older reviewed packages but does not activate
a public installation/update channel. Existing profiles keep their selected lists;
open My movie list from a movie context menu or enable it in list selection.

Original geometric placeholder artwork is included; no third-party skin or artwork
is bundled. The current skin stays installed separately.

## Build and try

```sh
python3 -m pip install -r tools/build-requirements.txt
python3 -m unittest discover -s tests -v
python3 tools/package.py
```

The ZIP and SHA-256 sidecar appear in `dist/`.
The public preview download page is https://susanto-dev.github.io/homefx/. Install the ZIP manually through
Kodi's add-on browser. See [TV testing](docs/testing-on-tv.md) for the safe preview
procedure and widget setup. No hosted repository or automatic update channel exists yet.

## Development

- [Contributing and review](CONTRIBUTING.md)
- [Development](docs/development.md) and [testing](docs/testing.md)
- [Account setup and activation gates](docs/account-setup.md)
- [Trakt authentication contracts](docs/trakt-authentication.md)
- [Architecture](docs/architecture.md), [decisions](docs/decisions.md), [backlog](docs/backlog.md)
- [Security reporting](SECURITY.md) and [weekly scanning / manual triage](docs/security.md)
- [Packaging and future releases](docs/releases.md)

Original code currently carries the existing MIT licence. The owner's final licence
preference remains pending. No third-party code reuse is authorized by that licence.
NBA and a separate Android application are outside scope.
