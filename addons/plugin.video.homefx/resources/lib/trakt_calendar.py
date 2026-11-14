"""Bounded personal-calendar projection; no player or persistent cache.

A personal calendar is the service's calendar scope, not a catalogue of every show
in selected or liked lists. Optional show filtering only intersects that response.
"""
from datetime import datetime, time, timedelta, timezone
import unicodedata

from .trakt_client import ApiError, calendar_arguments, metadata_id

UTC = timezone.utc
MAX_ROWS = 1000


def _stamp(value):
    if type(value) is not str or not 20 <= len(value) <= 64 or value[10] != "T":
        raise ApiError("invalid_calendar_date")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(UTC)
    except (ValueError, OverflowError):
        raise ApiError("invalid_calendar_date") from None


def _text(value, fallback=None):
    if value is None and fallback is not None:
        return fallback
    if (type(value) is not str or not value.strip() or len(value) > 1024
            or any(unicodedata.category(char).startswith("C") for char in value)):
        raise ApiError("invalid_calendar_metadata")
    return value


def _revision(session):
    value = getattr(session, "data_revision", 0)
    if type(value) is not int or value < 0:
        raise ApiError("invalid_data_revision")
    return value


def _guard(session, generation, revision):
    session.assert_current(generation)
    if _revision(session) != revision:
        raise ApiError("data_changed")


def _project(payload, start, end):
    if (type(payload) is not dict or not isinstance(payload.get("entries"), list)
            or len(payload["entries"]) > MAX_ROWS):
        raise ApiError("invalid_calendar_metadata")
    rows, identities, coordinates = [], {}, {}
    for source in payload["entries"]:
        if type(source) is not dict:
            raise ApiError("invalid_calendar_metadata")
        show, episode = source.get("show"), source.get("episode")
        if (type(show) is not dict or type(episode) is not dict
                or type(show.get("ids")) is not dict or type(episode.get("ids")) is not dict):
            raise ApiError("invalid_calendar_metadata")
        show_id, ident = metadata_id(show["ids"].get("trakt")), metadata_id(episode["ids"].get("trakt"))
        season, number = episode.get("season"), episode.get("number")
        if (type(season) is not int or not 0 <= season <= 10000
                or type(number) is not int or not 1 <= number <= 10000):
            raise ApiError("invalid_calendar_metadata")
        stamp = _stamp(source.get("first_aired"))
        if episode.get("first_aired") is not None and _stamp(episode["first_aired"]) != stamp:
            raise ApiError("conflicting_calendar_episode")
        if not start <= stamp < end:
            raise ApiError("calendar_window_mismatch")
        row = {"id": "trakt:episode:" + str(ident), "kind": "episode", "trakt_id": ident,
               "show_id": show_id, "show_title": _text(show.get("title")),
               "title": _text(episode.get("title"), "Episode S%02dE%02d" % (season, number)), "season": season, "episode": number,
               "release_at": stamp, "release_status": "upcoming", "watched": None,
               "playable": False, "aired_unwatched": False}
        coordinate = (show_id, season, number)
        if ident in identities:
            if row != identities[ident]:
                raise ApiError("conflicting_calendar_episode")
            continue
        if coordinate in coordinates:
            raise ApiError("conflicting_calendar_episode")
        identities[ident], coordinates[coordinate] = row, ident
        rows.append(row)
    return rows


def upcoming(session, start_date, days=7, *, now=None, allowed_show_ids=None):
    """Return future episodes within a bounded UTC personal-calendar window.

    All inputs are validated before credential refresh. Session reads and projection
    share one generation/revision; no partial result or retry follows a failure.
    Outer first_aired is authoritative for this calendar occurrence. A supplied
    nested first_aired must agree; an unknown episode title gets a numeric label.
    Watched is always unknown. A date does not establish a playable source.
    """
    start_date, days = calendar_arguments(start_date, days)
    current = datetime.now(UTC) if now is None else now
    if not isinstance(current, datetime) or current.tzinfo is None:
        raise ApiError("invalid_clock")
    try:
        current = current.astimezone(UTC)
        start = datetime.combine(datetime.strptime(start_date, "%Y-%m-%d").date(), time(), UTC)
        end = start + timedelta(days=days)
    except (ValueError, OverflowError):
        raise ApiError("invalid_calendar_window") from None
    selected = None
    if allowed_show_ids is not None:
        if not isinstance(allowed_show_ids, (set, frozenset, list, tuple)) or len(allowed_show_ids) > 100:
            raise ApiError("invalid_calendar_filter")
        selected = frozenset(metadata_id(value) for value in allowed_show_ids)
        if not selected:
            return []
    generation = session.cache_key()
    revision = _revision(session)
    _guard(session, generation, revision)
    payload = session.read("calendar_shows", start_date, days)
    _guard(session, generation, revision)
    if (type(payload) is not dict or payload.get("start_date") != start_date
            or type(payload.get("days")) is not int or payload["days"] != days):
        raise ApiError("calendar_window_mismatch")
    rows = _project(payload, start, end)
    rows = [row for row in rows if row["release_at"] > current
            and (selected is None or row["show_id"] in selected)]
    rows.sort(key=lambda row: (row["release_at"], row["show_id"], row["season"], row["episode"], row["trakt_id"]))
    _guard(session, generation, revision)
    return rows
