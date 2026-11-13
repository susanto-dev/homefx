"""Read-only Trakt contracts with an injected transport; no live network adapter.

Transport receives relative paths and must bind them to API_HOST, verify TLS,
reject redirects, bound response bytes/time, and never log credentials. Results
live only in invocation memory. Errors intentionally omit URLs and response data.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import re
import unicodedata
from urllib.parse import urlencode

API_HOST = "https://api.trakt.tv"


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict = field(default_factory=dict, repr=False)
    body: object = field(default=None, repr=False)


class ApiError(Exception):
    def __init__(self, kind, status=None, retry_after=None):
        self.kind, self.status, self.retry_after = kind, status, retry_after
        super().__init__("Trakt request failed: " + kind)


@dataclass(frozen=True)
class ListRef:
    trakt_id: int
    owner: str
    name: str
    writable: bool

    @property
    def key(self):
        return "trakt-list:" + str(self.trakt_id)


def _identifier(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ApiError("invalid_identifier")
    value = str(value)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value):
        raise ApiError("invalid_identifier")
    return value


def _positive_id(value):
    if type(value) is not int or value <= 0:
        raise ApiError("invalid_response")
    return value


def search_arguments(query, kind="movie"):
    """Validate a literal title query before any authenticated work."""
    if (not isinstance(kind, str) or kind not in {"movie", "show"} or
            not isinstance(query, str) or not 1 <= len(query) <= 128 or
            any(unicodedata.category(c).startswith("C") for c in query)):
        raise ApiError("invalid_search")
    query = query.strip()
    if not query:
        raise ApiError("invalid_search")
    return query, kind


def metadata_id(value):
    if type(value) is not int or not 1 <= value < 2 ** 63:
        raise ApiError("invalid_identifier")
    return value


def progress_arguments(show_id, include_specials=False):
    show_id = metadata_id(show_id)
    if type(include_specials) is not bool:
        raise ApiError("invalid_identifier")
    return show_id, include_specials


def season_arguments(show_id, season):
    show_id = metadata_id(show_id)
    if type(season) is not int or not 0 <= season <= 10000:
        raise ApiError("invalid_identifier")
    return show_id, season


def episode_arguments(show_id, season, episode):
    show_id, season = season_arguments(show_id, season)
    if type(episode) is not int or not 1 <= episode <= 10000:
        raise ApiError("invalid_identifier")
    return show_id, season, episode


def calendar_arguments(start_date, days=7):
    if (type(start_date) is not str or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", start_date)
            or type(days) is not int or not 1 <= days <= 31):
        raise ApiError("invalid_calendar_window")
    try:
        start = date.fromisoformat(start_date)
        start + timedelta(days=days)
    except (ValueError, OverflowError):
        raise ApiError("invalid_calendar_window") from None
    return start_date, days


def _metadata_text(value, nullable=False):
    if value is None and nullable:
        return None
    if (type(value) is not str or not value.strip() or len(value) > 1024
            or any(unicodedata.category(c).startswith("C") for c in value)):
        raise ApiError("invalid_metadata")
    return value


def _metadata_stamp(value, date_only=False):
    if type(value) is not str or len(value) > 64:
        raise ApiError("invalid_metadata")
    try:
        if date_only:
            if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                raise ValueError()
            return date.fromisoformat(value)
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
                            r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})", value):
            raise ValueError()
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError()
        return stamp.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise ApiError("invalid_metadata") from None


def _title_details(item, episode=False):
    if not isinstance(item, dict) or not isinstance(item.get("ids"), dict):
        raise ApiError("invalid_metadata")
    row = {"ids": {"trakt": metadata_id(item["ids"].get("trakt"))},
           "title": _metadata_text(item.get("title"), nullable=episode)}
    if episode:
        _, season, number = episode_arguments(1, item.get("season"), item.get("number"))
        row.update(season=season, number=number)
    else:
        year = item.get("year")
        if year is not None and (type(year) is not int or not 1 <= year <= 9999):
            raise ApiError("invalid_metadata")
        row["year"] = year
    return row


def _dated_details(item, episode=False):
    row = _title_details(item, episode)
    field = "first_aired" if episode else "released"
    value = item.get(field)
    if value is not None:
        _metadata_stamp(value, date_only=not episode)
    row[field] = value
    return row


def _season_rows(items, maximum):
    """Project season metadata; counts never establish watched or playable state."""
    if not isinstance(items, list) or len(items) > min(maximum, 1000):
        raise ApiError("invalid_metadata")
    rows, numbers, identifiers = [], set(), set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("ids"), dict):
            raise ApiError("invalid_metadata")
        number, ident = item.get("number"), metadata_id(item["ids"].get("trakt"))
        if (type(number) is not int or not 0 <= number <= 10000
                or number in numbers or ident in identifiers):
            raise ApiError("invalid_metadata")
        row = {"number": number, "ids": {"trakt": ident}}
        for key in ("episode_count", "aired_episodes"):
            value = item.get(key)
            if value is not None and (type(value) is not int or not 0 <= value <= 10000):
                raise ApiError("invalid_metadata")
            row[key] = value
        for key, maximum_length in (("title", 1024), ("first_aired", 64)):
            value = item.get(key)
            if value is not None and (not isinstance(value, str) or len(value) > maximum_length
                    or any(unicodedata.category(c).startswith("C") for c in value)):
                raise ApiError("invalid_metadata")
            row[key] = value
        rows.append(row)
        numbers.add(number)
        identifiers.add(ident)
    return rows


def metadata_rows(items, kind, wrapped=False):
    """Project basic title metadata without inferring release or watched state."""
    if not isinstance(items, list) or len(items) > 10000:
        raise ApiError("invalid_metadata")
    rows, seen = [], set()
    for item in items:
        if not isinstance(item, dict):
            raise ApiError("invalid_metadata")
        if wrapped and item.get("type") != kind:
            raise ApiError("invalid_metadata")
        media = item.get(kind) if wrapped else item
        if not isinstance(media, dict) or not isinstance(media.get("ids"), dict):
            raise ApiError("invalid_metadata")
        ident = metadata_id(media["ids"].get("trakt"))
        title, year = media.get("title"), media.get("year")
        if (ident in seen or not isinstance(title, str) or not title.strip() or
                len(title) > 1024 or any(unicodedata.category(c).startswith("C") for c in title) or
                (year is not None and (type(year) is not int or not 1 <= year <= 9999))):
            raise ApiError("invalid_metadata")
        seen.add(ident)
        rows.append({"kind": kind, "trakt_id": ident, "title": title, "year": year,
                     "watched": None, "release_status": "unknown", "playable": False})
    return rows


def retry_delay(headers, now=None):
    """Return a bounded UI delay, never sleep or retry a request automatically."""
    raw = {str(k).lower(): v for k, v in headers.items()}.get("retry-after", "")
    if type(raw) not in (str, int) or (isinstance(raw, str) and len(raw) > 128):
        return 60
    try:
        delay = int(raw)
    except (TypeError, ValueError, OverflowError):
        try:
            when = parsedate_to_datetime(raw)
            if when.tzinfo is None:
                raise ValueError()
            delay = (when - (now or datetime.now(timezone.utc))).total_seconds()
        except (TypeError, ValueError, OverflowError, IndexError):
            delay = 60
    return max(1, min(3600, int(delay)))


class Client:
    def __init__(self, request, client_id, access_token, page_size=100,
                 max_pages=20, max_items=2000):
        for value in (client_id, access_token):
            if not isinstance(value, str) or not 1 <= len(value) <= 4096 or any(
                    ord(c) < 33 or ord(c) > 126 for c in value):
                raise ApiError("invalid_credentials")
        if (type(page_size) is not int or not 1 <= page_size <= 100 or
                type(max_pages) is not int or not 1 <= max_pages <= 100 or
                type(max_items) is not int or not 1 <= max_items <= 10000):
            raise ApiError("invalid_bounds")
        self._request = request
        self._client_id, self._token = client_id, access_token
        self.page_size, self.max_pages, self.max_items = page_size, max_pages, max_items

    def search_titles(self, query, kind="movie"):
        query, kind = search_arguments(query, kind)
        # Trakt documents backslash escaping for literal search operators.
        operators = set('+ -&|!(){}[]^"~*?:/\\'.replace(' ', ''))
        literal = ''.join(('\\' + c) if c in operators else c for c in query)
        rows = self._pages("/search/" + kind + "?" + urlencode({"query": literal, "fields": "title"}))
        metadata_rows(rows, kind, wrapped=True)
        return rows

    def related_movies(self, trakt_id):
        trakt_id = metadata_id(trakt_id)
        rows = self._pages("/movies/" + str(trakt_id) + "/related")
        metadata_rows(rows, "movie")
        return rows

    def _get(self, path):
        headers = {"Authorization": "Bearer " + self._token,
                   "trakt-api-key": self._client_id, "trakt-api-version": "2",
                   "Content-Type": "application/json"}
        try:
            response = self._request("GET", path, headers, None)
        except Exception:
            raise ApiError("transport") from None
        if (type(getattr(response, "status", None)) is not int or
                not isinstance(getattr(response, "headers", None), dict) or
                not hasattr(response, "body")):
            raise ApiError("invalid_response")
        status = response.status
        if status == 401:
            raise ApiError("reauthenticate", status)
        if status in (403, 404):
            raise ApiError("unavailable", status)
        if status == 420:
            raise ApiError("account_limit", status)
        if status == 429:
            raise ApiError("rate_limit", status, retry_delay(response.headers))
        if status != 200:
            raise ApiError("service", status)
        return response

    def _pages(self, path):
        rows = []
        for page in range(1, self.max_pages + 1):
            separator = "&" if "?" in path else "?"
            response = self._get(path + separator + urlencode({"page": page, "limit": self.page_size}))
            body = getattr(response, "body", None)
            if not isinstance(body, list) or len(body) > self.page_size or any(
                    not isinstance(row, dict) for row in body):
                raise ApiError("invalid_response")
            rows.extend(body)
            if len(rows) > self.max_items:
                raise ApiError("result_limit")
            headers = {str(k).lower(): v for k, v in response.headers.items()}
            count = headers.get("x-pagination-page-count")
            try:
                if "x-pagination-page" in headers and int(headers["x-pagination-page"]) != page:
                    raise ValueError()
                if count is not None:
                    count = int(count)
                    if count < 0 or (count == 0 and body) or (count and count < page):
                        raise ValueError()
            except (TypeError, ValueError):
                raise ApiError("invalid_pagination") from None
            if count is not None:
                if count > self.max_pages:
                    raise ApiError("result_limit")
                if page >= count:
                    return rows
                if not body:
                    raise ApiError("invalid_pagination")
            elif len(body) < self.page_size:
                return rows
            else:
                # A full page without a total cannot be called a complete result.
                raise ApiError("invalid_pagination")
        raise ApiError("result_limit")

    @staticmethod
    def _list(row, own):
        item = row if own else row.get("list")
        if not isinstance(item, dict):
            raise ApiError("invalid_response")
        ids = item.get("ids")
        if not isinstance(ids, dict):
            raise ApiError("invalid_response")
        ident = _positive_id(ids.get("trakt"))
        name = item.get("name")
        if not isinstance(name, str) or not 1 <= len(name) <= 1000:
            raise ApiError("invalid_response")
        if own:
            owner = "me"
        else:
            user = item.get("user", {})
            user_ids = user.get("ids", {}) if isinstance(user, dict) else {}
            owner = _identifier(user_ids.get("slug") if isinstance(user_ids, dict) else None)
        return ListRef(ident, owner, name, own)

    def lists(self):
        """Union by global list ID; ownership evidence wins over a liked copy."""
        own = [self._list(row, True) for row in self._pages("/users/me/lists")]
        liked = [self._list(row, False) for row in self._pages("/users/likes/lists")]
        result = {}
        for ref in own + liked:
            result.setdefault(ref.key, ref)
        return list(result.values())

    def list_items(self, owner, list_id):
        return self._pages("/users/" + _identifier(owner) + "/lists/" +
                           _identifier(list_id) + "/items?extended=full")

    def watched_movies(self):
        """Complete unpaginated watched IDs, or an error; never a partial set.

        The typed personal watched endpoint has no page/limit contract. Reject
        pagination metadata rather than interpreting a partial response as all
        history. Large histories fail the configured item/transport byte bound.
        """
        response = self._get("/users/me/watched/movies")
        if any(str(key).lower().startswith("x-pagination-") for key in response.headers):
            raise ApiError("invalid_pagination")
        rows = response.body
        if not isinstance(rows, list):
            raise ApiError("invalid_response")
        if len(rows) > self.max_items:
            raise ApiError("result_limit")
        identifiers, seen = [], set()
        for row in rows:
            if (not isinstance(row, dict) or type(row.get("plays")) is not int
                    or not 1 <= row["plays"] <= 2 ** 63 - 1
                    or row.get("type", "movie") != "movie"):
                raise ApiError("invalid_progress")
            movie = row.get("movie")
            ids = movie.get("ids") if isinstance(movie, dict) else None
            if not isinstance(ids, dict):
                raise ApiError("invalid_progress")
            ident = ids.get("trakt")
            if type(ident) is not int or not 1 <= ident <= 2 ** 63 - 1 or ident in seen:
                raise ApiError("invalid_progress")
            seen.add(ident)
            identifiers.append(ident)
        return tuple(identifiers)

    def paused(self):
        return self._pages("/sync/playback")

    def _complete(self, path):
        response = self._get(path)
        if any(str(key).lower().startswith("x-pagination-") for key in response.headers):
            raise ApiError("invalid_pagination")
        return response.body

    def movie_details(self, trakt_id):
        ident = metadata_id(trakt_id)
        row = _dated_details(self._complete("/movies/" + str(ident) + "?extended=full"))
        if row["ids"]["trakt"] != ident:
            raise ApiError("mismatched_movie")
        return row

    def episode_details(self, show_id, season, episode):
        ident, season, episode = episode_arguments(show_id, season, episode)
        path = "/shows/{}/seasons/{}/episodes/{}?extended=full".format(ident, season, episode)
        row = _dated_details(self._complete(path), episode=True)
        if row["season"] != season or row["number"] != episode:
            raise ApiError("mismatched_episode")
        return {"show_id": ident, "episode": row}

    def calendar_shows(self, start_date, days=7):
        start_date, days = calendar_arguments(start_date, days)
        start = datetime.combine(date.fromisoformat(start_date), datetime.min.time(), timezone.utc)
        end = start + timedelta(days=days)
        body = self._complete("/calendars/my/shows/{}/{}?extended=full".format(start_date, days))
        if not isinstance(body, list) or len(body) > self.max_items:
            raise ApiError("invalid_metadata")
        entries, identifiers, coordinates = [], set(), set()
        for item in body:
            if not isinstance(item, dict):
                raise ApiError("invalid_metadata")
            show = _title_details(item.get("show"))
            episode_source = item.get("episode")
            if (not isinstance(episode_source, dict) or episode_source.get("episodes") is not None
                    or episode_source.get("episode_type") in ("full_season", "multiple_episodes")):
                raise ApiError("invalid_metadata")
            episode = _dated_details(episode_source, episode=True)
            stamp = _metadata_stamp(item.get("first_aired"))
            if not start <= stamp < end:
                raise ApiError("invalid_calendar_window")
            if (episode["first_aired"] is not None
                    and _metadata_stamp(episode["first_aired"]) != stamp):
                raise ApiError("conflicting_air_date")
            ident = episode["ids"]["trakt"]
            coordinate = (show["ids"]["trakt"], episode["season"], episode["number"])
            if ident in identifiers or coordinate in coordinates:
                raise ApiError("duplicate_metadata")
            identifiers.add(ident)
            coordinates.add(coordinate)
            entries.append({"first_aired": item["first_aired"], "show": show, "episode": episode})
        return {"start_date": start_date, "days": days, "entries": entries}

    def show_seasons(self, show_id):
        ident = metadata_id(show_id)
        response = self._get("/shows/" + str(ident) + "/seasons?extended=full")
        if any(str(key).lower().startswith("x-pagination-") for key in response.headers):
            raise ApiError("invalid_pagination")
        return {"show_id": ident, "seasons": _season_rows(response.body, self.max_items)}

    def show_progress(self, show_id, include_specials=False):
        ident, include_specials = progress_arguments(show_id, include_specials)
        specials = "true" if include_specials else "false"
        body = self._get("/shows/" + str(ident) + "/progress/watched?hidden=false&specials=" + specials).body
        if not isinstance(body, dict) or not isinstance(body.get("seasons"), list):
            raise ApiError("invalid_response")
        return {"show_id": ident, "progress": body}

    def season_episodes(self, show_id, season):
        ident, season = season_arguments(show_id, season)
        response = self._get("/shows/" + str(ident) + "/seasons/" + str(season) + "?extended=full")
        if any(str(key).lower().startswith("x-pagination-") for key in response.headers):
            raise ApiError("invalid_pagination")
        body = response.body
        if (not isinstance(body, list) or len(body) > self.max_items or
                any(not isinstance(row, dict) for row in body)):
            raise ApiError("invalid_response")
        return {"show_id": ident, "episodes": body}

    def settings(self):
        body = self._get("/users/settings").body
        if not isinstance(body, dict):
            raise ApiError("invalid_response")
        return body
