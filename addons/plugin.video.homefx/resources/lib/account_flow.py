"""Inactive, injected account interaction; no Kodi UI or network construction.

The UI adapter implements confirm_replace(), show_code(code, url), close(), and
confirm_disconnect(). The latter must explain that all local list choices are
removed, without promising remote revocation. wait(seconds) must advance the
injected monotonic clock and return truthy on cancellation. Requests themselves
must have transport timeouts: this controller cannot interrupt blocking I/O.
"""
from enum import Enum
from math import isfinite

from .trakt_auth import AuthError


class FlowResult(str, Enum):
    AUTHORIZED = "authorized"
    DISCONNECTED = "disconnected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    DENIED = "denied"
    USED = "used"
    INVALID = "invalid"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SESSION_CHANGED = "session_changed"


class _Stopped(Exception):
    def __init__(self, result):
        self.result = result


class AccountFlow:
    """An explicit interaction, with bounded waits and safe fixed outcomes.

    disconnect_callback must accept expected_generation and return False when
    that generation no longer matches. Library.disconnect provides this contract.
    Authorization means credentials were stored, not account/library verification.
    """
    def __init__(self, session, ui, wait, cancelled, clock, disconnect_callback,
                 max_seconds=600):
        if (isinstance(max_seconds, bool) or not isinstance(max_seconds, (int, float))
                or not isfinite(max_seconds) or not 1 <= max_seconds <= 1800):
            raise ValueError("invalid_flow_duration")
        self.session, self.ui = session, ui
        self.wait, self.cancelled, self.clock = wait, cancelled, clock
        self.disconnect_callback = disconnect_callback
        self.max_seconds = max_seconds

    def __repr__(self):
        return "AccountFlow(<private interaction>)"

    def connect(self):
        result = FlowResult.FAILED
        attempt = None
        opened = False
        try:
            started = self.clock()
            if not isfinite(started):
                return FlowResult.FAILED
            previous = started
            deadline = started + self.max_seconds
            status = self.session.status()
            generation = status["generation"]
            if self.cancelled():
                return FlowResult.CANCELLED
            if status["state"] != "disconnected" and not self.ui.confirm_replace():
                return FlowResult.CANCELLED
            if self.cancelled():
                return FlowResult.CANCELLED
            if self.session.status()["generation"] != generation:
                return FlowResult.SESSION_CHANGED
            prompt = self.session.begin_login(expected_generation=generation)
            if prompt is None:
                raise _Stopped(FlowResult.SESSION_CHANGED)
            # Ownership is acquired only after issuance succeeds for this generation.
            attempt = generation + 1
            if self.cancelled():
                raise _Stopped(FlowResult.CANCELLED)
            if self.clock() >= deadline:
                raise _Stopped(FlowResult.TIMEOUT)
            self.session.login_timing(expected_generation=attempt)
            opened = True
            self.ui.show_code(prompt.user_code, prompt.verification_url)
            # A second limit protects against a broken/non-advancing scheduler.
            for _ in range(4000):
                now = self.clock()
                if not isfinite(now) or now < previous:
                    break
                previous = now
                if self.cancelled():
                    result = FlowResult.CANCELLED
                    break
                if now >= deadline:
                    result = FlowResult.TIMEOUT
                    break
                timing = self.session.login_timing(expected_generation=attempt)
                if timing["state"] != "pending":
                    result = self._terminal(timing["state"])
                    break
                if now >= timing["expires_at"]:
                    result = FlowResult.EXPIRED
                    break
                if now >= timing["next_poll"]:
                    def abort():
                        return self.cancelled() or self.clock() >= deadline
                    state = self.session.poll_login(cancelled=abort, expected_generation=attempt)
                    if state != "pending":
                        result = self._terminal(state)
                        if state == "cancelled" and self.clock() >= deadline:
                            result = FlowResult.TIMEOUT
                        break
                else:
                    delay = min(1.0, timing["next_poll"] - now,
                                timing["expires_at"] - now, deadline - now)
                    if self.wait(delay):
                        result = FlowResult.CANCELLED
                        break
                    if self.clock() <= now:
                        break
        except _Stopped as stopped:
            result = stopped.result
        except AuthError as error:
            result = (FlowResult.SESSION_CHANGED if error.args == ("session_changed",)
                      else FlowResult.FAILED)
        except Exception:
            result = FlowResult.FAILED
        finally:
            if attempt is not None and result != FlowResult.AUTHORIZED:
                try:
                    self.session.cancel_login(expected_generation=attempt)
                except Exception:
                    result = FlowResult.FAILED
            if opened:
                try:
                    self.ui.close()
                except Exception:
                    # A UI cleanup failure must never undo committed credentials.
                    if result != FlowResult.AUTHORIZED:
                        result = FlowResult.FAILED
        return result

    @staticmethod
    def _terminal(state):
        try:
            return FlowResult(state) if state != "idle" else FlowResult.CANCELLED
        except ValueError:
            return FlowResult.FAILED

    def disconnect(self):
        try:
            generation = self.session.status()["generation"]
            if self.cancelled() or not self.ui.confirm_disconnect() or self.cancelled():
                return FlowResult.CANCELLED
            if not self.disconnect_callback(expected_generation=generation):
                return FlowResult.SESSION_CHANGED
            return FlowResult.DISCONNECTED
        except Exception:
            return FlowResult.FAILED
