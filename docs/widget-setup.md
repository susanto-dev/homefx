# Widget setup with your existing skin

Use **HomeFX Development Video** for your real saved Trakt lists. Keep Kodi 21.2
and the installed Arctic: Zephyr - Reloaded 3.0.3 **Vertical Multi Widget Netflix**
layout. HomeFX supplies folders; the skin chooses rows, headings, artwork layout
and focus behavior. **Saving a list in HomeFX does not create a skin row.**

The owner has already saved a real list and opened more than 100 movies. Continue
from that selection. Program diagnostics authorization, refresh, credential restart,
disconnect, cancellation and offline recovery were also reported successful; they
are separate evidence and do not need repeating for widget setup. Video widget
navigation, video restart persistence and performance remain unverified on TV.

## Real lists in Development Video

The root menu calls the entry **Widget folders (choose in your skin)**; the paths
below shorten it to **Widget folders**. **Widget setup help** also summarizes the
steps on the TV.

1. Use the current checksum-named **Development Video** ZIP from the existing
   HomeFX source, `https://susanto-dev.github.io/homefx/`, after its publication is
   verified. See [Development Video delivery](development-video.md). This is a direct
   ZIP install, outside repository auto-updates. A candidate described in source is
   not necessarily hosted yet. Keep existing credentials and saved selections.
2. Open Video add-ons → **HomeFX Development Video → Widget folders → Selected
   lists → your saved list**. Check that the folder opens. If no list is saved,
   use **Choose personal or liked lists** in the add-on first.
3. Open **Skin settings → Home → Customise home menu**. Choose the existing home
   menu item that should own the row, then its **Widgets → Widget 1** slot (or an
   unused slot). Open the slot's **Widget 1** source chooser.
4. In that chooser, browse **Video Library → Video Add-On → HomeFX Development
   Video → Widget folders → Selected lists → your saved list**. Enter the saved
   list folder, then choose **Use as widget**. Choosing HomeFX's root or an earlier
   chooser folder would make the row display navigation choices instead of titles.
5. Back out of customization and allow the skin to rebuild. Check the row on Home.
   If useful, choose **Widget aspect** in the slot's settings for the skin's poster
   or thumbnail presentation. Metadata placeholders are expected; tiles do not play.
6. Open the complete list inside HomeFX, or assign that same list folder to a
   separate home menu/submenu shortcut. **Create menu item to here** is the Skin
   Shortcuts folder-picker action for a menu shortcut. Use this fallback if the row
   heading cannot open the list. On a title, **Open full list** is another fallback.

The English skin/editor labels and folder-picker behavior above were checked in
public source, including the exact skin 3.0.3 archive. They have **not been exercised
on the target TV**. Skin Shortcuts versions and localization can change picker
labels or grouping. See [source evidence](widget-mvp.md#skin-source-and-license-evidence).
If a grouping differs, find the video add-on folder in the existing picker; keep
working rows until the new row is accepted.

## Other real widget folders

Inside **Widget folders**, choose the terminal folder appropriate for the row:

- **Selected lists → saved list** gives the existing mixed movie/show list.
- **Movie progress (reads Trakt history) → saved list → view** gives a movie-only
  view. Choose the actual view folder before **Use as widget**; see
  [movie progress](movie-progress.md) for its filters and history reads.
- **Shows and episodes (progress views read Trakt history) → saved list → show**
  offers **Seasons and episodes (reads Trakt history)** and **Aired unwatched
  episodes — all regular seasons**. The latter is a directly selectable episode
  folder. For a single season, enter Seasons and episodes, then the season folder
  before saving the widget source.
- The selected-show progress candidate adds **Continue watching episodes**,
  **Next aired unwatched episode** and **Upcoming episodes** under that same show
  chooser. Enter a terminal view before **Use as widget**. These are separate
  per-show views, not global feeds or playback; see [rules and acceptance](show-progress.md).

The ordinary show click in an existing selected-list row still opens seasons.
Existing saved routes remain valid; the new picker folders do not require remaking
working shortcuts. The cross-season view excludes specials, future/unknown dates,
watched episodes and unknown watched states. It orders unfinished entries first,
then newest aired first; it is **not Next aired** or narrative episode order.
See [cross-season scope and cost](show-unwatched.md).

A skin refresh can repeat list/history requests. The cross-season join can inspect
up to 50 regular seasons and 5,000 episodes and may stop sooner on other limits.
These are rejection bounds, not a promise that large shows load quickly. Measure
one row before adding another. No persistent cache or cross-row request sharing is
claimed.

## Read-only list journey acceptance

Use the short [one-list, one-row checklist](widget-mvp.md#one-list-one-row-tv-check)
for the remaining TV checks: focus, Back, return position, cancellation, full-list
fallback, video restart, cold/warm timing and then two rows. Report fixed outcomes
and approximate times only; keep list names, titles and history private.

The Development rows expose metadata and original placeholder artwork. Native Kodi
IDs support [TMDb Helper compatibility](kodi-metadata.md), including the inspected
5.4.16 contract, but do not guarantee automatic artwork. No playback, Real-Debrid,
remote list/history writes or new skin is enabled. Dates are not playable-source
availability. Continue Watching, Next aired and Upcoming remain distinct concepts;
the [personal calendar](calendar-contract.md) is not every selected show's schedule.

## Existing synthetic Preview widgets

**HomeFX Preview** remains separate: repository **0.2.0**, video **0.17.15** in the
existing published Preview. Its repository installation and updates do not install
or update Development Video. Keep any working Preview widget routes.

For that demo only, open **Select demo widget lists**, then browse **Widget
sources**. In the same skin picker choose **HomeFX Preview → Widget sources →
demo list/view**, enter it and choose **Use as widget**. Demo title clicks show
synthetic information; demo watched/context actions stay local. Preview's
Continue watching, Next aired unwatched episodes and Upcoming episodes are
synthetic, not real-account Development feeds.

Preview's **Widget setup** and **Device readiness** are demo help/local presence
checks. They do not establish real account access, repository reachability or TV
acceptance. The local presence check uses Kodi 21.2's documented
[`System.HasAddon(id)` condition](https://github.com/xbmc/xbmc/blob/21.2-Omega/xbmc/GUIInfoManager.cpp#L1996).
See the broader [TV checklist](testing-on-tv.md) for a fresh demo installation.
