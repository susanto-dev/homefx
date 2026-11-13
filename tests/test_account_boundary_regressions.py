"""Offline controller/UI boundaries and shared-limit transaction regressions."""
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib import account_flow, account_ui, request_limits
from resources.lib import trakt_auth, trakt_client, trakt_session, trakt_tokens


class Dialog:
    def __init__(self):
        self.on_confirm = lambda: None
        self.prompts = []

    def yesno(self, heading, message):
        self.prompts.append((heading, message))
        self.on_confirm()
        return True


class Progress:
    def __init__(self):
        self.created, self.updated, self.closed = [], [], 0

    def create(self, heading, message):
        self.created.append((heading, message))

    def update(self, percent):
        self.updated.append(percent)

    def iscanceled(self):
        return False

    def close(self):
        self.closed += 1


class Monitor:
    def __init__(self, tick):
        self.tick, self.waits = tick, []
        self.abort = False
        self.wait_result = False

    def abortRequested(self):
        return self.abort

    def waitForAbort(self, seconds):
        self.waits.append(seconds)
        self.tick[0] += seconds
        return self.wait_result


class AccountBoundaryRegressions(unittest.TestCase):
    def setUp(self):
        self.make_flow()

    def make_flow(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tick = [0.0]
        self.store = trakt_tokens.TokenStore(temporary.name)
        self.requests = []
        self.code = dict(device_code="synthetic-device", user_code="DISPLAY-ONLY",
                         verification_url="https://trakt.tv/activate", interval=5,
                         expires_in=60)
        self.issued_hook = lambda: None

        def oauth(method, path, body):
            self.requests.append(path)
            self.assertEqual(path, "/oauth/device/code", "must not poll after boundary failure")
            self.issued_hook()
            return trakt_client.Response(200, body=self.code)

        self.session = trakt_session.Session(
            self.store, oauth, None, "synthetic-client", "https://example.invalid/callback",
            clock=lambda: 1000, monotonic=lambda: self.tick[0])
        self.dialog, self.progress = Dialog(), Progress()
        self.monitor = Monitor(self.tick)
        self.factory = Mock(return_value=self.progress)
        self.ui = account_ui.AccountUI("trakt", self.dialog, self.factory, self.monitor)
        self.disconnect = Mock(side_effect=self.session.disconnect)
        self.flow = account_flow.AccountFlow(
            self.session, self.ui, self.ui.wait, self.ui.cancelled,
            lambda: self.tick[0], self.disconnect)

    def assert_abandoned(self):
        self.assertEqual(self.session.status()["login"], "idle")
        self.assertEqual(self.store.snapshot().state, "disconnected")
        self.assertEqual(self.requests, ["/oauth/device/code"])

    def test_abort_after_replacement_confirmation_preserves_original_credentials(self):
        self.store.install(trakt_auth.TokenSet("synthetic-access", "synthetic-refresh", 5000))
        before = self.store.snapshot()
        self.dialog.on_confirm = lambda: setattr(self.monitor, "abort", True)

        self.assertEqual(self.flow.connect(), account_flow.FlowResult.CANCELLED)

        self.assertEqual(self.store.snapshot(), before)
        self.assertEqual(len(self.dialog.prompts), 1)
        self.assertEqual(self.requests, [])
        self.factory.assert_not_called()

    def test_code_request_reaching_deadline_never_displays_or_polls(self):
        self.flow.max_seconds = 10
        self.issued_hook = lambda: self.tick.__setitem__(0, 10)

        self.assertEqual(self.flow.connect(), account_flow.FlowResult.TIMEOUT)

        self.assert_abandoned()
        self.factory.assert_not_called()
        self.assertEqual(self.monitor.waits, [])
        self.assertEqual(self.progress.closed, 0)

    def test_provider_accepted_prompts_rejected_by_ui_cancel_before_display(self):
        # The provider accepts these strings; the display contract is narrower.
        for changes in ({"verification_url": "https://trakt.tv/activate?synthetic=1"},
                        {"user_code": "[synthetic]"}):
            with self.subTest(changes=changes):
                self.make_flow()
                self.code.update(changes)
                self.assertEqual(self.flow.connect(), account_flow.FlowResult.FAILED)
                self.assert_abandoned()
                self.factory.assert_not_called()
                self.assertEqual(self.progress.created, [])
                self.assertEqual(self.monitor.waits, [])
                with self.assertRaisesRegex(account_ui.UIError, "^ui_failed$"):
                    self.ui.cancelled()

    def test_incomplete_progress_object_is_closed_without_display_or_polling(self):
        self.progress.iscanceled = None

        self.assertEqual(self.flow.connect(), account_flow.FlowResult.FAILED)

        self.assert_abandoned()
        self.factory.assert_called_once_with()
        self.assertEqual(self.progress.created, [])
        self.assertEqual(self.progress.updated, [])
        self.assertEqual(self.progress.closed, 1)
        self.ui.close()
        self.assertEqual(self.progress.closed, 1)

    def test_nonboolean_monitor_wait_fails_and_closes_open_login(self):
        self.monitor.wait_result = "synthetic-private-monitor-value"

        result = self.flow.connect()

        self.assertEqual(result, account_flow.FlowResult.FAILED)
        self.assertNotIn("synthetic", repr(result))
        self.assert_abandoned()
        self.assertEqual(len(self.progress.created), 1)
        self.assertEqual(len(self.monitor.waits), 1)
        self.assertEqual(self.progress.closed, 1)
        with self.assertRaisesRegex(account_ui.UIError, "^ui_failed$"):
            self.ui.wait(0)

    def test_system_abort_does_not_probe_progress_after_abort(self):
        original_create = self.progress.create

        def create(heading, message):
            original_create(heading, message)
            self.monitor.abort = True

        self.progress.create = create
        self.progress.iscanceled = Mock(side_effect=RuntimeError("synthetic-private-value"))

        self.assertEqual(self.flow.connect(), account_flow.FlowResult.CANCELLED)

        self.assert_abandoned()
        self.progress.iscanceled.assert_not_called()
        self.assertEqual(self.monitor.waits, [])
        self.assertEqual(self.progress.closed, 1)

    def test_abort_after_disconnect_confirmation_never_invokes_cleanup(self):
        self.store.install(trakt_auth.TokenSet("synthetic-access", "synthetic-refresh", 5000))
        before = self.store.snapshot()
        self.dialog.on_confirm = lambda: setattr(self.monitor, "abort", True)

        self.assertEqual(self.flow.disconnect(), account_flow.FlowResult.CANCELLED)

        self.disconnect.assert_not_called()
        self.assertEqual(self.store.snapshot(), before)
        self.assertEqual(self.requests, [])


class SharedLimitBoundaryRegressions(unittest.TestCase):
    def test_server_cooldown_and_full_window_both_gate_new_issued_attempts(self):
        for server_delay, expected_wait in ((30, 60), (90, 90)):
            with self.subTest(server_delay=server_delay), tempfile.TemporaryDirectory() as profile:
                tick = [1000]
                limits = request_limits.RequestLimits(profile, "realdebrid", clock=lambda: tick[0])
                for _ in range(250):
                    self.assertEqual(limits.reserve(), 0)
                limits.observe(429, {"Retry-After": str(server_delay)})
                other = request_limits.RequestLimits(profile, "realdebrid", clock=lambda: tick[0])
                self.assertEqual(other.reserve(), expected_wait)
                tick[0] = 1000 + min(server_delay, 60)
                self.assertEqual(other.reserve(), abs(server_delay - 60))
                tick[0] = 1000 + max(server_delay, 60)
                self.assertEqual(other.reserve(), 0)
                with sqlite3.connect(str(Path(profile) / "limits/requests.sqlite3")) as connection:
                    self.assertEqual(connection.execute("SELECT provider,stamp FROM issued").fetchall(),
                                     [("realdebrid", tick[0])])

    def test_failed_state_update_rolls_back_reservation_and_clock(self):
        with tempfile.TemporaryDirectory() as profile:
            tick = [1001]
            limits = request_limits.RequestLimits(profile, "realdebrid", clock=lambda: tick[0])
            path = Path(profile) / "limits/requests.sqlite3"
            with sqlite3.connect(str(path)) as connection:
                connection.execute("CREATE TRIGGER reject_state BEFORE UPDATE ON state "
                                   "BEGIN SELECT RAISE(ABORT, 'synthetic-storage-failure'); END")
            with self.assertRaisesRegex(request_limits.LimitError, "^limit_store_unavailable$"):
                limits.reserve()
            with sqlite3.connect(str(path)) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM issued").fetchone(), (0,))
                self.assertEqual(connection.execute(
                    "SELECT cooldown,last FROM state WHERE provider='realdebrid'").fetchone(), (0, 0))
                connection.execute("DROP TRIGGER reject_state")
            tick[0] = 1000
            self.assertEqual(limits.reserve(), 0)
            with sqlite3.connect(str(path)) as connection:
                self.assertEqual(connection.execute("SELECT stamp FROM issued").fetchall(), [(1000,)])


if __name__ == "__main__":
    unittest.main()
