# Selected-list movie progress views

This candidate adds real read-only movie progress to **HomeFX Development Video**
using the existing Trakt account and saved lists. It does not activate public
Preview/Production, TMDB, Real-Debrid, playback or remote list/history writes.
The installed skin and existing mixed movie/show widget routes stay unchanged.

## Where to find it

Open **Movie progress views / widgets (reads Trakt history)**, choose a saved list,
then choose a view. The new menu discloses the history read. Opening the source and
view-choice folders reads list/account identity only, not movie watched/playback
history. Selecting a movie view deliberately adds those read-only requests; a skin
row configured to its route can repeat them without showing login/consent dialogs.
A widget never initiates login or silently falls back to demo data.

| View | Included movies |
|---|---|
| All movies with progress | Movies in this selected list, with watched status and unfinished percentage where known |
| Unwatched movies | Absent from a successfully read complete watched snapshot; includes future/unknown release dates |
| Released unwatched movies | Unwatched with a known release date at or before now |
| Unfinished released movies | Released, unwatched, with a latest paused percentage strictly between 0 and 100 |
| Upcoming movies | Known future release dates in this list, with watch status shown |

Shows and other list entry types are intentionally outside these movie-only views.
Upcoming movies are not the personal episode calendar. Unfinished movies here are
not a global Continue Watching feed or next-episode list. Unknown release dates are
not treated as released. A movie's Trakt release date does not establish regional
streaming availability or a playable source.

Unfinished eligible movies sort first; then aired/unwatched, future dates, unknown
dates/status and watched items follow the existing ordering rules. Known watched
status overrides an older pause. In the new live view boundary, newer zero/completed
pause records supersede older unfinished records; contradictory or malformed movie
progress rejects the result. The older tolerant low-level helper behavior remains
available for its existing callers. A percentage is not a resume timestamp and is
never passed to a player.

## Data, privacy and request costs

The view reuses existing list metadata, the complete unpaginated movie watched
snapshot and bounded paused-playback pagination. There is no per-title metadata,
artwork or source lookup. These are two additional logical reads beyond the normal
list journey, not necessarily two HTTP requests: paused results can paginate, and
ordinary identity/list pagination or token refresh still applies. Lists with no
movies return empty without fetching history. Limits reject oversized/incomplete
results rather than silently truncating or declaring every movie unwatched.

The movie synopsis and explicitly named Trakt rating/vote count remain visible.
Movie details retain the selected filter and progress context. If the item no longer
belongs in the view, reopening its old detail route reports unavailable. **Open full
list** returns to the original mixed-list view, which has its original metadata-only
watch-state behavior.

URLs contain existing account-bound opaque list/item references plus a fixed filter
name, never account IDs, title text, history or tokens. Reopening resolves membership
again. Account replacement, disconnect or changed selection invalidates old access;
final guards still run before rendering. Failed history requests never produce an
empty watched snapshot or a successful partial directory.

History stays in the existing bounded invocation-memory cache only. No new database,
background process or persistent history cache is added. A fresh invocation checks
current account/list state and fetches the applicable data again. Multiple skin rows
can therefore repeat history requests; no performance or cross-row request-sharing
claim is made. Provider limits, offline responses, account changes and cancellation
use the existing fixed error states, with no raw response/credential reporting.

## Smallest TV check after verified publication

1. Update **HomeFX Development Video** from the current ZIP in the HomeFX source,
   then fully restart Kodi. Keep the existing login and saved lists; completed
   authentication/storage checks do not need repeating solely for this update.
2. Open **Movie progress views / widgets (reads Trakt history)** and a previously
   selected list. Check a few entries privately against what you know in Trakt.
   Known watched movies should be excluded from unwatched/unfinished views.
3. Check that future/unknown dates are excluded from released/unfinished views,
   and that movie details show the same watch status and unfinished percentage.
   An empty unfinished row can be correct: it depends on Trakt's paused records.
4. Assign one of these view folders to a row in the existing skin, separately from
   choosing the list in HomeFX. Check focus, Back/return position, and reopening the
   same saved widget after restart. The **Open full list** action remains available.
5. Report only success/empty/failure state, whether filters looked correct,
   navigation observations and cold/warm timings; optionally compare two rows.
   Do not share titles/list names, watch history, codes, tokens, paths or backups.

Actual Trakt endpoint entitlement, these new filters, skin presentation and load
times are unverified on TV. Cloud tests use fabricated HTTP responses and cannot
replace this acceptance. If a view fails, the original selected-list browser remains
available; do not reconnect or reinstall repeatedly without a specific diagnosis.

## Next boundaries

TMDB is deferred, not required for these views. Real-Debrid still needs separate
registered account/device-flow validation and an authorized source-input decision.
Continue Watching across all content, episode continuation and scrobbling are later
work; no custom skin is needed to test this candidate.
