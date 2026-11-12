"""Inactive provider session with durable refresh and account-generation guards.

Callers inject an already constructed store and request callbacks. Import and
construction create no profile, transport, account screen or player. Local
credential deletion is not service-side revocation or backup erasure.
"""
from threading import Lock
import time

from .debrid_auth import AuthError, DeviceLogin, _number, _text, _wall, refresh
from .debrid_client import Client, DebridError, validate_url


class Session:
    """One invocation, sharing durable account state with other invocations.

    Read/resolution operations serialize within this object and fail on reentry.
    There is no cross-process resolution lock or rate limiter. Refresh ownership
    is durable in the injected store; a failed/abandoned exchange is never replayed.
    All callbacks must enforce transport timeouts and cancellation themselves.
    """
    def __init__(self, store, oauth_request, api_request, public_client_id,
                 clock=time.time, monotonic=time.monotonic, refresh_margin=60,
                 pending_response=None):
        if (not _text(public_client_id, 256) or not _number(refresh_margin, 0, 300)
                or not all(callable(value) for value in
                           (oauth_request, api_request, clock, monotonic))
                or (pending_response is not None and not callable(pending_response))):
            raise AuthError("invalid_session_configuration")
        self._store, self._oauth, self._api = store, oauth_request, api_request
        self._client_id, self._clock, self._monotonic = public_client_id, clock, monotonic
        self._margin, self._pending_response = refresh_margin, pending_response
        self._login = self._login_generation = None
        self._login_lock, self._operation_lock = Lock(), Lock()
        self.data_revision = 0

    def __repr__(self):
        return "Session(<private provider account>)"

    def status(self):
        """Local state only, with no credentials, codes, refresh or network."""
        snapshot = self._store.snapshot()
        if self._login is not None and snapshot.generation != self._login_generation:
            self.cancel_login()
        state = snapshot.state
        if state == "ready" and snapshot.tokens.expires_at <= _wall(self._clock) + self._margin:
            state = "refresh_required"
        return {"state": state, "generation": snapshot.generation,
                "login": self._login.state if self._login is not None else "idle"}

    def _owns_login(self, login, generation):
        return (self._login is login and self._login_generation == generation
                and self._store.snapshot().generation == generation)

    def _assert_login(self, expected_generation):
        if expected_generation is not None and (
                type(expected_generation) is not int or expected_generation < 0
                or self._login_generation != expected_generation
                or self._store.snapshot().generation != expected_generation):
            raise AuthError("session_changed")

    def begin_login(self, expected_generation=None):
        """Explicit replacement; stale confirmation cannot clear a newer account."""
        if not self._login_lock.acquire(blocking=False):
            raise AuthError("login_in_progress")
        try:
            previous = self._store.snapshot()
            if expected_generation is not None and (
                    type(expected_generation) is not int or expected_generation < 0
                    or previous.generation != expected_generation):
                raise AuthError("session_changed")
            if not self._store.disconnect(expected_generation=previous.generation):
                raise AuthError("session_changed")
            self.cancel_login()
            generation = previous.generation + 1
            login = DeviceLogin(self._oauth, self._client_id, self._monotonic,
                                self._clock, self._pending_response)
            self._login, self._login_generation = login, generation
            try:
                prompt = login.begin(cancelled=lambda: not self._owns_login(login, generation))
                if not self._owns_login(login, generation):
                    login.cancel()
                    return None
                return prompt
            except Exception:
                login.cancel()
                if self._login is login:
                    self._login = self._login_generation = None
                raise
        finally:
            self._login_lock.release()

    def poll_login(self, cancelled=None, expected_generation=None):
        if not self._login_lock.acquire(blocking=False):
            raise AuthError("login_in_progress")
        login = generation = None
        try:
            self._assert_login(expected_generation)
            login, generation = self._login, self._login_generation
            if login is None:
                raise AuthError("login_not_started")

            def aborted():
                try:
                    requested = cancelled is not None and bool(cancelled())
                    return requested or not self._owns_login(login, generation)
                except Exception:
                    return True

            state = login.poll(cancelled=aborted)
            if not self._owns_login(login, generation):
                login.cancel()
                return "cancelled"
            if state == "authorized":
                credentials, tokens = login.credentials, login.tokens
                if not self._owns_login(login, generation):
                    login.cancel()
                    return "cancelled"
                if tokens.expires_at <= _wall(self._clock) + self._margin:
                    self.cancel_login(expected_generation=generation)
                    raise AuthError("invalid_token_response")
                if aborted():
                    self.cancel_login(expected_generation=generation)
                    return "cancelled"
                if not self._store.install(credentials, tokens,
                                           expected_generation=generation):
                    self.cancel_login(expected_generation=generation)
                    return "cancelled"
                # Installation advanced the durable generation. Do not attempt
                # another store write merely to erase in-memory grant material.
                self._drop_login(login)
            elif state != "pending":
                self.cancel_login(expected_generation=generation)
            return state
        except AuthError:
            if login is not None and self._login is login:
                self.cancel_login(expected_generation=generation)
            raise
        finally:
            self._login_lock.release()

    def login_timing(self, expected_generation=None):
        self._assert_login(expected_generation)
        self.status()
        self._assert_login(expected_generation)
        login = self._login
        if login is None:
            return {"state": "idle", "next_poll": None, "expires_at": None}
        return {"state": login.state, "next_poll": login.next_poll,
                "expires_at": login.prompt.expires_at if login.prompt else None}

    def _drop_login(self, login):
        login.cancel()
        if self._login is login:
            self._login = self._login_generation = None

    def cancel_login(self, expected_generation=None):
        """Invalidate pending durable ownership before accepting cancellation.

        True means a concurrent installation using this attempt's generation can
        no longer commit. False means no matching pending ownership remained;
        an installation that already committed is not undone by this method.
        """
        login, generation = self._login, self._login_generation
        if (login is None or (expected_generation is not None and (
                type(expected_generation) is not int or expected_generation < 0
                or generation != expected_generation))):
            return False
        accepted = self._store.disconnect(expected_generation=generation)
        self._drop_login(login)
        return accepted

    def disconnect(self, expected_generation=None):
        if not self._store.disconnect(expected_generation=expected_generation):
            return False
        self.cancel_login(expected_generation=expected_generation)
        self.data_revision += 1
        return True

    def _current(self, generation):
        snapshot = self._store.snapshot()
        if (snapshot.state != "ready" or snapshot.generation != generation
                or snapshot.tokens.expires_at <= _wall(self._clock)):
            raise AuthError("session_changed")
        return snapshot

    def current_generation(self):
        """Local-only player guard; never refresh or contact a service.

        Call account() explicitly to prepare/refresh before capturing this value.
        A refresh changes generation, so an old playback attempt must be discarded.
        The eventual player adapter must enforce identity atomically at dispatch.
        """
        snapshot = self._store.snapshot()
        return self._current(snapshot.generation).generation

    def cache_key(self):
        """Alias of the local-only generation guard, not an implicit refresh."""
        return self.current_generation()

    def assert_current(self, generation):
        self._current(generation)

    def _ready(self):
        snapshot = self._store.snapshot()
        if snapshot.state == "refreshing":
            raise AuthError("refresh_busy")
        if snapshot.state != "ready":
            raise AuthError("reauthentication_required")
        if snapshot.tokens.expires_at > _wall(self._clock) + self._margin:
            return snapshot
        claim = self._store.claim_refresh(snapshot.generation)
        if claim is None:
            if self._store.snapshot().state == "refreshing":
                raise AuthError("refresh_busy")
            raise AuthError("session_changed")

        def stopped():
            current = self._store.snapshot()
            return current.generation != claim.generation or current.state != "refreshing"

        try:
            tokens = refresh(self._oauth, claim.credentials, claim.tokens.refresh_token,
                             clock=self._clock, cancelled=stopped)
            if tokens.expires_at <= _wall(self._clock) + self._margin:
                raise AuthError("invalid_token_response")
            if not self._store.complete_refresh(claim, tokens):
                raise AuthError("session_changed")
        except Exception:
            self._store.fail_refresh(claim)
            raise
        return self._current(claim.generation + 1)

    def _execute(self, operation, link=None):
        if not self._operation_lock.acquire(blocking=False):
            raise AuthError("action_in_progress")
        attempted = False
        generation = None
        try:
            snapshot = self._ready()
            generation = snapshot.generation

            def guarded_request(method, path, headers, body=None):
                nonlocal attempted
                self._current(generation)
                if method == "POST":
                    attempted = True
                    self.data_revision += 1
                response = self._api(method, path, headers, body)
                self._current(generation)
                return response

            client = Client(guarded_request, snapshot.tokens.access_token)
            try:
                if operation == "account":
                    result = client.account()
                elif operation == "downloads":
                    result = client.downloads()
                else:
                    result = client.unrestrict(link)
                self._current(generation)
                return result
            except DebridError as error:
                try:
                    self._current(generation)
                except AuthError:
                    if attempted:
                        raise DebridError("uncertain") from None
                    raise
                if error.kind == "reauthenticate":
                    self._store.disconnect(expected_generation=generation)
                raise
            except AuthError:
                if attempted:
                    raise DebridError("uncertain") from None
                raise
        finally:
            if attempted:
                self.data_revision += 1
            self._operation_lock.release()

    def account(self):
        return self._execute("account")

    def downloads(self):
        return self._execute("downloads")

    def unrestrict(self, link):
        """One explicit resolution; validate before any credential/network access."""
        return self._execute("unrestrict", validate_url(link))
