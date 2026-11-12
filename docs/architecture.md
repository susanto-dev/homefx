# Architecture

One source repository, with separate add-on directories as components are needed.
Only plugin.video.homefx exists in the first batch. repository.homefx and any skin
component are deferred. A skin fork requires a demonstrated limitation first.

The preview boundary is: Kodi adapter → pure route/catalogue logic → invented data.
Demo preferences and watched overrides live in the add-on profile as demo.json.
Atomic replacement avoids partial writes; this is not a concurrent credential store.
No shared database or background service is introduced.

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
provider choice, pagination, caching, authentication, and playback are deferred.
