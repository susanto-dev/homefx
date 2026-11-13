# Widget setup with your existing skin

Keep the installed skin. HomeFX supplies folders of titles; the skin controls row
layout, focus, widget headings and shortcuts. These instructions describe the
synthetic preview. They do not connect Trakt, start playback or establish a successful
TV integration.

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
