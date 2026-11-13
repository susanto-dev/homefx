"""Explicit Development-only device wiring; never imported by the public preview."""
from dataclasses import dataclass, field
import http.client
from pathlib import Path
import time

from . import storage_probe, trakt_auth, trakt_session, trakt_tokens, trakt_transport
from .development_config import DevelopmentError, load_config, scoped_profile, validate_config as validate_config
from .account_flow import AccountFlow, FlowResult
from .account_ui import AccountUI
from .request_limits import RequestLimits


ADDON_ID = "script.homefx.development"
TITLE = "HomeFX Development Test"
FAILURE = "Test unavailable or failed. No success is established. No private details are shown."
CLEANUP_FAILURE = "UI cleanup unconfirmed. No success is established. A refresh may require login again."
ACTIONS = ("Test this add-on's private storage", "Local connection status (no network)",
           "Connect Development Trakt", "Test one refresh rotation", "Disconnect this test locally")
STATES = {"disconnected": "disconnected", "ready": "credentials stored",
          "refresh_required": "refresh required", "refreshing": "refresh in progress",
          "reauth": "login required"}


class _Cancelled(Exception):
    """Local control flow after UI creation; cleanup must still finish."""


def _no_api(*args, **kwargs):
    raise DevelopmentError("operation_not_available")


class LoginDiagnostics:
    """Invocation-only fixed labels; never retain bodies, codes or exception text."""
    STAGES = {
        "account": "local account preparation", "account_check": "local authorization state",
        "device_request": "device code request", "device_response": "device response validation",
        "grant_request": "token request", "grant_response": "token response validation",
        "dialog": "authorization dialog", "waiting": "authorization wait",
    }
    CATEGORIES = {
        "unavailable": "unavailable", "cancelled": "cancelled", "timeout": "timeout",
        "invalid_response": "response rejected", "redirect_refused": "redirect refused",
        "response_too_large": "response too large", "invalid_json": "response format rejected",
        "transport_failed": "request unavailable (network, TLS or local request guard)",
        "status": "request status rejected", "dialog": "code display unavailable",
    }

    def __init__(self):
        self.stage, self.category, self.status = "account", "unavailable", None

    def __repr__(self):
        return "LoginDiagnostics(<fixed categories>)"

    def request(self, callback, method, path, body):
        device = path == "/oauth/device/code"
        self.stage = "device_request" if device else "grant_request"
        self.category, self.status = "unavailable", None
        try:
            response = callback(method, path, body)
        except trakt_transport.TransportError as error:
            if (len(error.args) == 1 and type(error.args[0]) is str
                    and error.args[0] in self.CATEGORIES):
                self.category = error.args[0]
            raise
        self.stage = "device_response" if device else "grant_response"
        if type(response.status) is int and 100 <= response.status <= 599:
            self.status = response.status
            if response.status != 200:
                self.category = "status"
        return response

    def report(self):
        # Only enumerated literals and a bounded integer reach the result dialog.
        stage = self.STAGES.get(self.stage, "unavailable")
        category = self.CATEGORIES.get(self.category, "unavailable")
        status = (str(self.status) if type(self.status) is int and 100 <= self.status <= 599
                  else "unavailable")
        return ("\nLast stage: " + stage + "\nCategory: " + category + "\nResponse status: " + status
                + "\nA status may come from a local request limit; it does not prove service access.")


class DiagnosticSession(trakt_session.Session):
    def begin_login(self, expected_generation=None):
        self.diagnostics.stage = "account"
        prompt = super().begin_login(expected_generation=expected_generation)
        self.diagnostics.stage = "account_check"
        return prompt


@dataclass(repr=False)
class Runtime:
    store: object = field(repr=False)
    session: object = field(repr=False)
    oauth: object = field(repr=False)
    diagnostics: object = field(default=None, repr=False)

    def __repr__(self):
        return "DevelopmentRuntime(<private connection>)"


def assemble(profile, config, cancelled, *, clock=time.time, monotonic=time.monotonic,
             connection_factory=http.client.HTTPSConnection):
    """Only Trakt storage and OAuth wiring; construction performs no network call."""
    limits = RequestLimits(profile, "trakt", clock=clock)
    transport = trakt_transport.Transport(cancelled=cancelled, rate_limits=limits,
        clock=monotonic, connection_factory=connection_factory)
    store = trakt_tokens.TokenStore(profile, clock=clock)
    diagnostics = LoginDiagnostics()
    def request(method, path, body):
        return diagnostics.request(transport.oauth_request, method, path, body)
    session = DiagnosticSession(store, request, _no_api,
                                    config["client_id"], config["redirect_uri"],
                                    clock=clock, monotonic=monotonic)
    session.diagnostics = diagnostics
    return Runtime(store, session, request, diagnostics)


class TestUI(AccountUI):
    diagnostics = None

    def show_code(self, code, url):
        if self.diagnostics is not None:
            self.diagnostics.stage = "dialog"
            self.diagnostics.category = "dialog"
        super().show_code(code, url)
        if self.diagnostics is not None:
            self.diagnostics.stage = "waiting"
            self.diagnostics.category = "unavailable"

    def confirm_disconnect(self):
        return self._confirm(
            "Remove credentials for this Development test scope only? The public HomeFX "
            "profile is unchanged. This does not revoke Trakt authorization or erase backups. "
            "Revoke application access separately in Trakt account settings.")


def _consent(action):
    if action == 2:
        return ("Start a Development Trakt login on this TV? This contacts Trakt and can store "
                "unencrypted tokens in this test add-on's private profile. Other code running "
                "as Kodi and profile backups may access them. No lists or history will be read. "
                "Use only the trusted Trakt activation address shown on your own device; never share codes. "
                "Public HomeFX remains inactive.")
    if action == 3:
        return ("Test one live refresh rotation? This consumes the stored refresh token. "
                "A cancelled, interrupted or failed request can require login again. No retry "
                "or list request follows. Never share tokens, codes, paths or backups.")
    return ("Open this Development test's local storage for the selected check? Synthetic "
            "files or empty test stores may be created. No network request is made. "
            "This never changes the public HomeFX profile. Never share paths or backups.")


def _local_runtime(profile, config, *, clock=time.time):
    store = trakt_tokens.TokenStore(profile, clock=clock)
    return Runtime(store, trakt_session.Session(store, _no_api, _no_api,
                   config["client_id"], config["redirect_uri"], clock=clock), _no_api)


def run(addon, dialog, progress_factory, monitor, translate_path, *,
        factory=assemble, local_factory=_local_runtime, probe=storage_probe.report,
        clock=time.monotonic):
    """Run one action; return False only when fixed outcome delivery is unavailable.

    Cancel/denial never reads config or profile. Cleanup failure replaces any
    success result; callback exception details are never displayed.
    """
    progress = None
    ui = None
    outcome = None
    try:
        action = dialog.select(TITLE + " — no public live routes", list(ACTIONS))
        if type(action) is not int or action not in range(len(ACTIONS)) or monitor.abortRequested():
            return True
        if dialog.yesno(TITLE, _consent(action)) is not True or monitor.abortRequested():
            return True
        if addon.getAddonInfo("id") != ADDON_ID:
            raise DevelopmentError("unexpected_test_addon")
        config = load_config(Path(addon.getAddonInfo("path")) / "resources" / "development.json")
        profile = scoped_profile(translate_path(addon.getAddonInfo("profile")), config)
        if action in (0, 2, 3):
            report = probe(profile)
            if action == 0 or "Overall: passed" not in report.splitlines():
                dialog.textviewer(TITLE + " — private storage", report)
                return True
        if monitor.abortRequested():
            return True
        ui = TestUI("trakt", dialog, progress_factory, monitor)
        if action == 3:
            progress = progress_factory()
            progress.create(TITLE, "One refresh attempt. Cancel may require login again. No list requests.")
            def cancelled():
                return monitor.abortRequested() or progress.iscanceled()
            if cancelled():
                raise _Cancelled()
            runtime = factory(profile, config, cancelled)
            status = runtime.session.status()
            if status["state"] not in ("ready", "refresh_required"):
                outcome = "Refresh not run: local connection is not ready. Login may be required."
            elif cancelled():
                raise _Cancelled()
            else:
                tokens = trakt_auth.refresh_tokens(runtime.store, runtime.oauth,
                    config["client_id"], config["redirect_uri"], status["generation"])
                # A rotated token must also be usable and still belong to this attempt.
                # Never put tokens or generations in an outcome string.
                rotated = tokens is not None
                tokens = None
                after = runtime.session.status()
                expected = status["generation"] + 1
                if rotated and after["generation"] == expected and after["state"] == "ready":
                    outcome = "Refresh rotation: passed. No list or history request was made."
                else:
                    if (rotated and after["generation"] == expected
                            and after["state"] == "refresh_required"):
                        runtime.session.disconnect(expected_generation=expected)
                    outcome = "Refresh not completed: session changed, busy or login required."
        else:
            runtime = (factory(profile, config, ui.cancelled) if action == 2
                       else local_factory(profile, config))
            if action == 1:
                state = runtime.session.status()["state"]
                outcome = "Local status: " + STATES.get(state, "unavailable") + ". No network test was run."
            else:
                ui.diagnostics = runtime.diagnostics
                flow = AccountFlow(runtime.session, ui, ui.wait, ui.cancelled,
                                   clock, runtime.session.disconnect)
                result = flow.connect() if action == 2 else flow.disconnect()
                outcome = "Connection test: " + FlowResult(result).value + "."
                if action == 4:
                    outcome += " Local deletion is not remote revocation or backup erasure."
                else:
                    if result == FlowResult.FAILED and runtime.diagnostics is not None:
                        outcome += runtime.diagnostics.report()
                    if result == FlowResult.AUTHORIZED:
                        outcome += " Authorization does not validate refresh, lists or public preview activation."
                    else:
                        outcome += " No successful authorization is established. Stop and report fixed results only."
    except _Cancelled:
        outcome = None
    except Exception:
        outcome = FAILURE + " A failed refresh may require login again."
    finally:
        for item in (progress, ui):
            if item is not None:
                try:
                    item.close()
                except Exception:
                    outcome = CLEANUP_FAILURE

    if outcome is None:
        return True
    try:
        dialog.textviewer(TITLE, outcome)
    except Exception:
        return False
    return True
