# TV acceptance — preview 0.5.0

Status: NOT RUN. Target: Kodi 21.2 with the user’s existing home-screen layout.
Record device, embedded Python, skin and widget-configuration component versions,
package SHA-256, steps, expected/observed behavior and elapsed load times.

1. Transfer the locally built ZIP to the TV. In Kodi, use Add-ons → Install from
   zip file. Review any Unknown sources prompt; no repository is installed by this ZIP.
2. Open Video add-ons → HomeFX Preview. Confirm every title is fictional and clicks
   never start playback or ask for account credentials.
3. Select demo widget lists. Deselect/reselect lists; confirm the root reflects it.
4. In the skin's home-menu/widget configuration, browse Video add-ons → HomeFX
   Preview and choose a list folder. Repeat for another list, Continue watching,
   Next aired unwatched episodes, and Upcoming episodes. Menu wording may vary.
5. Check thumbnail/poster rendering, row scrolling, focus, Back navigation, and cold
   versus warm load times. The same original placeholder art is used on all titles.
6. Open My series → Signals from the Garden. Confirm six episodes in order with
   watched, resume, unwatched and future statuses. Episode 2 is unfinished; episode
   3 is watched; episode 4 is the following aired unwatched item.
7. Open the context menu (long-press OK if supported, or the remote menu button).
   Mark episode 2 watched: Next episodes should become episode 4 after refresh.
   Try movie search, Information, Similar movies and the episode continuation preview.
   Repeat from home widgets; note any stale widget needing a skin refresh.
8. Click an upcoming movie and a released movie: both explain demo limitations.
   Browse the full list from HomeFX. Record whether this skin also permits a clickable
   widget title or needs a separate menu/submenu shortcut; do not assume support.
9. Open Trakt connection setup. Confirm it only shows guidance and neither asks for
   credentials nor starts a login.
10. Add a released and a future movie to My movie list through the context menu.
    Add the same movie twice: it should appear once. Cancel removal, then confirm
    removal. Enable this fourth list in list selection if an older profile hides it.
11. From a show or episode context menu, browse aired unwatched episodes. Verify
    unfinished episodes remain, watched/future episodes are excluded, and All episodes
    restores the full narrative list. Check both folder navigation and saved widgets.
12. Restart Kodi and verify demo selections/overrides persist. Reset demo data and
   verify the original states return and the saved movie list is empty. Check empty search and cancellation behavior.

Playback/subtitle/resume/scrobbling acceptance is DEFERRED, not passed. The displayed
resume values are synthetic, not a functional player integration. Real Trakt lists,
Add to Trakt list, login and recommendations are also deferred. Do not send a full
Kodi backup or unredacted logs; provide only minimal sanitized evidence.

## Device readiness report

Open **Device readiness** from the HomeFX root. Record the displayed safe version and
capability fields, alongside the package checksum and observed UI behavior. The report
must not ask for credentials, access the network, create account storage, show profile
paths or claim live integration passed. Missing capability should appear as unavailable
without preventing normal demo navigation. No full backup or unredacted log is needed.

Use this report to plan the first registered-app/device test, not as a substitute for
it. TLS certificate availability, SQLite import and add-on presence do not establish
Trakt authorization, playback handoff, subtitles, resume or scrobbling.
