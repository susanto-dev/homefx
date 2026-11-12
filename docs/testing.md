# Testing

Run `python3 -m unittest discover -s tests -v` from the repository root.
Tests cover explicit synthetic expected orders/dates, episode identity, calendar
boundaries, watch-state overrides, search, related-title order, continuation choices,
URL encoding and malformed routes, local state recovery, reproducible ZIP bytes,
private-file exclusion, and rejection of deliberately broken manifests/files.

Expected values are independently specified. Keep the injected date fixed in logic
tests. Error and empty paths matter as much as happy paths. A package allowlist
prevents accidental inclusion of extra files but cannot detect a secret pasted into
an allowed source file; source review and future secret scanning remain necessary.

Kodi adapter tests use narrow stand-ins to verify route wiring, metadata and menu
construction. They do not establish actual Kodi API compatibility or rendering.
Cloud checks do not establish installation, home-widget behavior, navigation,
performance, playback, subtitles, resume, or scrobbling on Android/Google TV.
Record those separately with exact versions and the package hash.

Action audit tests require the optional security tool environment. They deliberately
reject floating tags, short/dynamic refs and nested unpinned Actions; mocked release
responses exercise annotated-tag resolution and update reporting. The security job
runs these tests explicitly. Plain standard-library runs skip this optional suite.
