"""Bounded, encoded plugin routes; no network or arbitrary command inputs."""
from urllib.parse import parse_qs, urlencode

BASE = "plugin://plugin.video.homefx/"
ROUTES = {"home", "list", "show", "continue", "next", "upcoming", "search",
          "similar", "play", "watched", "select", "reset", "info", "sequence"}


def url(route, **params):
    if route not in ROUTES:
        raise ValueError("Unknown route")
    return BASE + "?" + urlencode(dict(route=route, **params))


def parse(query):
    if len(query) > 4096:
        raise ValueError("Route too long")
    data = parse_qs(query.lstrip("?"), max_num_fields=12)
    route = data.get("route", ["home"])[0]
    if route not in ROUTES:
        raise ValueError("Unknown route")
    return route, {k: v[0] for k, v in data.items() if k in {"id", "q", "value"}}
