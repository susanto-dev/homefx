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

Download snapshot checked on **13 November 2026**:

- Repository installer: [repository.homefx-0.2.0.zip](https://susanto-dev.github.io/homefx/repository.homefx-0.2.0.zip).
- Video add-on: **HomeFX Preview 0.17.2**. Its separate manual download is
  [plugin.video.homefx-0.17.2.zip](https://susanto-dev.github.io/homefx/plugin.video.homefx-0.17.2.zip).

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

1. Choose **Device readiness**. Record the displayed HomeFX/repository versions and
   the fixed capability results. **Unavailable** or **not installed** is useful
   evidence; do not replace it with a guessed result. This screen makes no network
   request and does not test your account or playback.
2. Return to the HomeFX menu and choose **Test private storage**.
3. Read the confirmation. The test creates temporary synthetic SQLite files in the
   HomeFX profile, checks them and attempts cleanup. It does not read account files
   or log in. You can cancel the prompt; cancellation means the test was **not run**.
4. If you run it, record every fixed result, especially **Temporary cleanup**.
   The expected result is **passed** for private file permissions, SQLite
   commit/rollback and temporary cleanup, with **Overall: passed**.
5. If any result is unavailable, failed, unsupported or not run, report it as shown.
   If cleanup failed, report that explicitly; do not delete unfamiliar profile files
   or assume a partly successful test passed.

Safe observations to return:

- The displayed versions and fixed Device readiness capability labels/results.
- **Private file permissions**, **SQLite commit/rollback**, **Temporary cleanup**
  and **Overall**, or that you cancelled and did not run the test.
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

For an update, open **Settings → Add-ons → My add-ons → Video add-ons → HomeFX
Preview** and inspect its information/version screen. If Kodi offers **Update** or
**Versions**, select the published HomeFX repository version you intend to install.
Automatic updates depend on your Kodi settings; installing a repository is not
proof that an update happened. Review any warnings and confirm the installed
version in **Device readiness**, then fully restart Kodi and recheck saved rows.
Menu labels can vary by skin.

You normally do not need to reinstall the repository ZIP for every video add-on
update. If a new repository installer is advertised, follow its release instructions.
Do not replace a failed update with an arbitrary older ZIP: retained archives do not
establish safe rollback of every stored-data format.

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

Screenshots are a future improvement. No safe, original on-device installation
screenshots are available for this guide, and no third-party walkthrough images
or text have been copied.

- [HomeFX download page](https://susanto-dev.github.io/homefx/)
- [Source repository](https://github.com/susanto-dev/homefx)
- [Widget setup](https://github.com/susanto-dev/homefx/blob/main/docs/widget-setup.md)
- [Detailed TV acceptance checklist](https://github.com/susanto-dev/homefx/blob/main/docs/testing-on-tv.md)
- [Trakt setup and privacy gates](https://github.com/susanto-dev/homefx/blob/main/docs/account-setup.md)
- [Packaging, releases and retained versions](https://github.com/susanto-dev/homefx/blob/main/docs/releases.md)
