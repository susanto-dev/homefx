"""Inactive, single-use playback coordination with injected resolver and player.

Metadata identifies a title; a separately supplied link identifies a source the
caller is authorized to use. No discovery, provider fallback, network construction,
Kodi API call, persistence, history write or scrobbling occurs in this module.
"""
from enum import Enum
from math import isfinite
from threading import Lock
import time

from .debrid_client import validate_url


class PlaybackResult(str, Enum):
    ACCEPTED = "accepted"
    SOURCE_MISSING = "source_missing"
    INVALID_INPUT = "invalid_input"
    CANCELLED = "cancelled"
    SESSION_CHANGED = "session_changed"
    STATE_UNAVAILABLE = "state_unavailable"
    EXPIRED = "expired"
    RESOLVE_FAILED = "resolve_failed"
    START_REJECTED = "start_rejected"
    START_UNCERTAIN = "start_uncertain"
    ALREADY_ATTEMPTED = "already_attempted"


def _metadata(value):
    if type(value) is not dict:
        raise ValueError("invalid_identity")
    kind = value.get("kind")
    if kind == "movie":
        if set(value) != {"kind", "trakt_id"}:
            raise ValueError("invalid_identity")
        integers = ((value["trakt_id"], 1, 2 ** 63 - 1),)
    elif kind == "episode":
        if set(value) != {"kind", "show_trakt_id", "season", "episode"}:
            raise ValueError("invalid_identity")
        integers = ((value["show_trakt_id"], 1, 2 ** 63 - 1),
                    (value["season"], 0, 999), (value["episode"], 1, 10000))
    else:
        raise ValueError("invalid_identity")
    if any(type(number) is not int or not lower <= number <= upper
           for number, lower, upper in integers):
        raise ValueError("invalid_identity")
    return dict(value)


def _seconds(value, upper):
    if type(value) not in (int, float):
        return False
    try:
        return isfinite(value) and 0 <= value <= upper
    except OverflowError:
        return False


class PlaybackAttempt:
    """One in-memory attempt, never automatically retried.

    resolver(link) returns an object with .url. player(url, metadata, resume)
    returns exactly True to accept the request; ACCEPTED is not an AV-start event.
    Metadata IDs are Trakt IDs, never inferred from URLs or other namespaces.
    Resume is caller-supplied seconds (at most seven days), not a scrobbling policy.

    All callbacks must be bounded. The deadline is checked after blocking callbacks,
    but cannot interrupt them. The player callback must enforce its own cancellation
    and account identity atomically with dispatch if another thread can change state.
    A state change after dispatch cannot undo playback and yields START_UNCERTAIN.
    This lock prevents duplicate dispatch only within this object/process; it is not
    a durable or cross-invocation playback lock. Create a new object only for a new
    explicit user attempt. URLs and metadata are held only on the run call's stack.
    """
    def __init__(self, resolver, player, cancelled, current_generation,
                 expected_generation, clock=time.monotonic, max_seconds=60):
        if (type(expected_generation) is not int or expected_generation < 0
                or not _seconds(max_seconds, 300) or max_seconds < 1
                or not all(callable(callback) for callback in
                           (resolver, player, cancelled, current_generation, clock))):
            raise ValueError("invalid_playback_configuration")
        self._resolver, self._player = resolver, player
        self._cancelled, self._generation = cancelled, current_generation
        self._expected = expected_generation
        self._clock, self._max_seconds = clock, max_seconds
        self._lock, self._used = Lock(), False

    def __repr__(self):
        return "PlaybackAttempt(<private interaction>)"

    def _guard(self, started):
        try:
            if self._cancelled():
                return PlaybackResult.CANCELLED
            generation = self._generation()
            if type(generation) is not int or generation != self._expected:
                return PlaybackResult.SESSION_CHANGED
            now = self._clock()
            if not _seconds(now, float("inf")) or now < started:
                return PlaybackResult.STATE_UNAVAILABLE
            if now - started >= self._max_seconds:
                return PlaybackResult.EXPIRED
        except Exception:
            return PlaybackResult.STATE_UNAVAILABLE
        return None

    def run(self, metadata, source_link, resume=0):
        if not self._lock.acquire(blocking=False):
            return PlaybackResult.ALREADY_ATTEMPTED
        try:
            if self._used:
                return PlaybackResult.ALREADY_ATTEMPTED
            self._used = True
            try:
                identity = _metadata(metadata)
                if not _seconds(resume, 7 * 24 * 60 * 60):
                    return PlaybackResult.INVALID_INPUT
                started = self._clock()
                if not _seconds(started, float("inf")):
                    return PlaybackResult.STATE_UNAVAILABLE
                if source_link is None or source_link == "":
                    return PlaybackResult.SOURCE_MISSING
                link = validate_url(source_link)
            except Exception:
                return PlaybackResult.INVALID_INPUT
            stopped = self._guard(started)
            if stopped is not None:
                return stopped
            try:
                resolved = self._resolver(link)
                url = validate_url(resolved.url)
            except Exception:
                return PlaybackResult.RESOLVE_FAILED
            stopped = self._guard(started)
            if stopped is not None:
                return stopped
            try:
                accepted = self._player(url, identity, resume)
            except Exception:
                # Dispatch may have succeeded before the callback lost its response.
                return PlaybackResult.START_UNCERTAIN
            if accepted is False:
                return PlaybackResult.START_REJECTED
            if accepted is not True:
                return PlaybackResult.START_UNCERTAIN
            if self._guard(started) is not None:
                return PlaybackResult.START_UNCERTAIN
            return PlaybackResult.ACCEPTED
        finally:
            self._lock.release()
