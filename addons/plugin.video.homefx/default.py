"""Kodi entry point. This preview never resolves or starts media playback."""
import sys
from pathlib import Path
from datetime import date
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs
from resources.lib import catalogue as model, state, routes


def main():
    addon = xbmcaddon.Addon()
    handle = int(sys.argv[1])
    profile = Path(xbmcvfs.translatePath(addon.getAddonInfo("profile"))) / "demo.json"
    prefs = state.load(profile)
    items = model.apply_state(model.catalogue(), prefs)
    dialog = xbmcgui.Dialog()
    art_root = addon.getAddonInfo("path") + "/resources/art/"

    def message(text):
        dialog.ok("HomeFX Preview — demo only", text)

    def add(label, route, folder=True, key="", item=None):
        li = xbmcgui.ListItem(label=label)
        li.setArt({"thumb": art_root + "poster.png", "poster": art_root + "poster.png",
                   "icon": art_root + "icon.png", "fanart": art_root + "fanart.png"})
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
                actions.append(("Similar movies (demo)", "Container.Update(" +
                                routes.url("similar", id=key) + ")"))
            if item["kind"] == "episode":
                actions.append(("Preview next-episode choice", "RunPlugin(" +
                                routes.url("sequence", id=key) + ")"))
            li.addContextMenuItems(actions)
        # Deliberately not IsPlayable: demo clicks must not invoke Kodi's player.
        xbmcplugin.addDirectoryItem(handle, routes.url(route, id=key), li, folder)

    try:
        route, params = routes.parse(sys.argv[2] if len(sys.argv) > 2 else "")
        key = params.get("id", "")
        if route in {"play", "watched", "info", "sequence", "similar", "show"} and key not in items:
            raise ValueError("Demo title not found")
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
            if dialog.yesno("HomeFX Preview", "Reset local demo watch states and list selection?"):
                state.save(profile, {"watched": {}, "selected": list(model.LISTS)})
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
        if route == "home":
            for list_id in prefs["selected"]:
                add(model.LISTS[list_id], "list", key=list_id)
            for label, target in [("Continue watching (demo)", "continue"),
                                  ("Next aired unwatched episodes (demo)", "next"),
                                  ("Upcoming episodes — 7 days (demo)", "upcoming")]:
                add(label, target)
            add("Search demo titles…", "search")
            add("Select demo widget lists…", "select", False)
            add("Reset demo data…", "reset", False)
        else:
            query = params.get("q", "")
            if route == "search":
                query = dialog.input("Search synthetic titles", defaultt=query).strip()
                if not query:
                    xbmcplugin.endOfDirectory(handle, succeeded=True, cacheToDisc=False)
                    return
            result = model.view(route, items, prefs, key, query)
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
    except (ValueError, OSError) as exc:
        message("Unable to complete the demo action: " + str(exc))
        if handle >= 0:
            xbmcplugin.endOfDirectory(handle, succeeded=False)


if __name__ == "__main__":
    main()
