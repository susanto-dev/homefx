# One real Trakt list in Development Video

**Candidate, not yet published.** This is an intentionally installed read-only
Development video add-on for the app owner or invited Development users. It is not
general public Trakt access and does not activate HomeFX Preview. No paid service,
Production registration, server or Android app is introduced.

## Delivery and approval

The existing checked Pages build uses the GitHub **Development** public client ID
and registered redirect. It builds `plugin.video.homefx.development` from the same
shared runtime as HomeFX Preview, with a small video entry point. The program test
add-on is not a dependency. Public configuration is downloadable; no secret or user
token is embedded, requested by a build, or used in CI.

The intended source remains `https://susanto-dev.github.io/homefx/`. After this
candidate merges and normal publication/hosted-byte verification passes, the source
will list `plugin.video.homefx.development-0.1.0-<SHA-256>.zip` and its checksum.
The landing page will show the exact verified filename. This guide does not claim
that the new ZIP is already hosted. No independent deployment is required.

Merging the reviewed PR approves distribution of this explicitly labelled candidate.
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

## Smallest TV checklist

No previously passed program test needs repeating. These checks exercise a new video
profile, entry point and real-list route, which have not been validated on TV.

1. **Install only after publication is verified.** In Kodi choose Add-ons → Install
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
