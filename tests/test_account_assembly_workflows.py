"""Real account assemblies with fabricated HTTP and UI; no service traffic."""
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib.account_flow import AccountFlow, FlowResult
from resources.lib.account_ui import AccountUI
from resources.lib.debrid_auth import Credentials, Tokens
from resources.lib.debrid_client import DebridError
from resources.lib.debrid_store import CredentialStore
from resources.lib.service_runtime import build_debrid, build_trakt
from resources.lib.trakt_auth import TokenSet
from resources.lib.trakt_client import ApiError
from resources.lib.trakt_preferences import AccountPreferences
from resources.lib.trakt_tokens import TokenStore
from test_trakt_transport import Connections, wire


class Dialog:
    def __init__(self):
        self.messages = []

    def yesno(self, heading, message):
        self.messages.append((heading, message))
        return True


class Progress:
    def __init__(self):
        self.messages, self.closed = [], 0
        self.cancel = False
        self.opened_hook = None

    def create(self, heading, message):
        self.messages.append((heading, message))
        if self.opened_hook:
            self.opened_hook()

    def update(self, percent):
        self.last_percent = percent

    def close(self):
        self.closed += 1

    def iscanceled(self):
        return self.cancel


class Monitor:
    def __init__(self, tick):
        self.tick, self.waits = tick, []
        self.abort = False

    def abortRequested(self):
        return self.abort

    def waitForAbort(self, seconds):
        self.waits.append(seconds)
        self.tick[0] += seconds
        return self.abort


def response(body, status=200, headers=None):
    return wire(json.dumps(body).encode(), status, headers)


def authorization(provider):
    url = "https://trakt.tv/activate" if provider == "trakt" else "https://real-debrid.com/device"
    grant = response(dict(device_code="synthetic-private-device", user_code="DISPLAY-ONLY",
                          verification_url=url, interval=5, expires_in=60))
    if provider == "trakt":
        return [grant, response(dict(access_token="synthetic-access", refresh_token="synthetic-refresh",
            token_type="bearer", created_at=1000, expires_in=3600))]
    return [grant, response(dict(client_id="synthetic-bound", client_secret="synthetic-user-secret")),
            response(dict(access_token="synthetic-access", refresh_token="synthetic-refresh",
                          token_type="Bearer", expires_in=3600))]


class AccountAssemblyWorkflows(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.profile = Path(temporary.name)
        self.tick = [0.0]

    def assemble(self, provider, connections, **kwargs):
        settings = dict(clock=lambda: 1000 + self.tick[0], monotonic=lambda: self.tick[0],
                        connection_factory=connections)
        settings.update(kwargs)
        if provider == "trakt":
            return build_trakt(self.profile, "synthetic-public", "https://example.invalid/callback", **settings)
        return build_debrid(self.profile, "synthetic-public", **settings)

    def ui_flow(self, provider, bundle):
        dialog, progress, monitor = Dialog(), Progress(), Monitor(self.tick)
        ui = AccountUI(provider, dialog, lambda: progress, monitor)
        flow = AccountFlow(bundle.session, ui, ui.wait, ui.cancelled,
                           lambda: self.tick[0], bundle.disconnect)
        return flow, ui, dialog, progress, monitor

    def store(self, provider):
        kind = TokenStore if provider == "trakt" else CredentialStore
        return kind(self.profile, clock=lambda: 1000 + self.tick[0])

    def seed(self, provider, suffix="replacement"):
        store = self.store(provider)
        if provider == "trakt":
            store.install(TokenSet("synthetic-access-" + suffix, "synthetic-refresh-" + suffix, 5000))
        else:
            store.install(Credentials("synthetic-bound", "synthetic-user-secret"),
                          Tokens("synthetic-access-" + suffix, "synthetic-refresh-" + suffix, 5000))
        return store

    def test_trakt_authorization_is_explicit_and_writes_stay_disabled(self):
        connections = Connections(authorization("trakt"))
        bundle = self.assemble("trakt", connections)
        self.assertEqual(connections.calls, [])
        flow, ui, dialog, progress, monitor = self.ui_flow("trakt", bundle)
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            self.assertEqual(flow.connect(), FlowResult.AUTHORIZED)
        self.assertEqual(bundle.session.status()["state"], "ready")
        self.assertEqual(self.store("trakt").snapshot().tokens.access_token, "synthetic-access")
        self.assertEqual(len(connections.calls), 2)
        self.assertEqual([b"".join(sock.sent).split(b"\r\n", 1)[0] for sock in connections.sockets],
                         [b"POST /oauth/device/code HTTP/1.1", b"POST /oauth/device/token HTTP/1.1"])
        result = bundle.session.mutate("mark_watched", "movie", 7, datetime(2026, 11, 13, tzinfo=timezone.utc))
        self.assertEqual((result.outcome, result.reason), ("failed", "writes_disabled"))
        self.assertEqual(len(connections.calls), 2)
        visible = repr(progress.messages)
        self.assertIn("DISPLAY-ONLY", visible)
        for private in ("synthetic-private-device", "synthetic-access", "synthetic-refresh"):
            self.assertNotIn(private, visible + repr(bundle) + repr(flow) + repr(ui))
        self.assertNotIn("DISPLAY-ONLY", repr(bundle) + repr(flow) + repr(ui))
        self.assertEqual((output.getvalue(), errors.getvalue()), ("", ""))
        self.assertEqual(progress.closed, 1)
        self.assertEqual(dialog.messages, [])
        self.assertTrue(monitor.waits and all(0 < delay <= 0.1 for delay in monitor.waits))

    def test_provider_authorization_does_not_claim_account_entitlement(self):
        connections = Connections(authorization("realdebrid"))
        bundle = self.assemble("realdebrid", connections)
        flow, ui, _, progress, _ = self.ui_flow("realdebrid", bundle)
        self.assertEqual(flow.connect(), FlowResult.AUTHORIZED)
        snapshot = self.store("realdebrid").snapshot()
        self.assertEqual((snapshot.state, snapshot.tokens.access_token), ("ready", "synthetic-access"))
        self.assertEqual(snapshot.credentials.client_id, "synthetic-bound")
        paths = [b"".join(sock.sent).split(b"\r\n", 1)[0] for sock in connections.sockets]
        self.assertEqual(len(paths), 3)
        self.assertTrue(all(b"/oauth/v2/" in path for path in paths))
        self.assertFalse(any(b"/rest/" in path for path in paths))
        self.assertEqual(progress.closed, 1)
        self.assertNotIn("synthetic", repr(bundle) + repr(ui) + repr(flow))

    def test_cancelled_dialog_clears_attempt_without_token_exchange(self):
        for provider in ("trakt", "realdebrid"):
            with self.subTest(provider=provider):
                connections = Connections(authorization(provider))
                bundle = self.assemble(provider, connections)
                flow, _, _, progress, _ = self.ui_flow(provider, bundle)
                progress.opened_hook = lambda: setattr(progress, "cancel", True)
                self.assertEqual(flow.connect(), FlowResult.CANCELLED)
                self.assertEqual(len(connections.calls), 1)
                self.assertEqual(bundle.session.status()["login"], "idle")
                self.assertEqual(self.store(provider).snapshot().state, "disconnected")
                self.assertEqual(progress.closed, 1)

    def test_replacement_during_token_exchange_survives_stale_flow_cleanup(self):
        for provider in ("trakt", "realdebrid"):
            with self.subTest(provider=provider):
                connections = Connections(authorization(provider))
                bundle = self.assemble(provider, connections)
                flow, _, _, progress, _ = self.ui_flow(provider, bundle)
                token_request = 2 if provider == "trakt" else 3
                def replace():
                    if len(connections.calls) == token_request:
                        self.seed(provider)
                connections.connect_hook = replace
                expected = FlowResult.SESSION_CHANGED if provider == "trakt" else FlowResult.CANCELLED
                self.assertEqual(flow.connect(), expected)
                snapshot = self.store(provider).snapshot()
                self.assertEqual(snapshot.tokens.access_token, "synthetic-access-replacement")
                self.assertEqual(snapshot.state, "ready")
                self.assertEqual(len(connections.calls), token_request)
                self.assertEqual(progress.closed, 1)

    def test_rate_limit_survives_new_runtime_instance_for_each_provider(self):
        for provider, error in (("trakt", ApiError), ("realdebrid", DebridError)):
            with self.subTest(provider=provider):
                self.seed(provider)
                success = {} if provider == "trakt" else dict(type="premium", premium=100,
                                                               expiration="2030-01-01T00:00:00Z")
                throttled = response({}, 429, [("Content-Type", "application/json"),
                    ("Content-Length", "2"), ("Retry-After", "7")])
                connections = Connections([throttled, response(success)])
                first = self.assemble(provider, connections)
                def read(bundle):
                    return bundle.session.read("settings") if provider == "trakt" else bundle.session.account()
                with self.assertRaises(error) as caught:
                    read(first)
                self.assertEqual(caught.exception.kind, "rate_limit")
                second = self.assemble(provider, connections)
                with self.assertRaises(error) as caught:
                    read(second)
                self.assertEqual(caught.exception.kind, "rate_limit")
                self.assertEqual(len(connections.calls), 1)
                self.tick[0] += 7
                read(second)
                self.assertEqual(len(connections.calls), 2)

    def test_trakt_disconnect_clears_selections_but_preserves_provider_account(self):
        self.seed("trakt")
        provider_store = self.seed("realdebrid")
        before = provider_store.snapshot()
        preferences = AccountPreferences(self.profile)
        preferences.save("synthetic-account", ["trakt-list:4"])
        connections = Connections([])
        bundle = self.assemble("trakt", connections)
        flow, _, dialog, _, _ = self.ui_flow("trakt", bundle)
        self.assertEqual(flow.disconnect(), FlowResult.DISCONNECTED)
        self.assertEqual(preferences.load("synthetic-account"), [])
        self.assertEqual(self.store("trakt").snapshot().state, "disconnected")
        self.assertEqual(provider_store.snapshot(), before)
        self.assertEqual(connections.calls, [])
        self.assertIn("all saved HomeFX list choices", dialog.messages[0][1])
        self.assertIn("does not revoke", dialog.messages[0][1])

    def test_provider_pending_behavior_requires_explicit_fixture_classifier(self):
        frames = authorization("realdebrid")
        frames.insert(1, response({"fixture_pending": True}, 400))
        connections = Connections(frames)
        observed = []
        connections.connect_hook = lambda: observed.append(self.tick[0])
        bundle = self.assemble("realdebrid", connections,
            pending_response=lambda reply: reply.status == 400 and reply.body == {"fixture_pending": True})
        flow, _, _, progress, _ = self.ui_flow("realdebrid", bundle)
        self.assertEqual(flow.connect(), FlowResult.AUTHORIZED)
        self.assertEqual([round(tick, 6) for tick in observed], [0, 5, 10, 10])
        self.assertEqual(progress.closed, 1)
        self.assertEqual(self.store("realdebrid").snapshot().state, "ready")
