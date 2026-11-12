# Architecture

One source repository, with separate add-on directories as components are needed.
plugin.video.homefx supplies the synthetic preview. repository.homefx is a local
candidate only, with no hosted update channel. A separate skin component is deferred. A skin fork requires a demonstrated limitation first.

The preview boundary is: Kodi adapter → pure route/catalogue logic → invented data.
Demo preferences and watched overrides live in the add-on profile as demo.json.
Atomic replacement avoids partial writes; this is not a concurrent credential store.
The demo does not open a database or start a background service.

Later boundaries must remain explicit: Trakt supplies metadata/lists/watch state;
a playback adapter locates an authorized source and resolves media; Kodi plays it.
Real-Debrid is not a complete playable-title catalogue. An air/release date is not
proof of source availability. One component must own resume/scrobbling per playback.

Stable plugin routes allow skin widgets and folder browsing to use the same data.
Routes: list (id=weekend/discover/series), show (id=s1), continue, next, upcoming.
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
progress join. Refresh also changes generation and conservatively resets invocation
list selections; stable account-bound saved widget selection remains future work.
Cache TTL is 30 seconds by default, bounded to 32 entries/1 MiB serialized data,
with copy isolation. There is no private persistent metadata cache or background
observer. External account changes invalidate data when the next read observes them;
Library.disconnect clears its cache before clearing local credential state.
