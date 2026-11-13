# Widget setup with your existing skin

Keep the installed skin. HomeFX supplies folders of titles; the skin controls row
layout, focus, widget headings and shortcuts. These instructions describe the
synthetic preview. They do not connect Trakt, start playback or establish a successful
TV integration.

Selecting lists in HomeFX and assigning rows in the skin are **two separate steps**.
HomeFX selection does not create, remove or rearrange skin rows. Keep saved widget
routes when upgrading and verify them before recreating shortcuts. The full-list
folder in HomeFX is always the intended fallback when a skin heading cannot open;
a menu/submenu shortcut can point to that same folder.

1. Install the HomeFX repository, then the video add-on using the
   [repository instructions](releases.md). Open **Device readiness** in HomeFX.
   Record HomeFX and HomeFX repository versions. **Not installed** means Kodi's
   local presence check returned false; **unavailable** means the check or version
   could not be validated. Neither a version nor presence proves updates work.
2. Open **Select demo widget lists** and choose the lists you want. Open **Widget
   sources** to check the available list folders and progress/upcoming views.
3. In the skin's home-menu/widget configuration, browse Video add-ons → HomeFX
   Preview → Widget sources, then select a list folder as one widget's source.
   Repeat for other lists or Continue watching, Next aired unwatched episodes and
   Upcoming episodes. The actual setting names depend on the installed skin.
4. Choose the skin's poster/thumbnail presentation if available. Every preview
   title uses original placeholder artwork. Selecting a movie/episode thumbnail
   shows demo information; selecting a series opens its episode folder.
5. To open the complete list, browse its folder inside HomeFX or create a separate
   menu/submenu shortcut to that folder. A clickable widget heading is a skin
   capability, not something HomeFX can assume. Record the observed behavior.
6. Use the remote context/menu action (often long-press OK) on a title for local
   watched changes, search, information and similar movies. These changes stay
   local to the demo. Refresh the widget if its contents do not update immediately.

**Widget setup** in the HomeFX root provides a shorter two-page guide on the TV.
It does not read profiles or account configuration. Setup/help rows stay out of
Widget sources and title-list results.

Use the [TV acceptance checklist](testing-on-tv.md) to record navigation, Back,
focus, title versus heading clicks, multiple rows, empty views and cold/warm load
behavior. Do not send a complete Kodi backup, account tokens or unredacted logs.
Real account lists and playback need separate activation and acceptance tests.

The local repository-presence check uses Kodi 21.2's documented
[`System.HasAddon(id)` condition](https://github.com/xbmc/xbmc/blob/21.2-Omega/xbmc/GUIInfoManager.cpp#L1996).
It reports installation, not whether the repository is enabled, current or reachable.

## Read-only list journey acceptance

The current public preview remains synthetic. After the [account activation
gates](account-setup.md), check a personal list and a liked list separately: select
them in HomeFX, assign each folder to a skin row, browse title and season details,
then restart Kodi and confirm selections and widget shortcuts persist. Cancelling
a list-selection dialog must retain the previous choices. An empty successful list,
a loading operation, offline failure and authorization-needed state must be visibly
distinct; failure must not masquerade as an empty list or another account's cached
results. These are pending device acceptance checks, not a claim of live wiring.

Keep **Continue watching** (unfinished progress), **Next aired unwatched episodes**
(aired candidates established as unwatched) and **Upcoming** (future date metadata)
as separate views. A date does not establish a playable source. Trakt's personal
calendar covers watched/watchlisted shows and individually watchlisted episodes,
excluding hidden shows; it does not cover every show in arbitrary selected lists.
See [calendar contracts](calendar-contract.md) and the [staged TV checklist](testing-on-tv.md).
