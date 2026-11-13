"""Invocation-memory reads with optional account-bound saved list choices."""
from collections import OrderedDict
from copy import deepcopy
from dataclasses import asdict
import json
import time

from .trakt_auth import AuthError, _number
from .trakt_client import ApiError, ListRef, search_arguments, metadata_id, metadata_rows
from . import trakt_views
from .trakt_preferences import PreferencesError, account_uuid


class MemoryCache:
    """Bounded TTL cache. Entries are copies, never aliases of caller data.

    Bounds apply to serialized payloads, not Python heap overhead. Oversized
    successful responses may be returned to the caller but are not retained.
    """
    def __init__(self, clock=time.monotonic, ttl=30, max_entries=32,
                 max_bytes=1024 * 1024, max_rows=2000):
        if (not _number(ttl, 0, 300) or type(max_entries) is not int or
                not 1 <= max_entries <= 128 or type(max_bytes) is not int or
                not 1 <= max_bytes <= 4 * 1024 * 1024 or type(max_rows) is not int or
                not 1 <= max_rows <= 10000):
            raise ApiError("invalid_cache_configuration")
        self._clock, self._ttl = clock, ttl
        self._max_entries, self._max_bytes, self._max_rows = max_entries, max_bytes, max_rows
        self._entries = OrderedDict()
        self._bytes = 0

    def __repr__(self):
        return "MemoryCache(<private invocation data>)"

    def clear(self):
        self._entries.clear()
        self._bytes = 0

    def _remove(self, key):
        _, size, _ = self._entries.pop(key)
        self._bytes -= size

    def _prune(self):
        now = self._clock()
        for key in list(self._entries):
            if self._entries[key][0] <= now:
                self._remove(key)

    def get(self, key):
        self._prune()
        if key not in self._entries:
            return False, None
        return True, deepcopy(self._entries[key][2])

    def put(self, key, value):
        self._prune()
        if key in self._entries:
            self._remove(key)
        if self._ttl == 0 or (isinstance(value, (list, tuple)) and len(value) > self._max_rows):
            return

        def encode(obj):
            if isinstance(obj, ListRef):
                return asdict(obj)
            raise TypeError("unsupported cache value")

        try:
            encoded = json.dumps(value, default=encode, allow_nan=False, ensure_ascii=True)
            size = len(encoded.encode("utf-8"))
            if size > self._max_bytes:
                return
            copied = deepcopy(value)
        except (ValueError, TypeError, OverflowError, RecursionError):
            return
        while self._entries and (len(self._entries) >= self._max_entries or
                                 self._bytes + size > self._max_bytes):
            self._remove(next(iter(self._entries)))
        self._entries[key] = (self._clock() + self._ttl, size, copied)
        self._bytes += size


class Library:
    """Read through an account session and isolate cache/selection by generation.

    Selected keys optionally persist through a private AccountPreferences store.
    Only verified user.ids.uuid binds that store; no slug fallback is permitted.
    Every cache hit checks current shared account state before returning data.
    External account changes clear memory on the next access, not in a background
    observer. Local disconnect clears memory and all locally saved profile choices.
    Token rotation restores choices only after rechecking the stable account identity.
    No write, playback or availability claim is made by these reads.
    """
    def __init__(self, session, cache=None, preferences=None):
        self._session = session
        self._cache = cache if cache is not None else MemoryCache()
        # A caller may reuse a cache across profiles whose generations coincide.
        # An opaque per-library namespace keeps their private entries distinct.
        self._cache_namespace = object()
        self._generation = None
        self._revision = None
        self._account = None
        self._preferences = preferences
        self._preferences_epoch = None
        self._selected = ()

    def __repr__(self):
        return "Library(<private account views>)"

    def clear(self):
        self._cache.clear()
        self._generation, self._revision, self._account, self._selected = None, None, None, ()
        self._preferences_epoch = None

    def disconnect(self, expected_generation=None):
        """Clear local credentials and all choices, optionally pinning confirmation."""
        if expected_generation is not None:
            if not self._session.disconnect(expected_generation=expected_generation):
                return False
            self.clear()
            if self._preferences is not None:
                self._preferences.clear_all()
            return True
        self.clear()
        try:
            # Stop new authenticated loads before invalidating pending preference saves.
            self._session.disconnect()
        finally:
            if self._preferences is not None:
                self._preferences.clear_all()
        return True

    def _data_revision(self):
        return getattr(self._session, 'data_revision', 0)

    def _assert_view(self, generation, revision):
        self._session.assert_current(generation)
        if self._data_revision() != revision:
            raise ApiError('data_changed')

    def _activate(self, generation, revision):
        self.clear()
        if self._preferences is not None:
            settings = self._session.read('settings')
            self._assert_view(generation, revision)
            account = account_uuid(settings)
            epoch, selected = self._preferences.snapshot(account)
            self._assert_view(generation, revision)
            self._account, self._selected = account, tuple(selected)
            self._preferences_epoch = epoch
        self._generation = generation

    def _read(self, operation, *args, expected_generation=None, expected_revision=None):
        try:
            generation = self._session.cache_key()
            revision = self._data_revision()
            if expected_revision is not None and revision != expected_revision:
                raise ApiError("data_changed")
            if expected_generation is not None and generation != expected_generation:
                raise AuthError("session_changed")
            if generation != self._generation:
                self._activate(generation, revision)
            key = (self._cache_namespace, generation, revision, operation) + args
            found, value = self._cache.get(key)
            if not found:
                value = self._session.read(operation, *args)
            self._assert_view(generation, revision)
            self._revision = revision
            if not found:
                self._cache.put(key, value)
            return value
        except (AuthError, ApiError):
            self.clear()
            raise

    def lists(self):
        return self._read("lists")

    def select_lists(self, keys):
        if not isinstance(keys, (list, tuple)) or len(keys) > 100 or any(
                not isinstance(key, str) or len(key) > 128 for key in keys):
            raise ApiError("invalid_selection")
        available = {ref.key: ref for ref in self.lists()}
        if len(set(keys)) != len(keys) or any(key not in available for key in keys):
            raise ApiError("unavailable_selection")
        try:
            self._assert_view(self._generation, self._revision)
        except (AuthError, ApiError):
            self.clear()
            raise
        try:
            if self._preferences is not None:
                if not self._preferences.save(self._account, keys, expected_epoch=self._preferences_epoch):
                    raise PreferencesError('preferences_changed')
                self._assert_view(self._generation, self._revision)
            self._selected = tuple(keys)
            return [available[key] for key in self._selected]
        except (AuthError, ApiError):
            self.clear()
            raise

    def selected_lists(self):
        available = {ref.key: ref for ref in self.lists()}
        if any(key not in available for key in self._selected):
            raise ApiError("unavailable_selection")
        try:
            self._assert_view(self._generation, self._revision)
        except (AuthError, ApiError):
            self.clear()
            raise
        return [available[key] for key in self._selected]

    def list_items(self, key):
        if not isinstance(key, str) or len(key) > 128:
            raise ApiError("invalid_selection")
        available = {ref.key: ref for ref in self.lists()}
        if key not in available:
            raise ApiError("unavailable_selection")
        ref = available[key]
        return self._read("list_items", ref.owner, ref.trakt_id,
                          expected_generation=self._generation, expected_revision=self._revision)

    def episode_view(self, show_id, season, now=None, episode_filter="all"):
        if not isinstance(episode_filter, str) or episode_filter not in {"all", "aired_unwatched"}:
            raise ApiError("invalid_filter")
        # Guard the whole join as well as each component: mixing account snapshots
        # could otherwise attribute one account's history to another's metadata.
        try:
            generation = self._session.cache_key()
            revision = self._data_revision()
            metadata = self._read("season_episodes", show_id, season, expected_generation=generation, expected_revision=revision)
            progress = self._read("show_progress", show_id, expected_generation=generation, expected_revision=revision)
            pauses = self._read("paused", expected_generation=generation, expected_revision=revision)
            rows = trakt_views.episodes(metadata, progress, pauses, now)
            if episode_filter == "aired_unwatched":
                rows = [row for row in rows if row["aired_unwatched"]]
            self._assert_view(generation, revision)
            return rows
        except (AuthError, ApiError):
            self.clear()
            raise


    def series_view(self, show_id, now=None, episode_filter="all", include_specials=False):
        """Enumerate bounded season metadata under one account/revision guard.

        Regular seasons are the default; specials require an explicit opt-in for
        both metadata and watched progress. This is a metadata view, never a
        source catalogue. Responses are not truncated to fit the request budget.
        """
        show_id = metadata_id(show_id)
        if (type(include_specials) is not bool or not isinstance(episode_filter, str)
                or episode_filter not in {"all", "aired_unwatched"}):
            raise ApiError("invalid_filter")
        # Validate time before an account refresh or any authenticated read.
        now = trakt_views._now(now)
        try:
            generation = self._session.cache_key()
            revision = self._data_revision()

            def read(operation, *args):
                return self._read(operation, *args, expected_generation=generation,
                                  expected_revision=revision)

            snapshot = read("show_seasons", show_id)
            if (not isinstance(snapshot, dict) or snapshot.get("show_id") != show_id
                    or not isinstance(snapshot.get("seasons"), list)
                    or len(snapshot["seasons"]) > 1000):
                raise ApiError("invalid_metadata")
            seasons, numbers, identifiers, counts = [], set(), set(), {}
            for season in snapshot["seasons"]:
                if not isinstance(season, dict):
                    raise ApiError("invalid_metadata")
                number = season.get("number")
                ident = trakt_views._id(season)
                if (type(number) is not int or not 0 <= number <= 10000
                        or ident is None or number in numbers or ident in identifiers):
                    raise ApiError("invalid_metadata")
                numbers.add(number)
                identifiers.add(ident)
                count = season.get("episode_count")
                if count is not None and (type(count) is not int or not 0 <= count <= 10000):
                    raise ApiError("invalid_metadata")
                if number != 0 or include_specials:
                    seasons.append(number)
                    counts[number] = count
            if len(seasons) > 50 or sum(count or 0 for count in counts.values()) > 5000:
                raise ApiError("series_limit_exceeded")
            episodes = []
            for season in sorted(seasons):
                response = read("season_episodes", show_id, season)
                if (not isinstance(response, dict) or response.get("show_id") != show_id
                        or not isinstance(response.get("episodes"), list)):
                    raise ApiError("invalid_metadata")
                entries = response["episodes"]
                if counts[season] is not None and len(entries) != counts[season]:
                    # Metadata can change between requests. Do not present a
                    # truncated or inconsistent enumeration as a complete view.
                    raise ApiError("incomplete_series")
                if len(episodes) + len(entries) > 5000:
                    raise ApiError("series_limit_exceeded")
                if any(not isinstance(row, dict) or type(row.get("season")) is not int
                       or row["season"] != season for row in entries):
                    raise ApiError("mismatched_season")
                episodes.extend(entries)
            progress = read("show_progress", show_id, include_specials)
            pauses = read("paused")
            rows = trakt_views.episodes({"show_id": show_id, "episodes": episodes},
                                        progress, pauses, now)
            result = trakt_views.episode_filter(rows, episode_filter)
            self._assert_view(generation, revision)
            return result
        except (AuthError, ApiError):
            self.clear()
            raise

    def series_seasons(self, show_id, now=None, include_specials=False):
        """Counts from enumerated episode rows, not from guessed watched totals."""
        try:
            rows = self.series_view(show_id, now=now, include_specials=include_specials)
            generation, revision = self._generation, self._revision
            result = trakt_views.season_summaries(rows)
            self._assert_view(generation, revision)
            return result
        except (AuthError, ApiError):
            self.clear()
            raise

    def movie_view(self, key, now=None, movie_filter="all"):
        """Join list metadata, complete watched IDs and pauses for one account.

        Snapshot failures propagate; absence means unwatched only after a complete
        authenticated response. These are metadata views, not playable catalogues.
        """
        if not isinstance(movie_filter, str) or movie_filter not in {"all", "unwatched", "released_unwatched", "upcoming"}:
            raise ApiError("invalid_filter")
        try:
            generation = self._session.cache_key()
            revision = self._data_revision()
            source = self.list_items(key)
            self._assert_view(generation, revision)
            metadata = []
            for item in source:
                if not isinstance(item, dict):
                    raise ApiError("invalid_metadata")
                if item.get("type") == "movie":
                    metadata.append(item.get("movie"))
            pauses = self._read("paused", expected_generation=generation,
                                expected_revision=revision)
            watched = self._read("watched_movies", expected_generation=generation,
                                 expected_revision=revision)
            rows = trakt_views.movie_filter(
                trakt_views.movies(metadata, frozenset(watched), pauses, now), movie_filter)
            self._assert_view(generation, revision)
            return rows
        except (AuthError, ApiError):
            self.clear()
            raise

    def continue_view(self, now=None):
        """Dated aired pauses only; missing dates and watched state remain unverified.

        The current playback endpoint need not supply extended metadata, so this
        conservative view can be empty/incomplete. No implicit metadata requests.
        """
        try:
            generation = self._session.cache_key()
            revision = self._data_revision()
            pauses = self._read("paused", expected_generation=generation,
                                expected_revision=revision)
            rows = trakt_views.continued(pauses, now)
            self._assert_view(generation, revision)
            return rows
        except (AuthError, ApiError):
            self.clear()
            raise

    def search_titles(self, query, kind="movie"):
        """Literal title metadata in server relevance order; never widget-sorted."""
        query, kind = search_arguments(query, kind)
        return self._metadata_view("search_titles", (query, kind), kind, wrapped=True)

    def related_movies(self, trakt_id):
        """Default related titles, without personalized ranking or playback claims."""
        return self._metadata_view("related_movies", (metadata_id(trakt_id),), "movie")

    def _metadata_view(self, operation, args, kind, wrapped=False):
        try:
            generation = self._session.cache_key()
            revision = self._data_revision()
            source = self._read(operation, *args, expected_generation=generation,
                                expected_revision=revision)
            rows = metadata_rows(source, kind, wrapped=wrapped)
            self._assert_view(generation, revision)
            return rows
        except (AuthError, ApiError):
            self.clear()
            raise
