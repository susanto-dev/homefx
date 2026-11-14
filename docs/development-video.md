# One real Trakt list in Development Video

**Published Development candidate; selected-list browsing passed on TV, widget/restart acceptance pending.** This is an intentionally installed read-only
Development video add-on for the app owner or invited Development users. It is not
general public Trakt access and does not activate HomeFX Preview. No paid service,
Production registration, server or Android app is introduced.

## Delivery and approval

The existing checked Pages build uses the GitHub **Development** public client ID
and registered redirect. It builds `plugin.video.homefx.development` from the same
shared runtime as HomeFX Preview, with a small video entry point. The program test
add-on is not a dependency. Public configuration is downloadable; no secret or user
token is embedded, requested by a build, or used in CI.

The verified source is `https://susanto-dev.github.io/homefx/`. PR #37 merged as
`a28ad740458a363e48fae0c6f4284cd179195bb5`. The normal publication deployed the
candidate; its verification-only rerun compared all uploaded artifact files with
the hosted bytes successfully. The initial verification request failure remains
unexplained; see [publication evidence](releases.md#verified-development-video-delivery-after-pr-37).

Current video test ZIPs use harness version 0.1.0 and the filename
`plugin.video.homefx.development-0.1.0-<SHA-256>.zip`. The
[landing page](https://susanto-dev.github.io/homefx/) and Kodi's main HomeFX source
show the exact current filename and checksum. Use that video ZIP, not the program
script or public Preview. The new icon produces a new digest filename only after
normal publication; no new filename is claimed as hosted in advance.

Older experimental URLs may be retired, but their bytes are never overwritten.
The program diagnostics and manual Preview download move into **advanced/**;
Development Video remains on the main source. Existing indexed release archives and
root release URLs remain available.

The reviewed merge approved distribution of this explicitly labelled candidate.
It does not initiate an account connection. Installing it is deliberate; the owner
then separately consents to Connect and to reading/selecting lists on the TV.
The previously confirmed Development ID/redirect needs reconfirmation only if the
application or GitHub variables changed. No additional app values or private list
names are needed in chat. Do not select Production or supply a client secret.

Every candidate filename contains its SHA-256: different bytes have a different
URL. Version 0.1.0 denotes the test harness, not an immutable repository release.
This current experimental download is outside the retained release inventory;
older candidate URLs may disappear but must never serve changed bytes. Retain the
matching ZIP if needed to disconnect its app-identity scope later. Existing recorded
Preview/repository archives and URLs remain immutable.

## Why a separate video ID

`plugin.video.homefx.development` has its own Kodi profile and widget routes. The
public `plugin.video.homefx` preview, repository updates and saved demo widgets stay
separate. A same-ID replacement would overwrite the preview installation and risk
mixing package origin/account configuration; it is not used for this test.

The existing runtime is shared at build time, not copied into a second implementation.
The video candidate never reads the program test's profile or imports its tokens.
It needs a fresh owner-authorized login. Production packaging and any future choice
migration require separate review; this candidate does not permanently require a
second program or an automatic credential migration.

## Reported list result and remaining acceptance

The owner reported selecting and saving a real list, then opening more than 100
movies from that saved list successfully. No private list contents were supplied.
This establishes that list journey only; widget navigation, restart persistence,
season browsing and cold/warm timing have not been reported as passed.

Trakt requests use pages of up to 100 items, combined into a bounded complete list
before Kodi renders it. Displaying 20 items alone would not reduce those requests.
No pagination or cache behavior changes are included with the source/icon update.
Measure real widget and folder loading before choosing lazy pagination or caching;
a shorter displayed list is not proof of faster network access.

Existing Development Video users can install the new checksum-named ZIP after
publication and fully restart Kodi. The add-on ID and profile/configuration remain
unchanged; do not disconnect or reauthorize merely for the icon. Check that the
existing saved list remains, then continue the uncompleted widget/restart steps
below. No completed program test needs repeating.

## Smallest TV checklist

No previously passed program test needs repeating. These checks exercise a new video
profile, entry point and real-list route, which have not been validated on TV.

1. **Install the verified candidate.** In Kodi choose Add-ons → Install
   from zip file → HomeFX → the newly listed **plugin.video.homefx.development** ZIP.
   Review the source/Unknown sources warning; do not bypass certificate or integrity
   failures. Keep HomeFX Preview and the existing skin installed. This candidate is
   deliberately absent from Install from repository and does not auto-update.
2. **Fully restart Kodi.** Open Video add-ons → **HomeFX Development Video**. Run
   **Test this video add-on's private storage**. Expect permissions, directory,
   SQLite and cleanup to pass. If it fails, stop and return fixed results only.
3. **Connect Development Trakt.** Confirm the own-profile credential-storage notice,
   then authorize privately using the trusted address/code on your TV. A fresh login
   is necessary; the program test's credentials are not reused. No screenshot of a
   code, account page, token, profile path or private list is needed.
4. **Choose personal or liked lists.** Consent to read-only access and select one list
   privately. Expect the saved-choices message. Open **Selected lists / widget sources**,
   then the chosen list. Browse a title and, for a show, its seasons/episodes.
   Rows are metadata with original placeholder artwork, not playable sources.
5. **Assign a skin row separately.** In the existing Arctic Zephyr Reloaded 3.0.3
   Vertical Multi Widget Netflix customization, select this video add-on's chosen
   list folder as the widget source. Labels/menu placement still need device
   confirmation; see [widget setup](widget-setup.md). Selecting a list in HomeFX
   does not create a skin row. Use the full-list folder/context action when the skin
   heading is not clickable. Do not replace working Preview rows until satisfied.
6. **Check restart and navigation.** Fully restart Kodi again. Expect saved selections
   and the candidate row to remain. Check focus, Back, return position and details.
   Record approximate first/cold and immediate/warm row load times. If adding a
   second row, record its effect separately; no speed improvement is presumed.

Directory reads are silent so widget refreshes never display a login/progress/error
dialog. Kodi owns the loading display. Empty, authorization-needed and offline
outcomes use fixed directory status and do not silently substitute demo data.
Cancellation through Kodi and actual skin behavior require this device acceptance.
A widget read may refresh stored credentials automatically; it never initiates login.

**Return only:** installed candidate filename/checksum or harness version, storage and
cleanup results, connected/saved/restarted outcomes, whether the list was empty,
fixed error states, navigation observations and timings. Keep titles/list contents,
identity, tokens, codes, profile paths, raw logs and backups private. Stop after a
failure; do not repeatedly reconnect/refresh to hide it.

## Limits, updates and removal

No playback, sources, remote list/history writes, Real-Debrid or scrobbling are enabled.
The read-only library may read account settings/watch progress to bind and filter
rows; metadata or an upcoming date never establishes playable availability. Continue
Watching, Next aired and Upcoming remain separate future row integrations, not a
claim that the personal calendar covers all selected shows.

To update this candidate, deliberately install its new checksum-named ZIP from the
same source and restart Kodi. Changes to the public app identity use a different
local scope; they do not silently reuse or erase the old identity's credentials.
Use **Disconnect this video add-on locally** before removing it if desired; this
clears its credentials and choices, not the program/Preview profiles. Revoke app
access separately in Trakt settings if wanted. Uninstall/local disconnect does not
prove backup erasure or remote revocation. Stored tokens are unencrypted and may be
accessible to other code running as Kodi or to profile backups.

## Synopsis and Trakt rating candidate

After the metadata candidate is merged and its current Development ZIP is verified,
update from the HomeFX source and fully restart Kodi. Keep the existing login and
saved choices. Open a saved list and a movie's details: available synopsis text and
`Trakt rating: …/10 (… votes)` should appear alongside the existing unknown/known
watch state and date disclaimer. Missing optional data leaves the title browsable;
no rating is invented. Posters remain placeholders pending provider setup.

Check the same row in the existing skin; Kodi receives a named Trakt rating but the
skin chooses how to present it. Report only whether text/rating appears, navigation
works and elapsed cold/warm times—no list names, title screenshots, tokens or paths
are needed. This is a new metadata-display check, not a repeat authorization test.
