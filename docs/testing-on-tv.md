# TV acceptance — next preview

Status: **PARTIAL — storage check did not pass on 0.17.2**. Target: Kodi 21.2
with the user’s existing home-screen layout. Navigation and live-service acceptance
remain untested.
Record device, embedded Python, skin and widget-configuration component versions,
package SHA-256, steps, expected/observed behavior and elapsed load times.

Use the [short activation handoff checklist](activation-checklist.md) to track the
next evidence and owner input. It summarizes these gates without enabling live routes.

## Start here: bounded read-only journey

1. **Published package first:** follow the repository installation/update steps below.
   Expected: Kodi reports the advertised video/repository versions; old widget
   shortcuts still open. Record versions and whether installation/update succeeded.
2. **Local capability next:** open Device readiness, then Test private storage.
   Expected: safe capability fields and fixed storage/cleanup results. Cancel the
   storage prompt once before running it; cancellation must not perform the test.
3. **Current preview navigation:** select two demo lists in HomeFX, then configure
   their rows separately in the existing skin. Check thumbnail focus, Back and return
   position, opening the full-list folder when the heading cannot be clicked, and
   title/season browsing. Cancel selection once; previous choices must remain. Record
   first-open and immediate-reopen load times. Restart Kodi and check selections and
   saved widget paths again. Existing detailed checks below remain applicable.
4. **Blocked until activation gates:** registered identity/redirect verification,
   explicit owner authorization, and the [account gates](account-setup.md) precede
   any real login. Then repeat selection, row configuration, details and restart
   checks with one personal and one liked list. Check loading, empty, offline,
   authorization-needed and cancellation outcomes without remote writes. Never
   label the live step passed from synthetic or cloud tests.

Return only versions, fixed result/error categories, success/failure of the steps,
focus/Back/return-position observations and cold/warm timings. Do not send tokens,
device codes, private title/list contents, history, profile paths, screenshots with
private information, unredacted logs or a Kodi backup. No playback, Real-Debrid or
scrobbling acceptance is part of this milestone.

## Current device candidate and timing record

The hosted baseline checked on 13 November 2026 is **video 0.17.2 / repository 0.2.0**.
The index and both root/indexed ZIP copies matched the release inventory. Target Kodi **21.2**, Arctic Zephyr Reloaded **3.0.3**,
**Vertical Multi Widget Netflix**. Keep the existing skin and saved routes.
These download checks establish hosted bytes only; see the
[installation guide](install.md) for the verified source and filenames. Device acceptance remains incomplete; the observed diagnostics are recorded below.

This public candidate tests synthetic navigation, local demo persistence and the
optional temporary storage probe. It does **not** call the inactive account-bound
renderer added in 0.16/0.17. A successful demo cannot validate real season/progress
rendering, account isolation, login/refresh, TLS or stale-row removal in Kodi.

After steps 1–3 above, use the same skin presentation and record three trials for
one demo row, then two selected-list rows plus Continue watching, Next aired and
Upcoming. For each trial restart Kodi, time from opening the home screen until
all configured HomeFX rows visibly finish loading, then leave and immediately
reopen the home screen and time again. Label these **first open after restart**
and **immediate reopen**; they are observable timings, not proof of cache misses
or hits. Record loading failure/timeout rather than silently dropping a trial.
Also note whether focus responds while rows load, Back returns promptly, and the
previous selection is retained. No target latency or improvement is claimed yet.

| Layout | Trial | First open (seconds) | Immediate reopen (seconds) | Focus / Back / return position |
|---|---|---|---|---|
| One demo row | 1–3, one record each | Not measured | Not measured | Not observed |
| Five rows as above | 1–3, one record each | Not measured | Not measured | Not observed |

Synthetic rows make no Trakt requests. These timings cannot characterize provider
latency, request counts, rate limits or private metadata caching. The inactive
service cache is invocation-local, not a persistent warm cache across Kodi plugin
invocations. After authorized live activation, repeat the same measurements and
separately verify bounded network requests, rate-limit/offline behavior and cache
invalidation without exporting private data. Optimize only observed bottlenecks.

Return the versions, fixed readiness/storage results (including cleanup), navigation
outcomes and timing records. Keep actual list/title names, paths and account data
private. After those results, the next bounded milestone is registered-client
verification and an explicitly authorized development-device read-only connection;
see [required owner input](account-setup.md#owner-input-for-the-read-only-milestone).
No playback, writes, Real-Debrid or skin replacement is part of that milestone.

## Observed device diagnostics and 0.17.3 rerun

The owner supplied diagnostic results from the TV: **HomeFX 0.17.2**, **HomeFX
repository 0.2.0**, **Kodi 21.2** and **Python 3.11.7**. This confirms the embedded
Python version on that device. The visible readiness report contained only those
version fields; SQLite and TLS capability results were not visible and cannot be
inferred. The storage check reported:

| Result | Observed on 0.17.2 |
|---|---|
| Private file permissions | failed |
| SQLite commit/rollback | not run |
| Temporary cleanup | passed |
| Overall | not passed |

SQLite was not reached; this is not evidence of a SQLite transaction failure.
The exact permission failure stage and underlying filesystem cause remain unknown.
These observations establish neither a clean repository-first installation path
nor widget navigation, persistence, timing, TLS or live-account acceptance.

**0.17.3 is a diagnostic candidate until its merge and publication are verified.**
It uses a scrollable report for readiness/storage and adds a fixed **Failure stage**
label to the storage result. It does not relax permissions or repair profile data.
After verified publication:

1. Update to 0.17.3, fully restart Kodi, then open **Device readiness**. Check that
   the remote can scroll through the complete report and Back returns to HomeFX.
   Record versions and fixed capability fields, including unavailable results.
2. Open **Test private storage** and cancel once; no test should run. Reopen and
   confirm the synthetic test, then scroll through the result.
3. Return **Private file permissions**, **SQLite commit/rollback**, **Temporary
   cleanup**, **Overall** and **Failure stage** exactly as displayed. A failed
   result remains a blocker, even when cleanup passes. Do not infer a root cause
   from the stage label alone.

Do not change permissions, clear Kodi data, delete unfamiliar files or send paths,
logs, tokens or backups. No new screenshot is required. Live Trakt, Real-Debrid,
writes, playback and scrobbling remain inactive while this blocker is investigated.

## 0.17.1 repair acceptance — after verified publication

The 0.17.1 repair is included in the published 0.17.2 candidate. Update through the
repository, retaining saved widget routes and demo selections. While opening the
root, a selected-list folder and a season folder, press Back/cancel during loading.
Expected: no error modal, no continued row production after Kodi rejects submission,
and the listing is not reported as successfully complete. Reopen each folder and
check all expected titles return, then check focus, Back and return position in the
existing skin. Fast synthetic folders may finish before cancellation: record **not
exercised** rather than pass in that case. Do not infer that previously submitted
rows disappear atomically. Repeat the timing protocol above without claiming speed
improvement from cloud tests. All live-account activation gates remain unchanged.

## 0.17.2 local-edit acceptance — after verified publication

Restart Kodi after updating, then confirm existing selections, watched overrides,
saved movies and widget routes are retained. Select lists, mark a title watched,
add/remove a saved movie and cancel each dialog once. Expected: unrelated changes
remain, cancellation changes nothing, and confirmed reset deliberately restores all
defaults. If two invocations can be exercised safely, leave list selection open,
make a watched/movie change from another invocation, then finish selection: all
non-conflicting changes must persist after restart. A busy/save failure must not
show an update-success notification. Return only fixed outcomes and timings, not
profile files. Synthetic checks do not establish actual SQLite locking on Android.

## Detailed preview checks

1. After the reviewed Pages deployment and HTTP check, use Kodi Settings → File
   manager → Add source: `https://susanto-dev.github.io/homefx/`, named HomeFX.
   Open Add-ons → Install from zip file → HomeFX → `repository.homefx-0.2.0.zip`.
   Review any Unknown sources prompt. Then use Install from repository → HomeFX
   Preview Repository → Video add-ons → HomeFX Preview to install the currently verified published version (0.17.2).
   If File manager listing fails, record it and transfer the repository ZIP manually.
   The separate video ZIP is an alternate manual installation, not the repository.
2. Open Video add-ons → HomeFX Preview. Confirm every title is fictional and clicks
   never start playback or ask for account credentials.
3. Open Widget setup. Confirm both guidance pages appear without account prompts,
   profile access or playback. Select demo widget lists. Deselect/reselect lists;
   confirm the root reflects it. Follow [widget setup](widget-setup.md).
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
capability fields, including the HomeFX repository version, alongside the package
checksum and observed UI behavior. A missing repository must read **not installed**;
a failed/invalid local presence or version probe must read **unavailable**. Installing
the repository separately should change the displayed result after reopening the screen.
Neither result proves an index refresh or upgrade succeeded. The report
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

## Experimental repository acceptance (0.2.0 repository / current video)

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


## Explicit private-storage check

Open **Test private storage** from the HomeFX root and review its confirmation. This
separate action creates synthetic temporary files inside the add-on profile, checks
private permissions and SQLite commit/rollback, then removes its own temporary files.
It does not read account databases, contact services or start playback. Cancelling
before the check must leave the profile untouched. Existing **Device readiness**
continues to avoid profile access.

Record only the fixed result labels, HomeFX/Kodi versions and whether cleanup passed.
A failure must not be reported as account-storage acceptance. An empty profile
directory may remain when the profile did not exist before. Do not share profile
paths, backups or credentials. A pass is a local synthetic check, not proof of token
refresh recovery, account authorization, cross-device quotas or protection from
other code running as Kodi. These remain separate tests.

## Inactive account-bound route acceptance (0.16)

Do not attempt these live steps before registration, explicit authorization and
account/device gates. Then verify a saved personal/liked widget survives restart
and refresh, fails safely for another account, and does not rebind after list
reordering/deselection. Clear/disconnect must invalidate the old reference; choose
new sources after reconnecting. Test title and episode metadata actions without
playback, and a full-list shortcut when the heading cannot be clicked.

Include account/selection changes around directory submission. Failed completion
must not be assumed to clear skin-held rows: record actual stale-row behavior,
Back/return position and cancellation, and resolve it before public activation.
Return only fixed outcomes/timings, not URLs, private names, contents or profile data.

## Episode view acceptance after activation gates (0.17)

In the existing skin, open a season folder and check the independent count labels.
Use its context action to open Aired unwatched episodes: only known-unwatched aired
items should appear, with unfinished items first. Check the displayed percentage
without expecting playable media or functional seek/resume. Open metadata details,
return, and check focus/position. Switch to All episodes and confirm narrative order.
For an empty filtered folder, Back must return to the season folder, where All
is available. Check old saved episode URLs still use All after upgrade/restart.
Do not share private episode/list names or watched history; return fixed outcomes
and timing/focus observations only. These live checks remain NOT RUN.
