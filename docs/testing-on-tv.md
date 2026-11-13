# TV acceptance — preview 0.9.0

Status: NOT RUN. Target: Kodi 21.2 with the user’s existing home-screen layout.
Record device, embedded Python, skin and widget-configuration component versions,
package SHA-256, steps, expected/observed behavior and elapsed load times.

1. After the reviewed Pages deployment and HTTP check, use Kodi Settings → File
   manager → Add source: `https://susanto-dev.github.io/homefx/`, named HomeFX.
   Open Add-ons → Install from zip file → HomeFX → `repository.homefx-0.2.0.zip`.
   Review any Unknown sources prompt. Then use Install from repository → HomeFX
   Preview Repository → Video add-ons → HomeFX Preview to install version 0.9.0.
   If File manager listing fails, record it and transfer the repository ZIP manually.
   The separate video ZIP is an alternate manual installation, not the repository.
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

## Browsing and widget checks for 0.6

- Open Widget sources and select two list folders in the installed skin. Check the
  content endpoints contain titles only, with no settings rows inside widgets.
- Use a list folder's context menu to open All, Unwatched, Released unwatched and
  Upcoming. Unfinished released titles should remain first; a date is not a source.
- Add Tomorrow's Orchard to My movie list and open Upcoming saved movies. Remove it
  and confirm the empty view opens quietly, without a repeated modal dialog.
- Open Browse seasons from a series or episode menu. Check season counts and enter
  a season; switching All / Aired unwatched must preserve that season scope.
- Mark an episode watched, refresh, and verify counts and filtered views change.
  Restart and confirm the previous local selections and saved movies remain intact.

These are pending device checks, not a report of successful TV testing.

After upgrading from 0.5, reopen existing Continue watching, Next episodes and
Upcoming widget shortcuts before recreating them; legacy empty identifier parameters
must remain compatible.

## Playback setup guidance (0.7)

Open Playback and Real-Debrid setup from the root. It should explain title metadata,
authorized sources and inactive provider integration, without asking for credentials
or starting media. Existing movie/episode clicks must still show demo information.
There is no real account login or source input field to test in this version.
Follow the separate [playback plan](playback-plan.md) before any future live experiment.

## Experimental repository acceptance (0.2.0 repository / 0.9.0 video)

Status: NOT RUN. Record the deployed revision, exact ZIP checksums and the HTTP-check
result separately from device observations. Confirm Kodi can browse the source URL,
install the repository bootstrap, refresh its index and install the video add-on.
No skin package is supplied; keep the existing skin installed separately.

Using a disposable test profile, verify an upgrade from a retained reviewed version
preserves selected demo lists, local overrides and saved widget routes. Confirm the
index advertises only the current versions and that older ZIPs remain available at
their immutable paths. Test offline/error behavior and checksum rejection only with
controlled local test artifacts; never alter the public channel to simulate corruption.
A manual downgrade requires a separate profile-compatibility check and is not automatic.

Do not mark this section passed because a build, deployment or HTTP check succeeded.
Live accounts, real title recommendations, playable sources, next-episode playback,
subtitles, resume and scrobbling remain deferred pending their separate activation gates.
