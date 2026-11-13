# Install HomeFX on Android or Google TV

HomeFX adds folders and home-screen widget sources to Kodi. It runs alongside your
existing skin and add-ons; you do not need to replace them or install a separate
server or Android app.

**This is a preview with invented demo titles. It is not a complete live playback
product.** Trakt login, real personal lists, Real-Debrid, playable sources and
scrobbling are not enabled. Selecting a movie or episode shows demo information;
it does not play a video. Local watched changes do not update Trakt.

Installation and the skin steps below have **not been validated on a real TV**.
Published-file checks establish that downloads are available and match the release
inventory, not that Kodi installation or widgets work on your device.

Jump to [installation](#2-add-the-homefx-source-in-kodi),
[first-use checks](#5-run-the-first-use-checks),
[widgets](#6-put-a-demo-list-on-your-existing-home-screen),
[updates and removal](#7-update-or-uninstall), or
[troubleshooting](#8-if-something-goes-wrong).

## 1. Before you begin

You need:

- Android TV or Google TV with **Kodi 21.2** already installed, a working remote,
  internet access and enough free storage for an add-on installation.
- Access to Kodi settings. The wording or position of settings can vary with your skin.
- Your existing skin. The widget example targets **Arctic Zephyr Reloaded 3.0.3**
  with **Vertical Multi Widget Netflix**; HomeFX does not install or distribute it.

You do not need a Trakt or Real-Debrid account to try this preview. Do not enter
account credentials or tokens into the File manager source or a plugin URL.

The official **HomeFX project source** is:

[https://susanto-dev.github.io/homefx/](https://susanto-dev.github.io/homefx/)

Download snapshot checked on **13 November 2026**, after PR #31 merged. All 48
hosted files matched the verified publication artifact; this is download integrity,
not TV acceptance:

- Repository installer: [repository.homefx-0.2.0.zip](https://susanto-dev.github.io/homefx/repository.homefx-0.2.0.zip).
- Video add-on: **HomeFX Preview 0.17.4**. Its separate manual download is
  [plugin.video.homefx-0.17.4.zip](https://susanto-dev.github.io/homefx/repository/plugin.video.homefx/plugin.video.homefx-0.17.4.zip).

Start with the **repository ZIP**, not the video ZIP. The repository is Kodi's
installation and update source for HomeFX. Later releases may advertise a newer
video version; check the [download page](https://susanto-dev.github.io/homefx/)
for the current published version. HomeFX is a third-party project, not an official
Kodi repository.

## 2. Add the HomeFX source in Kodi

1. Open Kodi and go to **Settings → File manager**.
2. Choose **Add source**. If necessary, open the entry marked **None** to edit the address.
3. Enter exactly `https://susanto-dev.github.io/homefx/`, including `https://` and
   the final `/`. Confirm with **OK**.
4. Give the source a name such as **HomeFX**, then confirm the source with **OK**.
5. Return to Kodi's home screen. Adding a source only saves its address; it has not
   installed an add-on yet.

If Kodi cannot reach the source, stop here and use the troubleshooting section
below. Do not replace HTTPS with HTTP or accept a certificate warning to continue.

## 3. Install the repository, then HomeFX Preview

1. Open **Add-ons** and its package-browser control, usually the open-box icon.
   You can also reach the add-on browser through **Settings → Add-ons**.
2. Choose **Install from zip file**.
3. Kodi may say that installing add-ons from unknown sources is disabled. This
   warning means the ZIP is outside Kodi's official repository. Only continue if
   you have checked the HomeFX address and trust the project and its code.
4. If you choose to allow this installation, open **Settings → System → Add-ons →
   Unknown sources** and read Kodi's warning before confirming. Then return to
   **Install from zip file**. Do not enable the setting merely to dismiss an
   unexpected warning from an unfamiliar source.
5. Select **HomeFX**, then **repository.homefx-0.2.0.zip**. Wait for Kodi's
   repository-installed notification. Do not select the similarly listed video ZIP.
6. Choose **Install from repository → HomeFX Preview Repository → Video add-ons →
   HomeFX Preview → Install**. Review the add-on information and any installation
   confirmation Kodi presents. Wait for the installation notification.
7. Return to the add-ons screen. **HomeFX Preview** should now be under
   **Video add-ons**. A repository-installed notification alone does not mean the
   video add-on is installed.

You can turn **Unknown sources** off again after installation if that is your
preferred policy. A future manual ZIP installation may require reviewing and
allowing it again.

If Kodi's source listing does not show the repository ZIP, download that exact
repository ZIP from the link above on a phone or computer and transfer it to the
TV using a method you trust. In **Install from zip file**, browse to the transferred
file. This is a fallback for the file listing, not a reason to install a different
ZIP or bypass a validation error. Checksums are available on the download page;
see [release and integrity details](https://github.com/susanto-dev/homefx/blob/main/docs/releases.md).

## Optional Development account test

HomeFX Preview remains synthetic. The separate **HomeFX Development Test** is only
for the bounded account test after its readiness gates are met; it is not needed to
install the preview or use demo widgets. The hosted source ZIP and installation path have been verified, and the owner
reported authorization and refresh success in this separate test. These results
do not activate real lists in the video preview.

Choose **Add-ons → Install from zip file → HomeFX →
script.homefx.development-0.1.0-<SHA-256>.zip**, then open **Program add-ons → HomeFX
Development Test**. No download to a phone or transfer to the TV is required. Start
with **Test this add-on's private storage**. Follow the
[Development test guide](https://github.com/susanto-dev/homefx/blob/main/docs/development-device-test.md)
for the exact current filename, privacy limits and remaining steps. This direct ZIP
is separate from the repository index and does not receive repository auto-updates.
Installing it does not start login or enable live features in HomeFX Preview.
Already connected? Follow the [post-login checklist](https://github.com/susanto-dev/homefx/blob/main/docs/development-device-test.md#after-successful-authorization-and-refresh).
The separate program is a temporary validation tool; the intended everyday
list/widget experience belongs in the video add-on, with its own account storage.

## 4. Restart Kodi fully

Do this after installing or updating HomeFX, before the first-use checks.

1. Finish any open dialog. Open Kodi's power menu and choose **Exit** if available.
2. Wait for Kodi to close, then launch it again from the TV's app launcher.
3. If Exit is unavailable or Kodi has not closed, go to the TV's Android/Google TV
   **Settings → Apps → Kodi**. You may need **See all apps** first. Choose
   **Force stop**, confirm, then open Kodi again. Menu wording varies by device.

Pressing the remote's Home button, switching apps or putting the TV to sleep may
leave Kodi running. **Do not choose Clear data or Clear storage** to restart it:
those actions can remove Kodi configuration and other add-ons' data.

## 5. Run the first-use checks

Open **Add-ons → Video add-ons → HomeFX Preview**. Its root menu contains both checks.

The published 0.17.3 reports are scrollable. The TV result now identifies
**directory permissions** as the failure stage, with cleanup passed and SQLite
not run. The underlying filesystem cause is still unknown. **0.17.4 is a candidate,
not yet a verified download**; use the published snapshot above until its merge
and publication are verified. A screen showing only some fields is incomplete
evidence; do not guess the hidden results.

1. Choose **Device readiness**. Record the displayed HomeFX/repository versions and
   the fixed capability results. **Unavailable** or **not installed** is useful
   evidence; do not replace it with a guessed result. This screen makes no network
   request and does not test your account or playback.
2. Return to the HomeFX menu and choose **Test private storage**.
3. Read the confirmation. The test creates temporary synthetic SQLite files in the
   HomeFX profile, checks them and attempts cleanup. It does not read account files
   or log in. You can cancel the prompt; cancellation means the test was **not run**.
4. If you run it, record every fixed result, especially **Temporary cleanup**.
   Scroll through the report and include **Failure stage**. On 0.17.4, also
   include **Directory check**, which describes the initial directory setup.
   The expected result is **passed** for private file permissions, SQLite
   commit/rollback and temporary cleanup, with **Overall: passed**.
5. If any result is unavailable, failed, unsupported or not run, report it as shown.
   If cleanup failed, report that explicitly; do not delete unfamiliar profile files
   or assume a partly successful test passed. Do not change permissions or clear
   Kodi data to try to make a result pass.

Safe observations to return:

- The displayed versions and fixed Device readiness capability labels/results.
- **Private file permissions**, **SQLite commit/rollback**, **Temporary cleanup**
  and **Overall**, plus **Failure stage** and **Directory check** where available,
  or that you cancelled
  and did not run the test.
- Whether installation/update, opening HomeFX, Back and restart worked.
- Approximate first-open and immediate-reopen times, if measured.

**Do not share tokens, client secrets, device codes, profile paths, private lists,
watch history, full Kodi backups or unredacted logs.** No screenshot is required.
A storage pass is not proof that live Trakt, TLS, playback or every Android storage
operation works. See the [detailed TV checklist](https://github.com/susanto-dev/homefx/blob/main/docs/testing-on-tv.md).

## 6. Put a demo list on your existing home screen

The following is an **unverified setup path** for Arctic Zephyr Reloaded 3.0.3 and
Vertical Multi Widget Netflix. The exact skin settings and heading behavior still
need a real-TV check; keep your current layout and other widget sources.

### Choose lists in HomeFX

1. In HomeFX Preview, open **Select demo widget lists**.
2. Select one or two lists and confirm. Cancelling keeps your previous choices.
3. Open **Widget sources** and browse the selected list folders to check them.

This selection controls HomeFX's offered lists. **It does not create a skin row.**

### Assign a row in the skin

1. Open your skin's settings for editing the home menu and its widgets. Find the
   widget source selector for the home-menu item you want to use. Exact labels
   vary; this guide does not assume a tested sequence of Arctic settings screens.
2. Add a row or edit a row you are willing to change. Browse **Video add-ons →
   HomeFX Preview → Widget sources**, then choose the desired demo list folder.
3. If offered, choose the skin's poster/thumbnail presentation. Save the skin change
   and return to the home screen.
4. Repeat for another selected list. You can assign **Continue watching**, **Next
   aired unwatched episodes** and **Upcoming episodes** as separate rows too.
5. Check focus, scrolling, Back and the position you return to. Restart Kodi and
   check that the HomeFX selections and skin rows remain.

These rows contain **demo data**, not your real Trakt lists. Movies and episodes
open information; a show opens its episode folder. All titles use original
placeholder artwork. Upcoming dates do not guarantee playable availability.

A widget heading may not be clickable. To browse the full list, open its folder
inside HomeFX, or assign that folder to a separate skin menu/submenu shortcut if
supported. Do not assume selecting a list in HomeFX also creates this shortcut.

For more detail, see [widget setup](https://github.com/susanto-dev/homefx/blob/main/docs/widget-setup.md).
Future real Trakt lists require the separate
[account activation steps](https://github.com/susanto-dev/homefx/blob/main/docs/account-setup.md);
creating an application or passing the configuration preflight does not activate
login in this preview.

## 7. Update or uninstall

The repository and video add-on have independent versions. Repository **0.2.0**
is still current; it does not need a new version or a fresh ZIP installation every
time the video add-on changes. Keep **HomeFX Preview Repository** installed and
enabled. Installing only a video ZIP does not install the repository.

Automatic updates are not an immediate push from the download site. Kodi 21.2's
[default repository recheck interval is 24 hours](https://github.com/xbmc/xbmc/blob/d1a1d48c3cb3722d39264ffdd8132f755ffecd27/xbmc/addons/Repository.cpp#L184).
The interval is not a promise that an update will install within 24 hours: Kodi must
be running, the repository must be reachable, and update settings/rules must allow it.

If an expected update has not appeared:

1. Confirm **HomeFX Preview Repository** is installed and enabled under **My add-ons
   → Add-on repository**.
2. Check **Settings → System → Add-ons → Updates**. Choose **Install updates
   automatically** if that is your preferred policy; a notification-only setting
   requires you to install the offered update yourself.
3. Open **My add-ons → Video add-ons → HomeFX Preview** and check its **Auto-update**
   control. Keep it enabled if you want automatic updates.
4. In Kodi's add-on browser, choose **Check for updates** and wait for the refresh.
   Menu locations and labels may differ in your skin. This requests a refresh;
   it is not proof that installation completed.
5. Open HomeFX Preview's **Versions** or **Update** screen. Choose the latest
   published version explicitly labelled **HomeFX Preview Repository**. Review any
   confirmation, wait for completion, fully restart Kodi, then confirm the installed
   version in **Device readiness**. Recheck saved widget rows.

A manual video-ZIP install can leave Kodi without a repository origin for that
installation; Kodi also maintains update pin rules. This follows Kodi's
[ZIP installation path](https://github.com/xbmc/xbmc/blob/d1a1d48c3cb3722d39264ffdd8132f755ffecd27/xbmc/addons/AddonInstaller.cpp#L409)
and [origin/update-rule handling](https://github.com/xbmc/xbmc/blob/d1a1d48c3cb3722d39264ffdd8132f755ffecd27/xbmc/addons/AddonInstaller.cpp#L823),
not an inspection of your TV's database. Selecting the latest version from the
HomeFX repository is the supported recovery path to try; do not assume the manual
ZIP has preserved the previous repository association. Record the version/source
shown, whether refresh found an update, and whether installation succeeded. Actual
automatic update behavior still needs a later repository-delivered release to test.

If the HomeFX repository version is absent after refresh, stop and report the fixed
error category or missing entry. Do not broaden trust to every repository, edit
Kodi's add-on database, uninstall unrelated add-ons, or clear Kodi data to force it.
Do not choose an arbitrary older ZIP: retained archives do not establish safe
rollback of every stored-data format. If a new repository installer is advertised,
follow that release's instructions.

To remove HomeFX, first remove any HomeFX widget/menu shortcuts you no longer want.
Open its add-on information screen and choose **Uninstall**. Review Kodi's question
about removing related data/settings before answering. If you no longer want the
update source, separately uninstall **HomeFX Preview Repository** under **My add-ons
→ Add-on repository**. Removing only the repository does not remove the video add-on.
Removing the File manager source only removes that saved address.

Uninstalling is not a guarantee of profile-data erasure or remote account revocation.
Keep your skin and unrelated add-ons installed; do not reset Kodi or clear all app
data merely to remove HomeFX.

## 8. If something goes wrong

**The source cannot be opened:** check the exact HTTPS address, TV network connection,
and date/time. Open the HomeFX download page on your phone to help distinguish a
site problem from a TV connection problem. If a certificate or security warning
appears, stop and investigate it; do not disable certificate checking.

**The ZIP is missing or cannot be installed:** confirm that it is
`repository.homefx-0.2.0.zip`, not the video ZIP or a renamed web page. Check free
storage and the download page. For a failed/partial download, download the same
verified file again. If Kodi reports a dependency, integrity or compatibility
failure, retain the fixed error category and stop; do not edit the ZIP or suppress
the check. The manual transfer fallback is described in step 3.

**The repository is installed but HomeFX is absent:** use **Install from repository**
and open **HomeFX Preview Repository → Video add-ons**. Confirm you completed the
video add-on installation and that the repository is enabled. A stale listing or
network failure may require refreshing Kodi's add-on listing or reopening Kodi;
record what you observed instead of assuming installation succeeded.

**A widget is missing or empty:** first open the list inside HomeFX. Check both
HomeFX list selection and the skin's row assignment. A filtered or empty local
movie list can legitimately have no titles. Refresh the row or restart Kodi if
needed, and note whether the skin retains stale content. No real Trakt list is
expected in this preview.

**A storage check fails or a local edit reports failure:** report the fixed result,
including cleanup, and whether the issue persists after a full restart. Do not
upload databases, change profile permissions blindly or share a full backup.

Use the [TV checklist](https://github.com/susanto-dev/homefx/blob/main/docs/testing-on-tv.md)
for safe observations and [release documentation](https://github.com/susanto-dev/homefx/blob/main/docs/releases.md)
for update/integrity details. Record unsupported or untested behavior as such;
cloud tests and download checks are not device acceptance.

## 9. Screenshots and further reading

Installation screenshots are a future improvement. No original installation
screenshots have been prepared for publication in this guide; private diagnostic
images are not embedded. No third-party walkthrough images or text have been copied.

- [HomeFX download page](https://susanto-dev.github.io/homefx/)
- [Source repository](https://github.com/susanto-dev/homefx)
- [Widget setup](https://github.com/susanto-dev/homefx/blob/main/docs/widget-setup.md)
- [Detailed TV acceptance checklist](https://github.com/susanto-dev/homefx/blob/main/docs/testing-on-tv.md)
- [Trakt setup and privacy gates](https://github.com/susanto-dev/homefx/blob/main/docs/account-setup.md)
- [Packaging, releases and retained versions](https://github.com/susanto-dev/homefx/blob/main/docs/releases.md)
