# Progress rows for one selected show

This candidate adds three read-only terminal folders to **HomeFX Development
Video**. It reuses the saved list, selected show and private video account. It
changes no skin settings and does not enable the public Preview account routes.
A source change is not proof that its new package is hosted or tested on TV.

## Three different views

The menu appends **— this show, regular seasons** to each folder name below.

| Folder | Included episodes and order |
|---|---|
| **Continue watching episodes** | Regular-season episodes with a known aired date, known unwatched status and a resumable pause (progress greater than 0 and less than 100, with a pause timestamp). Most recently paused first, then season/episode order for ties. |
| **Next aired unwatched episode** | At most one episode: the earliest season/episode number among known aired, known unwatched regular-season episodes. It can already be partially watched. This is narrative order, not newest air date. |
| **Upcoming episodes** | Regular-season episodes with a known future air date, excluding known watched entries. Earliest date first, then season/episode order. Unknown watched status stays unknown; it is not labelled unwatched. |

These are views of **one show in one saved list**, not a global Continue Watching
feed, an automatic next-player action or a personal calendar. Next aired can point
to an earlier missed episode even if a later episode was watched. It does not
choose only episodes after the most recently watched one. An episode can appear
in both Continue watching and Next aired; the views answer different questions.

Unknown air dates appear in none of these views. Watched progress takes precedence
over a stale pause. A future date does not establish that a playable source exists.
The existing **Aired unwatched episodes — all regular seasons** remains separate:
it orders unfinished entries first and then newest aired first. Existing saved
widget routes and ordinary show-to-season browsing remain unchanged.

## Choose a folder, then assign a skin row

After merge and verified normal publication, update **Development Video** from the
current checksum-named ZIP at the [HomeFX source](https://susanto-dev.github.io/homefx/)
and fully restart Kodi. Keep the existing login and saved selections. Development
Video is a deliberate ZIP update, outside repository auto-updates; use the verified
filename/checksum for the published candidate. No token transfer or new login is
required solely for this update. See [delivery boundaries](development-video.md).

Open **HomeFX Development Video → Widget folders → Shows and episodes (progress
views read Trakt history) → saved list → show**, then choose one of the three
folders above. The add-on's list selection does not create a skin row.

In the existing Arctic: Zephyr - Reloaded skin's widget chooser, enter that same
terminal folder and choose **Use as widget**. Do not stop at the show/view chooser,
which would display navigation choices. Follow the [existing skin picker steps](widget-setup.md#real-lists-in-development-video)
and retain working rows. Those labels are supported by source inspection; the
new view's actual focus, Back and heading behavior have not been tested on the TV.
If a heading cannot open its folder, browse it inside HomeFX or add a separate
menu/submenu shortcut to the same folder.

## Completeness and request cost

All three views use the existing complete bounded regular-season join: season
metadata, an episode collection per regular season, watched progress and paused
pages, alongside the selected-list/account reads. They add no endpoint or new
metadata provider. The join rejects oversized or incomplete responses; it does
not return a truncated successful row. The existing bounds are 50 included
seasons and 5,000 episodes, and request limits can stop it earlier.

This means even a one-item Next aired row can require the full show's metadata
and progress. Each additional row or refresh can repeat requests. Only the
existing invocation-memory cache is used; there is no persistent history cache,
background refresh or guaranteed request sharing between rows. Measure before
adding several show rows; no performance improvement is claimed.

A successful empty Continue watching view means no eligible pause was found.
An empty Next aired view does not prove that the show is complete: air-date or
watched evidence can be unknown. An empty Upcoming view means no eligible known
future date was found, not that no future episodes will be announced. A failed,
offline, cancelled or authorization-needed read must remain a separate state,
not look like an empty successful result. Account/selection changes invalidate
old references and final rendering retains the existing guards.

## Short TV check

Use only the already working account. Do not alter token files, disconnect or
repeat completed authentication/storage checks for this candidate.

1. Open the three folders for one selected show. Privately check that Continue
   watching contains unfinished aired entries, Next aired follows season/episode
   order, and Upcoming contains future dates. A genuinely empty view is valid;
   record **content / empty / failed / not run** for each, without names or titles.
2. Open an episode's details, then Back. Check episode/season identity, return
   position and responsiveness. These tiles open metadata, not playback.
3. Assign one terminal folder as a skin row using **Use as widget**. Fully restart
   Kodi and confirm the saved list and row survive. Record approximate first-load
   (**cold**) and immediate-reopen (**warm**) seconds, plus focus/Back behavior.
4. If that works, add a second row in an unused slot and record the combined load
   time and responsiveness. Do not assume separate rows share requests. Keep an
   existing working row until the new one is accepted.

Report fixed outcomes, failed step numbers and approximate times only. Keep tokens,
verification codes, private lists/history, profile paths, full backups and raw logs
private. Synthetic tests are not live-account or device acceptance. No playback,
Real-Debrid, remote writes, scrobbling or replacement skin is enabled here.
