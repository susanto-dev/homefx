# Architecture

One source repository, with separate add-on directories as components are needed.
plugin.video.homefx supplies the synthetic preview. repository.homefx is a local
candidate only, with no hosted update channel. A separate skin component is deferred. A skin fork requires a demonstrated limitation first.

The preview boundary is: Kodi adapter → pure route/catalogue logic → invented data.
Demo selected lists, saved movie IDs and watched overrides live in the add-on
profile as demo.json. The saved collection starts empty and accepts future movies.
Atomic replacement avoids partial writes; this is not a concurrent credential store.
The demo does not open a database or start a background service.

Later boundaries must remain explicit: Trakt supplies metadata/lists/watch state;
a playback adapter locates an authorized source and resolves media; Kodi plays it.
Real-Debrid is not a complete playable-title catalogue. An air/release date is not
proof of source availability. One component must own resume/scrobbling per playback.

Stable plugin routes allow skin widgets and folder browsing to use the same data.
Routes: list (id=weekend/discover/series/saved), show (id=s1), continue, next, upcoming.
The show filter defaults to all; filter=aired_unwatched excludes watched, future and
unknown air dates while preserving episode order. Existing widget URLs remain valid.
Root selection controls which demo list folders are shown; existing skin widgets
are configured separately and are not automatically removed when a list is deselected.
Changing route names later requires considering existing saved widget paths.

Widget header clickability and context-menu behavior are skin/device-dependent.
Folder access through the HomeFX root is the baseline fallback. Real metadata
provider choice, persistent data caching, live authentication, and playback remain
deferred.

## Inactive Trakt foundations

The auth/token/client/view modules separate device login, profile credentials, API
requests and metadata/watch joins. The transport module supplies fixed-host HTTPS
callbacks; Session coordinates login/refresh/account changes and Library combines
read operations with a bounded invocation-memory cache. No public client identity
or account configuration is shipped. `default.py` does not import this stack;
existing saved widget routes retain synthetic behavior. Its new setup route only
shows guidance. Merely installing the video ZIP does not create token storage.

Transport binds OAuth to auth.trakt.tv and read-only data calls to api.trakt.tv,
uses the standard certificate/hostname-verifying TLS context, refuses redirects
and proxies, and bounds connected I/O and JSON parsing. Cancellation is checked at
I/O boundaries. OS DNS resolution is not interruptible by Python's socket timeout;
there is no claim of an absolute DNS-inclusive deadline. Target TLS/runtime behavior
still requires device tests. No network test uses a real account.

Session checks token expiry before reads, permits one durable refresh claimant and
never automatically repeats a failed data request. Conditional generation updates
prevent stale login or 401 responses from overwriting a replacement account. Library
checks shared state before returning cache hits and validates the whole metadata/
progress join. Without a preference store, refresh conservatively resets invocation selection.
With an injected preference store, a new generation re-verifies user.ids.uuid and
restores only that account's saved list IDs. Durable live widget wiring remains future
work; private selection records are never embedded into public plugin URLs.
Cache TTL is 30 seconds by default, bounded to 32 entries/1 MiB serialized data,
with copy isolation. There is no private persistent metadata cache or background
observer. External account changes invalidate data when the next read observes them;
Library.disconnect clears its cache before clearing local credential state.
Cache keys also include an opaque library-instance identity, so shared cache injection
cannot mix accounts whose independent profile generation counters happen to match.

## Explicit action contracts

`trakt_actions` prepares validated single-item requests for mark-watched history and
movie additions to an owned list. Session accepts an optional mutation callback;
without one it reports writes disabled before authentication/network work. The
transport exposes a separate strict POST boundary; existing read callbacks remain
GET-only. Result classification checks the response body, not just its HTTP status.
Uncertain results are not replayed or used to change local watched status.

Session data revisions invalidate invocation caches after attempted writes, including
lost responses. This is not cross-device synchronization; other invocations still
observe bounded cache staleness. Compound reads check revision and credential generation
so they cannot combine snapshots across an intervening action or account switch.
Reads through the same session are refused while a mutation callback is pending;
completion invalidates again even if the callback raises. Preference snapshots
carry a persistent epoch used for conditional saves; disconnect invalidates credentials
first and advances the epoch while clearing choices, rejecting delayed saves.

## Readiness and future account UI

The readiness route is handled before profile/state loading. A bounded report of
local interpreter/standard-library and installed add-on capability is shown only on
request. Arbitrary strings, paths and exceptions are not echoed into the report.
No network probe, file export, account-store creation or playback handoff is performed.

`account_flow` sits above Session behind injected UI/wait/cancellation callbacks.
It coordinates a future device-code screen and explicit local disconnect; it is not
imported or enabled by the Kodi connection menu. The flow confirms account replacement,
respects poll timing/expiry, checks cancellation and always closes progress UI. Its
bounded waiting is not proof of actual Kodi responsiveness or live authorization.
