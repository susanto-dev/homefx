"""Kodi entry point. This preview never resolves or starts media playback."""
import sys
from pathlib import Path
from datetime import date
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
from resources.lib import catalogue as model, state, routes, readiness


def main():
    addon = xbmcaddon.Addon()
    handle = int(sys.argv[1])
    dialog = xbmcgui.Dialog()

    def message(text):
        dialog.ok("HomeFX Preview — demo only", text)

    def add(label, route, folder=True, key="", item=None, **route_params):
        li = xbmcgui.ListItem(label=label)
        li.setArt({"thumb": art_root + "poster.png", "poster": art_root + "poster.png",
                   "icon": art_root + "icon.png", "fanart": art_root + "fanart.png"})
        folder_actions = []
        if route == "list":
            for label_text, view_filter in [("All titles (demo)", "all"),
                    ("Unwatched titles (demo)", "unwatched"),
                    ("Released unwatched titles (demo)", "released_unwatched"),
                    ("Upcoming titles (demo)", "upcoming")]:
                folder_actions.append((label_text, "Container.Update(" +
                    routes.url("list", id=key, filter=view_filter) + ")"))
        if route == "show" and item is None:
            for label_text, view_filter in [("All episodes in this season (demo)", "all"),
                    ("Aired unwatched episodes in this season (demo)", "aired_unwatched")]:
                target = dict(route_params, id=key, filter=view_filter)
                folder_actions.append((label_text, "Container.Update(" + routes.url("show", **target) + ")"))
        if folder_actions:
            li.addContextMenuItems(folder_actions)
        if item:
            tag = li.getVideoInfoTag()
            tag.setTitle(item["title"])
            tag.setMediaType(item["kind"])
            tag.setPlot("Invented HomeFX demonstration title. No playable sources. "
                        + "Release/air date: " + item["date"])
            tag.setPremiered(item["date"])
            tag.setPlaycount(1 if item["watched"] else 0)
            if item["progress"]:
                tag.setResumePoint(item["progress"] * 60, 6000)
            if item["kind"] == "episode":
                tag.setSeason(item["season"])
                tag.setEpisode(item["episode"])
                tag.setTvShowTitle(item["show_title"])
            actions = [("Mark unwatched (demo)" if item["watched"] else "Mark watched (demo)",
                        "RunPlugin(" + routes.url("watched", id=key,
                            value="0" if item["watched"] else "1") + ")"),
                       ("Search this title…", "Container.Update(" +
                        routes.url("search", q=item["title"]) + ")"),
                       ("Information (demo)", "RunPlugin(" + routes.url("info", id=key) + ")")]
            if item["kind"] == "movie":
                saved = key in prefs["saved_movies"]
                actions.append(("Remove from my movie list (demo)" if saved else
                                "Add to my movie list (demo)", "RunPlugin(" +
                                routes.url("collect", id=key, value="0" if saved else "1") + ")"))
                actions.append(("Open my movie list (demo)", "Container.Update(" +
                                routes.url("list", id="saved") + ")"))
                actions.append(("Similar movies (demo)", "Container.Update(" +
                                routes.url("similar", id=key) + ")"))
            if item["kind"] in {"tvshow", "episode"}:
                show_id = key if item["kind"] == "tvshow" else item["show"]
                season_params = {"season": params["season"]} if current_route == "show" and "season" in params else {}
                actions.extend([("Browse aired unwatched episodes (demo)", "Container.Update(" +
                                 routes.url("show", id=show_id, filter="aired_unwatched", **season_params) + ")"),
                                ("Browse all episodes (demo)", "Container.Update(" +
                                 routes.url("show", id=show_id, filter="all", **season_params) + ")"),
                                ("Browse seasons (demo)", "Container.Update(" +
                                 routes.url("seasons", id=show_id) + ")")])
            if item["kind"] == "episode":
                actions.append(("Preview next-episode choice", "RunPlugin(" +
                                routes.url("sequence", id=key) + ")"))
            li.addContextMenuItems(actions)
        # Deliberately not IsPlayable: demo clicks must not invoke Kodi's player.
        # Directory-level actions have no synthetic identifier.
        target_params = dict(route_params)
        if key:
            target_params["id"] = key
        xbmcplugin.addDirectoryItem(handle, routes.url(route, **target_params), li, folder)

    try:
        route, params = routes.parse(sys.argv[2] if len(sys.argv) > 2 else "")
        current_route = route
        if route == "readiness":
            dialog.ok("HomeFX — Device readiness", readiness.report(
                lambda: addon.getAddonInfo("version"),
                lambda: xbmc.getInfoLabel("System.BuildVersion"),
                lambda: xbmcaddon.Addon("plugin.video.umbrella").getAddonInfo("version")))
            return
        if route == "playback_setup":
            message("Titles, lists and release dates are metadata, not playable sources.\n"
                    "Real-Debrid needs a separate account and a source you are authorized to access. "
                    "It is not a complete title catalogue or a source-discovery service.\n"
                    "An initial Umbrella playback handoff is unverified. "
                    "The native Real-Debrid prototype is inactive.\n"
                    "This screen does not connect accounts, resolve sources or start playback. "
                    "Never enter or share account tokens or client secrets here.")
            return
        profile = Path(xbmcvfs.translatePath(addon.getAddonInfo("profile"))) / "demo.json"
        prefs = state.load(profile)
        items = model.apply_state(model.catalogue(), prefs)
        art_root = addon.getAddonInfo("path") + "/resources/art/"
        key = params.get("id", "")
        if route == "setup":
            message("Trakt connection is not enabled in this preview.\n"
                    "The lists and watched changes remain local demonstrations.\n"
                    "Setup instructions: github.com/susanto-dev/homefx — docs/account-setup.md\n"
                    "Only a public client ID and registered redirect URI will be needed. "
                    "Never enter or share a client secret or account tokens here.")
            return
        if route in {"play", "watched", "info", "sequence", "similar", "show", "seasons", "collect"} and key not in items:
            raise ValueError("Demo title not found")
        if route in {"show", "seasons"} and items[key]["kind"] != "tvshow":
            raise ValueError("Invalid series")
        if route == "list" and key not in model.LISTS:
            raise ValueError("Invalid list")
        if route == "collect":
            if items[key]["kind"] != "movie" or params.get("value") not in {"0", "1"}:
                raise ValueError("Invalid demo movie-list action")
            saved = prefs["saved_movies"]
            if params["value"] == "1":
                if key not in saved:
                    saved.append(key)
            elif key in saved:
                if not dialog.yesno("HomeFX Preview", "Remove this movie from your local demo movie list?"):
                    return
                saved.remove(key)
            state.save(profile, prefs)
            dialog.notification("HomeFX Preview", "Local movie list updated; Trakt is not connected")
            xbmc.executebuiltin("Container.Refresh")
            return
        if route == "select":
            keys = list(model.LISTS)
            chosen = dialog.multiselect("Select demo widget lists", list(model.LISTS.values()),
                         preselect=[i for i, k in enumerate(keys) if k in prefs["selected"]])
            if chosen is not None:
                prefs["selected"] = [keys[i] for i in chosen]
                state.save(profile, prefs)
                xbmc.executebuiltin("Container.Refresh")
            return
        if route == "reset":
            if dialog.yesno("HomeFX Preview", "Reset local demo watch states, movie list and widget selection?"):
                state.save(profile, {"watched": {}, "selected": list(model.LISTS), "saved_movies": []})
                xbmc.executebuiltin("Container.Refresh")
            return
        if route == "watched":
            if params.get("value") not in {"0", "1"}:
                raise ValueError("Invalid watched state")
            prefs["watched"][key] = params["value"] == "1"
            state.save(profile, prefs)
            dialog.notification("HomeFX Preview", "Local demo updated; Trakt is not connected")
            xbmc.executebuiltin("Container.Refresh")
            return
        if route in {"play", "info"}:
            item = items[key]
            message(item["title"] + "\nRelease/air date: " + item["date"] +
                    "\n" + ("Upcoming. " if item["date"] > date.today().isoformat() else "") +
                    "A release date does not establish a playable source. "
                    "Playback needs a separate authorized source.\n"
                    "Demo only: no playback or Trakt connection.")
            return
        if route == "sequence":
            immediate, unwatched = model.continuation(items, key)
            if not immediate:
                message("No next aired episode in this demo.")
            elif immediate["watched"]:
                choices = ["Replay: " + immediate["title"]]
                if unwatched:
                    choices.append("Next aired unwatched: " + unwatched["title"])
                choices.append("Stop")
                choice = dialog.select("Preview only — no playback", choices)
                if 0 <= choice < len(choices) - 1:
                    message("Selected: " + choices[choice] + "\nNo media was started.")
            else:
                message("Would continue to: " + immediate["title"] + "\nNo media was started.")
            return
        xbmcplugin.setPluginCategory(handle, "HomeFX Preview — synthetic data")
        xbmcplugin.setContent(handle, "videos")
        if route in {"home", "widgets"}:
            for list_id in prefs["selected"]:
                add(model.LISTS[list_id], "list", key=list_id)
            for label, target in [("Continue watching (demo)", "continue"),
                                  ("Next aired unwatched episodes (demo)", "next"),
                                  ("Upcoming episodes — 7 days (demo)", "upcoming"),
                                  ("Upcoming saved movies (demo)", "upcoming_movies")]:
                add(label, target)
            if route == "home":
                add("Widget sources (demo)", "widgets")
                add("Search demo titles…", "search")
                add("Select demo widget lists…", "select", False)
                add("Trakt connection setup…", "setup", False)
                add("Playback and Real-Debrid setup…", "playback_setup", False)
                add("Device readiness", "readiness", False)
                add("Reset demo data…", "reset", False)
        elif route == "seasons":
            for summary in model.seasons(items, key):
                season = summary["season"]
                label = ("Specials" if season == 0 else "Season " + str(season))
                label += " · %d/%d watched · %d aired unwatched · %d upcoming" % (
                    summary["watched"], summary["total"], summary["aired_unwatched"], summary["upcoming"])
                add(label, "show", key=key, season=season, filter="all")
        else:
            query = params.get("q", "")
            if route == "search":
                query = dialog.input("Search synthetic titles", defaultt=query).strip()
                if not query:
                    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
                    return
            result = model.view(route, items, prefs, key, query,
                                episode_filter=params.get("filter", "all") if route == "show" else "all",
                                list_filter=params.get("filter", "all") if route == "list" else "all",
                                season=int(params["season"]) if "season" in params else None)
            if not result:
                xbmcplugin.setPluginCategory(handle, "HomeFX Preview — no matching demo titles")
            kinds = {x["kind"] for x in result}
            content = {"movie": "movies", "episode": "episodes", "tvshow": "tvshows"}
            if len(kinds) == 1:
                xbmcplugin.setContent(handle, content[next(iter(kinds))])
            for item in result:
                status = ("Watched" if item["watched"] else
                          "Upcoming" if item["date"] > date.today().isoformat() else
                          "Resume " + str(item["progress"]) + "%" if item["progress"] else "Unwatched")
                title = item["title"]
                if item["kind"] == "episode":
                    title = "S%02dE%02d · %s" % (item["season"], item["episode"], title)
                add(title + " · " + status + " · " + item["date"],
                    "show" if item["kind"] == "tvshow" else "play",
                    item["kind"] == "tvshow", item["id"], item)
        xbmcplugin.addSortMethod(handle, xbmcplugin.SORT_METHOD_NONE)
        xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
    except (ValueError, OSError):
        message("Unable to complete the demo action. Check the selected view or local profile access.")
        if handle >= 0:
            xbmcplugin.endOfDirectory(handle, succeeded=False)


if __name__ == "__main__":
    main()
