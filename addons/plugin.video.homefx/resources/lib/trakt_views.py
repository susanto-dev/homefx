"""Join separate metadata, watched and paused snapshots without playable claims.

All inputs are fabricated in tests. Metadata wrappers bind an episode collection
and watched-progress snapshot to the requested show ID. Missing watched evidence
stays unknown; it is never silently treated as unwatched.
"""
from datetime import date, datetime, time, timezone
import math

from .trakt_client import ApiError, metadata_rows

UTC = timezone.utc
MIN_TIME = datetime.min.replace(tzinfo=UTC)


def _id(row):
    ids = row.get("ids") if isinstance(row, dict) else None
    value = ids.get("trakt") if isinstance(ids, dict) else None
    return value if type(value) is int and value > 0 else None


def _stamp(value, date_only=False):
    if not isinstance(value, str):
        return None
    try:
        if date_only and len(value) == 10:
            return datetime.combine(date.fromisoformat(value), time(), UTC)
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(UTC) if result.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def _now(value):
    value = datetime.now(UTC) if value is None else value
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ApiError("invalid_clock")
    return value.astimezone(UTC)


def _pause_map(rows, kind, show_id=None):
    result = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("type") != kind:
            continue
        if kind == "episode" and _id(row.get("show")) != show_id:
            continue
        ident, progress = _id(row.get(kind)), row.get("progress")
        when = _stamp(row.get("paused_at"))
        if (ident is None or type(progress) not in (int, float) or
                not 0 < progress < 100 or not math.isfinite(progress) or when is None):
            continue
        if ident not in result or when > result[ident][1]:
            result[ident] = (progress, when)
    return result


def _row(item, kind, watched, pause, now):
    ident = _id(item)
    if not isinstance(item, dict) or ident is None or not isinstance(item.get("title"), str):
        raise ApiError("invalid_metadata")
    release = _stamp(item.get("first_aired" if kind == "episode" else "released"),
                     date_only=kind == "movie")
    progress, last_played = pause or (0, None)
    if watched is True:
        progress, last_played = 0, None
    status = "unknown_date" if release is None else "upcoming" if release > now else "aired"
    return {"id": "trakt:" + kind + ":" + str(ident), "trakt_id": ident,
            "kind": kind, "title": item["title"], "release_at": release,
            "release_status": status, "watched": watched, "progress": progress,
            "last_played": last_played,
            "aired_unwatched": status == "aired" and watched is False}


def _list_description(media):
    """Optional display data must not make an otherwise valid title unavailable.

    Only list responses already requesting extended=full supply these fields.
    Scores retain their Trakt identity and require a positive vote count.
    """
    result = {}
    tmdb_id = media.get("ids", {}).get("tmdb")
    if type(tmdb_id) is int and 1 <= tmdb_id < 2**63:
        result["tmdb_id"] = tmdb_id
    overview = media.get("overview")
    if type(overview) is str and len(overview) <= 4096 and overview.strip():
        result["overview"] = overview
    rating, votes = media.get("rating"), media.get("votes")
    if (type(rating) in (int, float) and 0 <= rating <= 10 and math.isfinite(rating)
            and type(votes) is int and 0 < votes <= 2147483647):
        result.update(trakt_rating=float(rating), trakt_votes=votes)
    return result


def browse_list(items, now=None):
    """Normalize movie/show entries in list order without inventing watch state.

    Season, episode and person entries are explicitly counted as unsupported in
    this browser. Unknown types and malformed supported rows fail the whole read.
    """
    now = _now(now)
    if not isinstance(items, list) or len(items) > 10000:
        raise ApiError("invalid_metadata")
    rows, seen, unsupported = [], set(), 0
    for item in items:
        if not isinstance(item, dict):
            raise ApiError("invalid_metadata")
        kind = item.get("type")
        if not isinstance(kind, str) or kind not in {"movie", "show", "season", "episode", "person"}:
            raise ApiError("invalid_metadata")
        if kind in {"season", "episode", "person"}:
            if _id(item.get(kind)) is None:
                raise ApiError("invalid_metadata")
            unsupported += 1
            continue
        row = metadata_rows([item], kind, wrapped=True)[0]
        identity = (kind, row["trakt_id"])
        if identity in seen:
            raise ApiError("invalid_metadata")
        seen.add(identity)
        media = item[kind]
        row.update(_list_description(media))
        release = _stamp(media.get("released" if kind == "movie" else "first_aired"),
                         date_only=kind == "movie")
        row.update(id="trakt:" + kind + ":" + str(row["trakt_id"]),
                   release_at=release,
                   release_status="unknown" if release is None else "upcoming" if release > now else "aired")
        rows.append(row)
    return {"items": rows, "unsupported_count": unsupported}


def episodes(metadata, watched_snapshot, paused=(), now=None):
    """Return season/episode order; watched progress uses show+season+number.

Pauses join by episode Trakt ID AND parent show ID, never by titles or episode
numbers alone. Watched progress takes precedence over stale pause records.
"""
    now = _now(now)
    if not isinstance(metadata, dict) or not isinstance(watched_snapshot, dict):
        raise ApiError("invalid_metadata")
    show_id = metadata.get("show_id")
    if type(show_id) is not int or show_id <= 0 or watched_snapshot.get("show_id") != show_id:
        raise ApiError("mismatched_show")
    source = metadata.get("episodes")
    snapshot = watched_snapshot.get("progress")
    if not isinstance(source, list) or not isinstance(snapshot, dict):
        raise ApiError("invalid_metadata")
    seasons = snapshot.get("seasons")
    if not isinstance(seasons, list):
        raise ApiError("invalid_progress")
    watched = {}
    for season in seasons:
        if not isinstance(season, dict) or type(season.get("number")) is not int:
            raise ApiError("invalid_progress")
        entries = season.get("episodes")
        if not isinstance(entries, list):
            raise ApiError("invalid_progress")
        for entry in entries:
            if (not isinstance(entry, dict) or type(entry.get("number")) is not int or
                    type(entry.get("completed")) is not bool):
                raise ApiError("invalid_progress")
            key = (season["number"], entry["number"])
            if key in watched:
                raise ApiError("invalid_progress")
            watched[key] = entry["completed"]
    pauses = _pause_map(paused, "episode", show_id)
    result, identifiers, numbers = [], set(), set()
    for item in source:
        if (not isinstance(item, dict) or type(item.get("season")) is not int or
                type(item.get("number")) is not int or not 0 <= item["season"] <= 10000 or not 1 <= item["number"] <= 10000):
            raise ApiError("invalid_metadata")
        key, ident = (item["season"], item["number"]), _id(item)
        if ident in identifiers or key in numbers:
            raise ApiError("duplicate_metadata")
        identifiers.add(ident)
        numbers.add(key)
        row = _row(item, "episode", watched.get(key), pauses.get(ident), now)
        row.update(show_id=show_id, season=key[0], episode=key[1])
        result.append(row)
    return sorted(result, key=lambda row: (row["season"], row["episode"]))


def episode_filter(rows, selection="all"):
    """Narrative browsing or unfinished-first aired/unwatched widget ordering."""
    if not isinstance(selection, str) or selection not in {"all", "aired_unwatched"}:
        raise ApiError("invalid_filter")
    if selection == "all":
        return sorted(rows, key=lambda row: (row["season"], row["episode"]))
    return widget_order([row for row in rows if row["aired_unwatched"]])


def _series_rows(rows):
    """Validate the identity boundary of normalized rows for one series."""
    if not isinstance(rows, list) or len(rows) > 5000:
        raise ApiError("invalid_metadata")
    show_id, identifiers, numbers = None, set(), set()
    for row in rows:
        if (not isinstance(row, dict) or row.get("kind") != "episode"
                or type(row.get("show_id")) is not int or row["show_id"] <= 0
                or type(row.get("trakt_id")) is not int or row["trakt_id"] <= 0
                or type(row.get("season")) is not int or not 0 <= row["season"] <= 10000
                or type(row.get("episode")) is not int or not 1 <= row["episode"] <= 10000
                or not (row.get("watched") is None or type(row["watched"]) is bool)
                or not isinstance(row.get("release_status"), str)
                or row["release_status"] not in {"aired", "upcoming", "unknown_date"}):
            raise ApiError("invalid_metadata")
        if show_id is not None and row["show_id"] != show_id:
            raise ApiError("mismatched_show")
        show_id = row["show_id"]
        number = (row["season"], row["episode"])
        if row["trakt_id"] in identifiers or number in numbers:
            raise ApiError("duplicate_metadata")
        identifiers.add(row["trakt_id"])
        numbers.add(number)
    return rows



def show_progress(rows, selection):
    """Separate pause, narrative-next and future metadata for one regular show.

    Upcoming preserves unknown watched state instead of claiming unwatched. A
    date or pause is metadata, never evidence of a playable source.
    """
    if type(selection) is not str or selection not in {"continue", "next", "upcoming"}:
        raise ApiError("invalid_filter")
    regular = []
    for row in _series_rows(rows):
        release, paused = row.get("release_at"), row.get("last_played")
        progress = row.get("progress")
        if (row["release_status"] != "unknown_date" and
                (not isinstance(release, datetime) or release.tzinfo is None)):
            raise ApiError("invalid_metadata")
        if (type(progress) not in (int, float) or not math.isfinite(progress)
                or not 0 <= progress <= 100 or
                (paused is not None and (not isinstance(paused, datetime) or paused.tzinfo is None))):
            raise ApiError("invalid_progress")
        if row["season"] > 0:
            regular.append(row)
    narrative = lambda row: (row["season"], row["episode"])
    if selection == "upcoming":
        return sorted((row for row in regular if row["release_status"] == "upcoming"
                       and row["watched"] is not True),
                      key=lambda row: (row["release_at"], *narrative(row)))
    aired = [row for row in regular if row["release_status"] == "aired" and row["watched"] is False]
    if selection == "next":
        return sorted(aired, key=narrative)[:1]
    unfinished = sorted((row for row in aired if 0 < row["progress"] < 100
                         and row["last_played"] is not None), key=narrative)
    return sorted(unfinished, key=lambda row: row["last_played"], reverse=True)


def season_summaries(rows):
    """Count actual normalized rows, preserving unknown watched/date evidence."""
    seasons = {}
    for row in _series_rows(rows):
        number = row["season"]
        summary = seasons.setdefault(number, dict(season=number, total=0, watched=0,
            unwatched=0, unknown_watched=0, aired_unwatched=0, upcoming=0, unknown_date=0))
        summary["total"] += 1
        state = row["watched"]
        summary["watched" if state is True else "unwatched" if state is False else "unknown_watched"] += 1
        status = row["release_status"]
        if status in {"upcoming", "unknown_date"}:
            summary[status] += 1
        elif state is False:
            summary["aired_unwatched"] += 1
    return [seasons[number] for number in sorted(seasons)]


def continuation(rows, current_id, include_specials=False):
    """Return immediate aired and next known-unwatched candidates, never play.

    Narrative season/episode order defines successors, including cross-season
    boundaries. Specials are excluded unless explicitly requested. An immediate
    candidate with unknown watched state remains unknown: callers must not infer
    automatic-play permission or a watched result from its presence.
    """
    if (type(current_id) is not int or not 1 <= current_id <= 2 ** 63 - 1
            or type(include_specials) is not bool):
        raise ApiError("invalid_identifier")
    source = _series_rows(rows)
    ordered = sorted((row for row in source if include_specials or row["season"] != 0),
                     key=lambda row: (row["season"], row["episode"]))
    matches = [index for index, row in enumerate(ordered) if row["trakt_id"] == current_id]
    if not matches:
        raise ApiError("episode_not_in_scope")
    following = [row for row in ordered[matches[0] + 1:] if row["release_status"] == "aired"]
    immediate = dict(following[0]) if following else None
    unwatched = next((dict(row) for row in following if row["watched"] is False), None)
    return immediate, unwatched


def _movie_pauses(rows, now):
    latest = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ApiError("invalid_progress")
        if row.get("type") != "movie":
            continue
        ident = _id(row.get("movie"))
        progress, when = row.get("progress"), _stamp(row.get("paused_at"))
        if (ident is None or ident >= 2**63 or type(progress) not in (int, float)
                or not 0 <= progress <= 100 or not math.isfinite(progress)
                or when is None or when > now):
            raise ApiError("invalid_progress")
        previous = latest.get(ident)
        if previous is not None and previous[1] == when and previous[0] != progress:
            raise ApiError("conflicting_progress")
        if previous is None or when > previous[1]:
            latest[ident] = progress, when
    # A newer zero/complete event supersedes an older unfinished pause.
    return {ident: value for ident, value in latest.items() if 0 < value[0] < 100}


def movies(metadata, watched_ids=None, paused=(), now=None, *, strict_pauses=False):
    """watched_ids is a complete watched snapshot, or None if not fetched.

The supplied movie release date is metadata, not regional streaming availability.
"""
    now = _now(now)
    if watched_ids is not None and (not isinstance(watched_ids, (set, frozenset)) or
                                   any(type(i) is not int or i <= 0 for i in watched_ids)):
        raise ApiError("invalid_progress")
    if type(strict_pauses) is not bool:
        raise ApiError("invalid_progress")
    pauses = _movie_pauses(paused, now) if strict_pauses else _pause_map(paused, "movie")
    basics = metadata_rows(metadata, "movie")
    result, seen = [], set()
    for item, basic in zip(metadata, basics):
        ident = _id(item)
        if ident in seen:
            raise ApiError("duplicate_metadata")
        seen.add(ident)
        watched = ident in watched_ids if watched_ids is not None else None
        row = dict(basic, **_row(item, "movie", watched, pauses.get(ident), now))
        row.update(_list_description(item))
        result.append(row)
    return result


def widget_order(rows):
    """Unfinished, aired unwatched, upcoming, unknown date/status, then watched."""
    def key(row):
        release = row["release_at"] or MIN_TIME
        if row["watched"] is True:
            return (5, -release.toordinal(), row["id"])
        if row["release_status"] == "upcoming":
            return (2, release, row["id"])
        if row["release_status"] == "unknown_date":
            return (3, MIN_TIME, row["id"])
        if row["watched"] is None:
            return (4, MIN_TIME, row["id"])
        if row["progress"] > 0:
            played = row["last_played"] or MIN_TIME
            return (0, -played.toordinal(), -played.hour, -played.minute, -played.second, row["id"])
        return (1, -release.toordinal(), -release.hour, -release.minute, -release.second, row["id"])
    return sorted(rows, key=key)


def movie_filter(rows, selection="all"):
    """Filter normalized metadata; unknown watched evidence never means unwatched.

    Callers must supply a complete watched snapshot before requesting either
    unwatched view. Empty rows alone are not evidence of such a snapshot, so the
    Library layer also rejects those views when no watched endpoint is available.
    """
    if not isinstance(selection, str) or selection not in {"all", "unwatched", "released_unwatched", "unfinished", "upcoming"}:
        raise ApiError("invalid_filter")
    if selection in {"unwatched", "released_unwatched", "unfinished"} and any(
            row["watched"] is None for row in rows):
        raise ApiError("watched_status_unavailable")
    if selection == "unwatched":
        rows = [row for row in rows if row["watched"] is False]
    elif selection == "released_unwatched":
        rows = [row for row in rows if row["aired_unwatched"]]
    elif selection == "unfinished":
        rows = [row for row in rows if row["aired_unwatched"] and row["progress"] > 0]
    elif selection == "upcoming":
        rows = [row for row in rows if row["release_status"] == "upcoming"]
    return widget_order(rows)


def continued(paused, now=None):
    """Normalize only dated, aired pause metadata; this is not a watched snapshot.

    The playback response may omit release dates. Such rows are excluded rather
    than assumed aired, so this deliberately conservative view may be incomplete.
    watched remains None: a pause proves partial progress, not current watch state.
    No external metadata lookup, source resolution or playback occurs here.
    """
    now = _now(now)
    selected = {}
    for source in paused:
        if (not isinstance(source, dict) or not isinstance(source.get("type"), str)
                or source["type"] not in {"movie", "episode"}):
            continue
        kind = source["type"]
        item, ident = source.get(kind), _id(source.get(kind))
        show_id = _id(source.get("show")) if kind == "episode" else None
        if ident is None or (kind == "episode" and show_id is None):
            continue
        pause = _pause_map([source], kind, show_id).get(ident)
        if pause is None or pause[1] > now:
            continue
        try:
            row = _row(item, kind, None, pause, now)
        except ApiError:
            continue
        if row["release_status"] != "aired":
            continue
        if kind == "episode":
            if any(type(item.get(key)) is not int or not 0 <= item[key] <= 10000
                   for key in ("season", "number")):
                continue
            row.update(show_id=show_id, season=item["season"], episode=item["number"])
        key = (kind, ident)
        previous = selected.get(key)
        if previous is not None and kind == "episode" and previous["show_id"] != show_id:
            raise ApiError("mismatched_show")
        if previous is None or row["last_played"] > previous["last_played"]:
            selected[key] = row
    # Sort by exact UTC instant, retaining stable global identity for equal dates.
    rows = sorted(selected.values(), key=lambda row: row["id"])
    return sorted(rows, key=lambda row: row["last_played"], reverse=True)
