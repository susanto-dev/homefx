"""Inactive playback observations; no player, service writes or completion policy."""
from dataclasses import dataclass
from enum import Enum
import math
from threading import Lock
import time

MAX_SECONDS = 7 * 24 * 60 * 60
MAX_ID = 2 ** 63 - 1


class EventResult(str, Enum):
    ACCEPTED = "accepted"
    STALE = "stale"
    INVALID = "invalid"
    TERMINAL = "terminal"
    BUSY = "busy"


@dataclass(frozen=True)
class Observation:
    state: str
    position: object = None
    duration: object = None
    progress: object = None
    watched: object = None


class EventError(ValueError):
    """Fixed diagnostics without event data or callback exception text."""


def _integer(value, minimum=0):
    return type(value) is int and minimum <= value <= MAX_ID


def _seconds(value, maximum):
    return type(value) in (int, float) and 0 <= value <= maximum and math.isfinite(value)


class PlaybackEvents:
    """Observe one explicitly correlated attempt, without interpreting completion.

    The future adapter must correlate callbacks to the attempt and assign strictly
    increasing sequence numbers in event order. A sequence is not an authentication
    mechanism. Callbacks are trusted bounded code. Nothing constructs this observer
    from the Kodi entry point. The timeout applies only while awaiting AV start.
    """
    _TERMINAL = frozenset({"ended", "stopped", "error", "cancelled", "session_changed",
                           "expired", "unavailable"})
    _EVENTS = frozenset({"av_started", "sample", "paused", "resumed", "ended", "stopped", "error"})

    def __init__(self, attempt_id, expected_generation, cancelled, current_generation,
                 clock=time.monotonic, startup_timeout=30):
        if (not _integer(attempt_id, 1) or not _integer(expected_generation)
                or not _seconds(startup_timeout, 300) or startup_timeout < 1
                or not all(callable(item) for item in (cancelled, current_generation, clock))):
            raise EventError("invalid_event_configuration")
        self._attempt, self._generation = attempt_id, expected_generation
        self._cancelled, self._current, self._clock = cancelled, current_generation, clock
        self._timeout = startup_timeout
        self._lock = Lock()
        self._state, self._sequence = "waiting", 0
        self._position = self._duration = None
        try:
            self._created = self._last_time = clock()
            if not _seconds(self._created, 10 ** 12):
                raise ValueError()
        except Exception:
            raise EventError("invalid_event_clock") from None

    def __repr__(self):
        return "PlaybackEvents(<private observation>)"

    def _clear(self, state):
        self._state, self._position, self._duration = state, None, None

    def _guard(self):
        try:
            now = self._clock()
            cancelled = self._cancelled()
            generation = self._current()
            if (not _seconds(now, 10 ** 12) or now < self._last_time
                    or not _integer(generation) or type(cancelled) is not bool):
                raise ValueError()
            self._last_time = now
            if generation != self._generation:
                self._clear("session_changed")
            elif cancelled:
                self._clear("cancelled")
            elif self._state == "waiting" and now - self._created >= self._timeout:
                self._clear("expired")
        except Exception:
            self._clear("unavailable")

    @staticmethod
    def _sample(position, duration):
        if not _seconds(position, MAX_SECONDS):
            return False
        return duration is None or (_seconds(duration, MAX_SECONDS)
                                    and duration > 0 and position <= duration)

    def observe(self, attempt_id, generation, sequence, event, position=None, duration=None):
        """Accept one valid event; invalid/late events never advance the sequence.

        Samples have seconds, not percentage. Unknown duration must be None.
        A new sample with unknown duration clears an older known duration.
        End/stop/error never manufacture a final sample or a watched result.
        """
        if not self._lock.acquire(blocking=False):
            return EventResult.BUSY
        try:
            if (not _integer(attempt_id, 1) or not _integer(generation)
                    or not _integer(sequence, 1) or type(event) is not str or event not in self._EVENTS):
                return EventResult.INVALID
            if attempt_id != self._attempt or generation != self._generation or sequence <= self._sequence:
                return EventResult.STALE
            if event == "sample":
                if not self._sample(position, duration):
                    return EventResult.INVALID
            elif position is not None or duration is not None:
                return EventResult.INVALID
            self._guard()
            if self._state in self._TERMINAL:
                return EventResult.TERMINAL
            valid = (event in {"error", "stopped"}
                     or event == "av_started" and self._state == "waiting"
                     or event in {"sample", "ended"} and self._state in {"playing", "paused"}
                     or event == "paused" and self._state == "playing"
                     or event == "resumed" and self._state == "paused")
            if not valid:
                return EventResult.INVALID
            self._sequence = sequence
            if event == "sample":
                self._position, self._duration = position, duration
            else:
                self._state = {"av_started": "playing", "resumed": "playing"}.get(event, event)
            return EventResult.ACCEPTED
        finally:
            self._lock.release()

    def snapshot(self):
        """Return a detached observation after account/cancellation/clock guards."""
        if not self._lock.acquire(blocking=False):
            raise EventError("event_observer_busy")
        try:
            self._guard()
            progress = (100 * self._position / self._duration
                        if self._position is not None and self._duration is not None else None)
            return Observation(self._state, self._position, self._duration, progress)
        finally:
            self._lock.release()
