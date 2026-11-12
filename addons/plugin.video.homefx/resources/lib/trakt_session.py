"""Inactive account coordinator; construction performs no network or storage I/O.

Callers supply a private token store and request callbacks. This module neither
constructs a transport nor enables an account screen. A new login disconnects the
previous local account; server-side revocation remains a separate user action.
"""
import time
from threading import Lock

from .trakt_auth import AuthError, DeviceLogin, _number, _text, refresh_tokens
from .trakt_client import search_arguments, metadata_id, ApiError, Client
from .trakt_actions import ActionResult, MutationClient, prepare


class Session:
    """Coordinate one invocation while checking the shared store generation.

    No request is automatically repeated after an authentication error. Read
    results from a generation changed during the request are discarded. Callers
    must still cancel outstanding network I/O through their transport callback.
    """
    READS = frozenset(("lists", "list_items", "paused", "show_progress",
                       "season_episodes", "settings", "watched_movies", "search_titles", "related_movies"))

    def __init__(self, store, oauth_request, api_request, client_id, redirect_uri,
                 clock=time.time, monotonic=time.monotonic, refresh_margin=60,
                 mutation_request=None):
        if not _text(client_id, 256) or not _text(redirect_uri, 2048):
            raise AuthError("invalid_client_identity")
        if not _number(refresh_margin, 0, 300):
            raise AuthError("invalid_session_configuration")
        self._store = store
        self._oauth = oauth_request
        self._api = api_request
        self._mutation = mutation_request
        self.data_revision = 0
        self._mutation_pending = False
        self._mutation_lock = Lock()
        self._client_id = client_id
        self._redirect_uri = redirect_uri
        self._clock, self._monotonic = clock, monotonic
        self._margin = refresh_margin
        self._login = None
        self._login_generation = None

    def __repr__(self):
        return "Session(<private account>)"

    def status(self):
        """Read local status only; never refresh or expose tokens/device codes."""
        snapshot = self._store.snapshot()
        if self._login is not None and snapshot.generation != self._login_generation:
            self.cancel_login()
        state = snapshot.state
        if state == "ready" and snapshot.tokens.expires_at <= self._clock() + self._margin:
            state = "refresh_required"
        return {"state": state, "generation": snapshot.generation,
                "login": self._login.state if self._login is not None else "idle"}

    def begin_login(self, expected_generation=None):
        """Start an explicit account replacement and return a redacted prompt."""
        prior = self._store.snapshot()
        if expected_generation is not None and prior.generation != expected_generation:
            raise AuthError("session_changed")
        self.cancel_login()
        if not self._store.disconnect(expected_generation=prior.generation):
            raise AuthError("session_changed")
        expected = prior.generation + 1
        login = DeviceLogin(self._oauth, self._client_id, self._monotonic)
        self._login, self._login_generation = login, expected
        try:
            prompt = login.begin()
        except Exception:
            login.cancel()
            if self._login is login:
                self._login, self._login_generation = None, None
            raise
        if self._login is not login or self._store.snapshot().generation != expected:
            login.cancel()
            return None
        return prompt

    def _assert_login_generation(self, expected_generation):
        if expected_generation is not None and (
                self._login_generation != expected_generation
                or self._store.snapshot().generation != expected_generation):
            raise AuthError("session_changed")

    def poll_login(self, cancelled=None, expected_generation=None):
        self._assert_login_generation(expected_generation)
        login = self._login
        if login is None:
            raise AuthError("login_not_started")
        expected = self._login_generation
        if self._store.snapshot().generation != expected:
            self.cancel_login()
            return "cancelled"
        def aborted():
            try:
                return cancelled is not None and cancelled()
            except Exception:
                return True

        cancelled_before = aborted()
        self._assert_login_generation(expected_generation)
        if cancelled_before:
            self.cancel_login(expected_generation=expected)
            return "cancelled"
        state = login.poll()
        self._assert_login_generation(expected_generation)
        cancelled_after = aborted()
        self._assert_login_generation(expected_generation)
        if cancelled_after:
            self.cancel_login(expected_generation=expected)
            return "cancelled"
        if self._login is not login or self._store.snapshot().generation != expected:
            login.cancel()
            return "cancelled"
        if state == "authorized":
            if login.tokens.expires_at <= self._clock() + self._margin:
                self.cancel_login()
                raise AuthError("invalid_token_response")
            if not self._store.install(login.tokens, expected_generation=expected):
                self.cancel_login()
                return "cancelled"
            self._login, self._login_generation = None, None
        return state

    def login_timing(self, expected_generation=None):
        """Public monotonic scheduling data; contains no codes or credentials."""
        self._assert_login_generation(expected_generation)
        self.status()
        self._assert_login_generation(expected_generation)
        login = self._login
        if login is None:
            return {"state": "idle", "next_poll": None, "expires_at": None}
        return {"state": login.state, "next_poll": login.next_poll,
                "expires_at": login.prompt.expires_at if login.prompt else None}

    def cancel_login(self, expected_generation=None):
        if expected_generation is not None and self._login_generation != expected_generation:
            return
        if self._login is not None:
            self._login.cancel()
        self._login, self._login_generation = None, None

    def disconnect(self, expected_generation=None):
        if not self._store.disconnect(expected_generation=expected_generation):
            return False
        self.cancel_login(expected_generation=expected_generation)
        return True

    def _current(self, generation):
        snapshot = self._store.snapshot()
        if snapshot.generation != generation or snapshot.state != "ready":
            raise AuthError("session_changed")
        return snapshot

    def _ready(self):
        if self._mutation_pending:
            raise AuthError("action_in_progress")
        snapshot = self._store.snapshot()
        if snapshot.state == "refreshing":
            raise AuthError("refresh_busy")
        if snapshot.state != "ready":
            raise AuthError("reauthentication_required")
        if snapshot.tokens.expires_at <= self._clock() + self._margin:
            refreshed = refresh_tokens(self._store, self._oauth, self._client_id,
                                       self._redirect_uri, snapshot.generation)
            if refreshed is None:
                current = self._store.snapshot()
                if current.state == "refreshing":
                    raise AuthError("refresh_busy")
                raise AuthError("session_changed")
            snapshot = self._current(snapshot.generation + 1)
            if snapshot.tokens.expires_at <= self._clock() + self._margin:
                self._store.disconnect(expected_generation=snapshot.generation)
                raise AuthError("reauthentication_required")
        return snapshot

    def cache_key(self):
        """Usable account generation; may refresh once, never returns a token."""
        return self._ready().generation

    def assert_current(self, generation):
        """Validate a cached/read result immediately before returning it."""
        snapshot = self._current(generation)
        if snapshot.tokens.expires_at <= self._clock():
            raise AuthError("session_changed")

    def read(self, operation, *args):
        if not isinstance(operation, str) or operation not in self.READS:
            raise ApiError("unsupported_operation")
        if operation == "search_titles":
            search_arguments(*args)
        elif operation == "related_movies":
            metadata_id(*args)
        snapshot = self._ready()
        generation = snapshot.generation

        def guarded_request(method, path, headers, body=None):
            self.assert_current(generation)
            response = self._api(method, path, headers, body)
            self.assert_current(generation)
            return response

        client = Client(guarded_request, self._client_id, snapshot.tokens.access_token)
        try:
            result = getattr(client, operation)(*args)
            self.assert_current(generation)
            return result
        except ApiError as error:
            # A late 401 must not disconnect an account installed in the meantime.
            if error.kind == "reauthenticate":
                self._store.disconnect(expected_generation=generation)
            else:
                self._current(generation)
            raise

    def mutate(self, operation, *args):
        """An explicit single write; failures/uncertainty are never replayed.

        No callback is configured by default. History writes are not idempotent;
        callers must reconcile an uncertain outcome before attempting another.
        data_revision changes at both attempt and completion, even when the result
        is lost. Reads and nested writes are refused while a callback is pending.
        """
        request = prepare(operation, *args)
        if self._mutation is None:
            return ActionResult('failed', 'writes_disabled')
        snapshot = self._ready()
        generation = snapshot.generation
        attempted = [False]
        blocked = [False]

        def guarded_request(method, path, headers, body=None):
            if not self._mutation_lock.acquire(blocking=False):
                blocked[0] = True
                raise AuthError('action_in_progress')
            try:
                self.assert_current(generation)
                attempted[0] = True
                self._mutation_pending = True
                self.data_revision += 1
                try:
                    return self._mutation(method, path, headers, body)
                finally:
                    self.data_revision += 1
                    self._mutation_pending = False
            finally:
                self._mutation_lock.release()

        client = MutationClient(guarded_request, self._client_id, snapshot.tokens.access_token)
        result = client.execute(request)
        if blocked[0]:
            return ActionResult('failed', 'action_in_progress')
        try:
            self.assert_current(generation)
        except AuthError:
            return ActionResult('uncertain' if attempted[0] else 'failed', 'session_changed')
        if result.reason == 'reauthenticate':
            self._store.disconnect(expected_generation=generation)
        return result
