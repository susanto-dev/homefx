"""Join separate metadata, watched and paused snapshots without playable claims.

All inputs are fabricated in tests. Metadata wrappers bind an episode collection
and watched-progress snapshot to the requested show ID. Missing watched evidence
stays unknown; it is never silently treated as unwatched.
"""
from datetime import date, datetime, time, timezone
import math

from .trakt_client import ApiError

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
    value = value or datetime.now(UTC)
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
                not math.isfinite(progress) or not 0 < progress < 100 or when is None):
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
                type(item.get("number")) is not int or item["season"] < 0 or item["number"] < 0):
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


def movies(metadata, watched_ids=None, paused=(), now=None):
    """watched_ids is a complete watched snapshot, or None if not fetched.

The supplied movie release date is metadata, not regional streaming availability.
"""
    now = _now(now)
    if watched_ids is not None and (not isinstance(watched_ids, (set, frozenset)) or
                                   any(type(i) is not int or i <= 0 for i in watched_ids)):
        raise ApiError("invalid_progress")
    pauses = _pause_map(paused, "movie")
    result, seen = [], set()
    for item in metadata:
        ident = _id(item)
        if ident in seen:
            raise ApiError("duplicate_metadata")
        seen.add(ident)
        watched = ident in watched_ids if watched_ids is not None else None
        result.append(_row(item, "movie", watched, pauses.get(ident), now))
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
