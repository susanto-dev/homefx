# HomeFX

A personal Kodi video add-on project, targeting Kodi 21.2 and the existing
Arctic Zephyr Reloaded 3.0.3 Vertical Multi-Widget Netflix layout.

## Current preview: 0.1.0

**Synthetic data only. No account login, network calls, source resolution, or playback.**
The preview supplies three selectable demo lists, a series episode browser,
continue-watching, next aired unwatched episodes, and a seven-day upcoming view.
Movie context menus offer related demo movies and editable title search. Watch-state
changes are local demonstration overrides, never Trakt updates. A separate episode
context action previews the next-episode choice without starting media.

Movies/episodes open an explanatory dialog when selected. Shows open their episodes.
Original geometric placeholder artwork is included; no third-party skin or artwork
is bundled. The current skin stays installed separately.

## Build and try

```sh
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
- [Architecture](docs/architecture.md), [decisions](docs/decisions.md), [backlog](docs/backlog.md)
- [Security reporting](SECURITY.md) and [security design](docs/security.md)
- [Packaging and future releases](docs/releases.md)

Original code currently carries the existing MIT licence. The owner's final licence
preference remains pending. No third-party code reuse is authorized by that licence.
NBA and a separate Android application are outside scope.
