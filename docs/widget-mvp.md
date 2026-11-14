# Real-list widget MVP on the existing skin

The root entry is **Widget folders (choose in your skin)**, shortened below to
**Widget folders**. **Widget setup help** is available alongside it.

The next device milestone is **one existing real list in one row**, using HomeFX
Development Video and the installed Kodi 21.2 / Arctic: Zephyr - Reloaded 3.0.3
Vertical Multi Widget Netflix layout. Start with the already saved list; then test
a second row and the movie/show views. [Widget setup](widget-setup.md) gives the
folder-picker steps. HomeFX selection and skin row configuration are separate.

The reported real-list selection/save and browsing of more than 100 movies passed.
Program diagnostics authorization, refresh, stored credentials after restart,
disconnect, code-dialog cancellation and responsive offline recovery also passed.
Those program results do not establish the video's widget or restart behavior.
Do not repeat completed authentication checks just to collect more evidence.

## Delivery boundary

Development Video uses ID `plugin.video.homefx.development`, its existing profile
and the direct checksum-named ZIP at the [HomeFX source](https://susanto-dev.github.io/homefx/).
Use the filename/checksum shown after publication verification; source changes alone
do not prove a new ZIP is hosted. This add-on has no repository auto-update path.
Keep the existing login and selections when installing a same-ID update.

HomeFX Preview (`plugin.video.homefx`) remains synthetic and separately installed
through Preview repository 0.2.0. Its existing published video is 0.17.17. The program
diagnostics add-on has its own profile; do not transfer tokens or databases between
them. See [Development delivery and scope](development-video.md).

## One list, one row TV check

Use a phone to follow one step at a time. Keep the existing working home rows.
Record **pass / fail / not run**; no private names, contents or screenshots are needed.

1. **Identify the build.** Open Development Video's **Device / build information (no network)**.
   Record **Source version**, **Runtime fingerprint**, **Kodi**, **Python**,
   **Active skin** and **Skin version**. The fingerprint describes the build; it is
   not the ZIP checksum, a signature or a recheck of installed files. Use the
   published filename/checksum separately to identify the downloaded ZIP. A local
   presence/version result does not prove repository updates or widget compatibility.
2. **Open the saved list.** Choose **Widget folders → Selected lists → saved list**.
   Expect the existing real titles. No new authorization or selection is required.
3. **Save one row.** Follow [the skin picker](widget-setup.md#real-lists-in-development-video).
   Enter that exact saved list folder and choose **Use as widget**. Return Home and
   wait for the rebuild/loading to finish. Record success, genuinely empty or the
   fixed failure state; a failed request must not look like an empty successful list.
4. **Check the remote.** Move along the row beyond its first tile. Open title
   information (or a show's seasons and an episode), then press Back. Record where
   focus returns, whether the previous position survives and whether another Back
   returns to Home predictably. Check the full list through HomeFX or a separate
   menu/submenu shortcut if the heading does not open it. A title is metadata,
   not a playback button.
5. **Check cancellation once.** Cancel the skin source chooser without saving and
   confirm the existing row is retained. When Kodi offers cancellation during an
   ordinary folder load, check that Back/cancel returns control and the next open
   can recover. If no cancellable state appears, mark that case not run. Do not
   disconnect, replace credentials or repeat authorization for this check.
6. **Check a real video restart.** Fully close and restart Kodi. Confirm the saved
   selection and row still exist, then repeat the short detail → Back journey.
   A previously passed program restart does not cover this video profile and row.
7. **Measure one row.** Record approximate seconds from opening Home to usable
   tiles after the restart (**cold**), and after immediately reopening the same row
   (**warm**). Note remote responsiveness separately. A warm revisit may still make
   fresh requests; it is not proof of a persistent cache.
8. **Add a second row.** Only after the first works, use another unused slot and a
   second chosen terminal list/view folder. Record the two-row load time, focus/Back
   behavior and whether either row changes unexpectedly. Repeat after a restart if
   practical. Do not assume two rows share reads or load as quickly as one.

Return the fixed build identity, outcomes, approximate cold/warm/two-row times and
any failed step. Keep credentials, codes, private list/history data, profile paths,
full backups and raw logs private. Do not redo a completed grant to make a report.

## Movie and episode rows

After the basic row works, use **Widget folders → Movie progress (reads Trakt
history) → saved list → view** for [movie progress](movie-progress.md). The source
and view-choice folders are navigation; save the chosen terminal view as the row.

For episodes use **Widget folders → Shows and episodes (progress views read Trakt
history) → saved list → show → Aired unwatched episodes — all regular seasons**,
then **Use as widget**. Alternatively enter **Seasons and episodes (reads Trakt
history)** and a season for that season's episode folder. This makes the cross-season
folder reachable in a picker without relying on a context-menu action.

The all-regular-seasons view excludes specials and requires known aired/unwatched
evidence. Unfinished entries come first, then newest aired first; it does not choose
the next narrative episode or provide a global Next aired feed. It may read a season
collection, one episode collection per regular season, watched progress and paused
pages, in addition to normal account/list reads. Bounds of 50 seasons / 5,000 episodes
reject oversized or incomplete results; other limits can stop sooner. Fresh opens
and additional rows can repeat the work. See [show view limits](show-unwatched.md).

The selected-show progress candidate also exposes **Continue watching episodes**,
**Next aired unwatched episode** and **Upcoming episodes** in the same show-view
chooser. Choose the terminal folder before **Use as widget**. Continue watching
uses resumable aired pauses; Next aired chooses at most one known-unwatched episode
in season/episode order; Upcoming shows known future dates while preserving unknown
watched status. None is a global feed or a playback action. See the [per-show rules,
request costs and short acceptance check](show-progress.md). Install only after its
normal publication is verified; no completed authentication check needs repeating.

Metadata uses original placeholders. Standard Kodi IDs are exposed for the
[TMDb Helper 5.4.16 contract](kodi-metadata.md); installed Helper support is not a
promise that the skin will fetch artwork automatically. This batch adds no playback,
Real-Debrid, remote writes, scrobbling or replacement skin.

## Skin source and license evidence

Source inspection is read-only. No upstream skin code, artwork, fonts or other
assets are included in HomeFX. The paths and English labels above are supported by
source; the installed TV's picker, heading clicks, focus, Back, restart and timing
remain **untested until reported**.

- The [official Kodi Omega archive listing](https://mirrors.kodi.tv/addons/omega/skin.arctic.zephyr.mod/)
  serves [skin.arctic.zephyr.mod 3.0.3](https://mirrors.kodi.tv/addons/omega/skin.arctic.zephyr.mod/skin.arctic.zephyr.mod-3.0.3.zip).
  Inspected archive SHA-256:
  `1ec00396d43a3bf35a7699639bbbcb0c7701c457e71825ecc11bb8ec42573a7e`.
  Its `addon.xml` identifies `skin.arctic.zephyr.mod`, version `3.0.3`, name
  **Arctic: Zephyr - Reloaded**, by jurialmunkey and beatmasterrs. It declares a
  dependency on `script.skinshortcuts` with minimum version `0.4.0`; that does not
  identify the user's installed dependency version.
- In that exact archive, `1080i/SkinSettings.xml` maps **Home → Customise home menu**
  to Skin Shortcuts' main-menu editor. `1080i/Includes.xml` supplies **Widgets** and
  six widget slots; `1080i/script-skinshortcuts.xml` opens each slot's source chooser
  and exposes **Widget aspect**. `shortcuts/overrides.xml` includes the **Video
  Library → Video Add-On** picker grouping. The English labels are in
  `language/resource.language.en_gb/strings.po`.
- The skin archive's manifest abbreviates the license as **Creative Commons Non
  Commercial 3.0 License**. Its `LICENSE.txt` explicitly names **Creative Commons
  Attribution-NonCommercial-ShareAlike 3.0 Unported**
  ([CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/)). The
  manifest links the [upstream source repository](https://github.com/beatmasterRS/skin.arctic.zephyr.mod).
  This inspection does not license copying its assets into HomeFX.
- The [official Omega Skin Shortcuts 2.0.3 archive](https://mirrors.kodi.tv/addons/omega/script.skinshortcuts/script.skinshortcuts-2.0.3.zip)
  was inspected for picker behavior. Its `resources/lib/skinshorcuts/library.py`
  `explorer` adds **Use as widget** to the current folder in widget mode and stores
  that folder as `widgetPath`. In menu mode the action is **Create menu item to
  here**. Its English strings identify **Video Library**, **Video Add-On** and
  **Use as widget**. This is supporting evidence, not confirmation that 2.0.3 is
  installed on the TV. Its manifest declares GPL-2.0-only; no code is reused.

For a mixed movie/episode feed independent of saved lists, see the
[account-wide Continue Watching candidate](continue-widget.md).

The [personal calendar candidate](calendar-widget.md) adds a distinct Upcoming
row; it is not a complete schedule of selected-list shows.
