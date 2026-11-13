"""Bounded, encoded plugin routes; no network or arbitrary command inputs."""
import re
from urllib.parse import parse_qs, urlencode

BASE = "plugin://plugin.video.homefx/"
ROUTES = {"home", "list", "show", "continue", "next", "upcoming", "search",
          "similar", "play", "watched", "select", "reset", "info", "sequence", "setup",
          "collect", "readiness", "widgets", "seasons", "upcoming_movies", "playback_setup", "widget_setup"}
LIST_FILTERS = {"all", "unwatched", "released_unwatched", "upcoming"}


def url(route, **params):
    if route not in ROUTES:
        raise ValueError("Unknown route")
    return BASE + "?" + urlencode(dict(route=route, **params))


def parse(query):
    if not isinstance(query, str) or len(query) > 4096:
        raise ValueError("Invalid route")
    data = parse_qs(query.lstrip("?"), max_num_fields=12, keep_blank_values=True)
    if any(len(values) != 1 for values in data.values()):
        raise ValueError("Duplicate route parameter")
    if set(data) - {"route", "id", "q", "value", "filter", "season"}:
        raise ValueError("Unknown route parameter")
    route = data.get("route", ["home"])[0]
    if route not in ROUTES:
        raise ValueError("Unknown route")
    params = {key: values[0] for key, values in data.items() if key != "route"}
    # Older previews emitted an empty id even for directory-level routes. Keep
    # saved widget URLs working, without accepting absent IDs on title routes.
    if params.get("id") == "" and route in {
            "home", "continue", "next", "upcoming", "search", "select", "reset",
            "setup", "readiness", "widgets", "upcoming_movies", "playback_setup", "widget_setup"}:
        del params["id"]
    if route == "widget_setup" and params:
        raise ValueError("Unexpected widget setup parameter")
    if "filter" in params:
        choices = {"all", "aired_unwatched"} if route == "show" else LIST_FILTERS if route == "list" else set()
        if params["filter"] not in choices:
            raise ValueError("Invalid view filter")
    if "season" in params and (route != "show" or not re.fullmatch(r"(?:0|[1-9][0-9]{0,2})", params["season"])):
        raise ValueError("Invalid season")
    if "id" in params and not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", params["id"]):
        raise ValueError("Invalid title identifier")
    if "q" in params and (route != "search" or len(params["q"]) > 256 or
                          any(ord(c) < 32 for c in params["q"])):
        raise ValueError("Invalid search query")
    if "value" in params and (route not in {"watched", "collect"} or params["value"] not in {"0", "1"}):
        raise ValueError("Invalid action value")
    return route, params
