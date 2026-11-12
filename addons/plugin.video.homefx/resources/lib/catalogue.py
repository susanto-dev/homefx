"""Invented catalogue. Dates are relative so the preview remains useful."""
from datetime import date, timedelta

LISTS = {"weekend": "Weekend movies (demo)", "discover": "Discover (demo)",
         "series": "My series (demo)", "saved": "My movie list (demo)"}
MEMBERS = {"weekend": ["m1", "m2", "m3", "m4"],
           "discover": ["m2", "m5", "s1"], "series": ["s1"]}


def catalogue(today=None):
    today = today or date.today()
    def item(key, title, kind, days, **extra):
        return dict(id=key, title=title, kind=kind,
                    date=(today + timedelta(days=days)).isoformat(),
                    watched=False, progress=0, last_played="", **extra)
    movies = [item("m1", "The Lantern Harbour", "movie", -100),
              item("m2", "A Map of Quiet Stars", "movie", -8),
              item("m3", "Tomorrow's Orchard", "movie", 30),
              item("m4", "The Last Paper Boat", "movie", -40),
              item("m5", "Beyond the Blue Window", "movie", -20)]
    movies[0].update(progress=42, last_played="2026-01-03T20:00:00")
    movies[3]["watched"] = True
    show = item("s1", "Signals from the Garden", "tvshow", -35)
    episodes = [item("e" + str(n), title, "episode", days,
                     show="s1", show_title=show["title"], season=1, episode=n)
                for n, title, days in [(1, "The First Signal", -28),
                                        (2, "A Door in the Rain", -21),
                                        (3, "The Familiar Path", -14),
                                        (4, "An Unopened Letter", -7),
                                        (5, "Tomorrow's Visitor", 3),
                                        (6, "The Long Summer", 14)]]
    episodes[0]["watched"] = True
    episodes[1].update(progress=35, last_played="2026-01-04T20:00:00")
    episodes[2]["watched"] = True
    return {x["id"]: x for x in movies + [show] + episodes}


def apply_state(items, state):
    result = {key: dict(value) for key, value in items.items()}
    for key, watched in state.get("watched", {}).items():
        if key in result and isinstance(watched, bool):
            result[key].update(watched=watched, progress=0, last_played="")
    return result


def ordered(items, today=None):
    """Widget groups: unfinished, released unwatched, upcoming, watched."""
    today = (today or date.today()).isoformat()
    def key(x):
        if x["watched"]:
            return (3, -date.fromisoformat(x["date"]).toordinal())
        if x["date"] > today:
            return (2, date.fromisoformat(x["date"]).toordinal())
        if x["progress"] > 0:
            return (0, -date.fromisoformat(x["last_played"][:10]).toordinal())
        return (1, -date.fromisoformat(x["date"]).toordinal())
    return sorted(items, key=key)


def _aired(item, today):
    try:
        released = date.fromisoformat(item.get("date", ""))
    except (TypeError, ValueError):
        return False
    return released <= today


def view(route, items, state, key="", query="", today=None, episode_filter="all"):
    today = today or date.today()
    values = list(items.values())
    if route == "list":
        if key == "saved":
            saved = state.get("saved_movies", [])
            return ordered([item for ident, item in items.items()
                            if ident in saved and item["kind"] == "movie"], today)
        return ordered([items[i] for i in MEMBERS.get(key, [])], today)
    if route == "show":
        if episode_filter not in {"all", "aired_unwatched"}:
            raise ValueError("Unknown episode filter")
        return sorted([x for x in values if x.get("show") == key and
                       (episode_filter == "all" or (not x["watched"] and _aired(x, today)))],
                      key=lambda x: (x["season"], x["episode"]))
    if route == "continue":
        return ordered([x for x in values if x["progress"] > 0 and not x["watched"]
                        and x["date"] <= today.isoformat()], today)
    if route == "next":
        # One next aired unwatched episode per show, in narrative order.
        result = []
        for show in [x for x in values if x["kind"] == "tvshow"]:
            candidates = [x for x in view("show", items, state, show["id"])
                          if not x["watched"] and x["date"] <= today.isoformat()]
            if candidates:
                result.append(candidates[0])
        return ordered(result, today)
    if route == "upcoming":
        end = (today + timedelta(days=7)).isoformat()
        return sorted([x for x in values if x["kind"] == "episode"
                       and today.isoformat() < x["date"] <= end], key=lambda x: x["date"])
    if route == "search":
        return [x for x in values if query.casefold() in x["title"].casefold()]
    if route == "similar":
        # Explicit fictional relevance order; no recommendation provider yet.
        ids = {"m1": ["m5", "m2"], "m2": ["m1", "m5"],
               "m3": ["m2", "m1"], "m4": ["m1", "m5"], "m5": ["m1", "m2"]}
        return [items[i] for i in ids.get(key, [])]
    return []


def continuation(items, current_id, today=None):
    current = items[current_id]
    episodes = view("show", items, {}, current.get("show", ""))
    after = [x for x in episodes if (x["season"], x["episode"]) >
             (current.get("season", 0), current.get("episode", 0))]
    if not after or after[0]["date"] > (today or date.today()).isoformat():
        return None, None
    immediate = after[0]
    unwatched = next((x for x in after if not x["watched"] and
                     x["date"] <= (today or date.today()).isoformat()), None)
    return immediate, unwatched
