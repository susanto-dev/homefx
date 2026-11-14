# Aired unwatched episodes across a selected show

Development Video adds **Aired unwatched episodes — all regular seasons** to the
context menu of a selected-list show and its season/episode rows. Long-press or
use the remote's context-menu button, then choose that action. The ordinary click
still opens seasons; existing saved routes and per-season filters are unchanged.

This is a read-only view of one selected show, not a global Next aired feed,
automatic continuation or playback. It uses the existing Trakt account and complete
bounded series metadata/progress join. Future episodes, unknown air dates and
unknown watched states are excluded. Watched entries are excluded even if an older
pause exists. Specials (season zero) are excluded. Unfinished episodes come first,
then the existing newest-aired-first order applies; this is not narrative episode
order. Each row includes season/episode numbers and opens its own episode details.

## Completeness, privacy and loading

The route contains only account-bound opaque selected-list/show references. The
show must still belong to the selected list; old-account and deselected references
cannot access it. Existing cancellation, error states, account/revision checks and
final render guards remain. Failed/incomplete reads do not become an empty watched
snapshot or a successful partial directory. A genuinely empty view can mean all
known aired episodes were watched, or watched/air-date evidence is unknown; it does
not prove the show is complete or that no episodes are available elsewhere.

The existing series join reads season metadata, one episode collection per regular
season, watched progress and bounded paused-playback pages, alongside normal
account/list reads. No extra title-provider request or new endpoint is added.
The existing limits are 50 included seasons and 5,000 episodes. Metadata count
mismatches and larger results fail rather than truncate. Existing request limits
can stop work sooner; these bounds do not promise a large show loads successfully.

The cache is invocation-memory only. Opening this route again or using multiple
skin rows may repeat these reads. No persistent history database, prefetch loop,
background worker or performance improvement is introduced. Kodi disk directory
caching remains disabled. Date/progress metadata does not identify playable sources.
No remote writes, playback, Real-Debrid, scrobbling or new skin is activated.

## Smallest TV check after verified publication

1. Update Development Video from the current checksum-named ZIP in the HomeFX
   source and fully restart Kodi. Keep existing credentials and selections.
2. Choose a saved show, open its context menu and select the new all-regular-seasons
   action. Check a few entries privately: season/episode labels, watched exclusion,
   future exclusion and unfinished ordering. Unknown watched state is not unwatched.
3. Open an episode from a later season; its detail and per-season context actions
   should stay in that episode's season. Back should return to the same directory.
4. Report success/empty/failure, approximate first/repeat loading times and remote
   responsiveness. Do not share titles, list names, history, tokens or raw logs.

A skin may let you save this directory as a widget; context-menu navigation is not
proof its widget picker can select it. Start with folder browsing, then use only the
skin's existing supported directory selection. Test restart, focus/Back and timing
separately if assigned. No extra skin row is created by HomeFX.

Cloud tests use fabricated responses. Actual endpoint behavior, the new context
menu and cross-season browsing have not been validated on the target TV. Existing
season browsing and the completed authentication tests remain valid; do not repeat
login/storage tests solely because of this view.
