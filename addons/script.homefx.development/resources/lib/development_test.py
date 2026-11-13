"""Explicit Development-only device wiring; never imported by the public preview."""
from dataclasses import dataclass, field
import hashlib
import http.client
import json
from pathlib import Path
import stat
import time

from . import service_runtime, storage_probe, trakt_auth, trakt_session, trakt_tokens, trakt_transport
from .account_flow import AccountFlow, FlowResult
from .account_ui import AccountUI
from .request_limits import RequestLimits


ADDON_ID = "script.homefx.development"
MAX_CONFIG_BYTES = 4096
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


class DevelopmentError(ValueError):
    """Fixed error only; no configuration, code, token or path values."""


def validate_config(value):
    if (type(value) is not dict
            or set(value) != {"schema", "environment", "client_id", "redirect_uri"}
            or type(value["schema"]) is not int or value["schema"] != 1
            or value["environment"] != "Development"
            or type(value["client_id"]) is not str
            or not trakt_auth._text(value["client_id"], 256)
            or not service_runtime._redirect(value["redirect_uri"])):
        raise DevelopmentError("invalid_development_configuration")
    return dict(value)


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DevelopmentError("invalid_development_configuration")
        result[key] = value
    return result


def load_config(path):
    try:
        path = Path(path).absolute()
        if any(part.is_symlink() for part in (path,) + tuple(path.parents)):
            raise ValueError()
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError()
        with path.open('rb') as stream:
            raw = stream.read(MAX_CONFIG_BYTES + 1)
        if len(raw) > MAX_CONFIG_BYTES:
            raise ValueError()
        return validate_config(json.loads(raw.decode('utf-8'), object_pairs_hook=_unique))
    except Exception:
        raise DevelopmentError("invalid_development_configuration") from None


def scoped_profile(profile, config):
    config = validate_config(config)
    base = storage_probe._safe_profile(profile)
    identity = json.dumps([config["client_id"], config["redirect_uri"]],
                          ensure_ascii=True, separators=(',', ':')).encode('utf-8')
    path = base / ("development-" + hashlib.sha256(identity).hexdigest())
    # Includes existing database and sidecar checks before constructors mutate anything.
    return service_runtime._profile(path, "trakt")


def _no_api(*args, **kwargs):
    raise DevelopmentError("operation_not_available")


@dataclass(repr=False)
class Runtime:
    store: object = field(repr=False)
    session: object = field(repr=False)
    oauth: object = field(repr=False)

    def __repr__(self):
        return "DevelopmentRuntime(<private connection>)"


def assemble(profile, config, cancelled, *, clock=time.time, monotonic=time.monotonic,
             connection_factory=http.client.HTTPSConnection):
    """Only Trakt storage and OAuth wiring; construction performs no network call."""
    limits = RequestLimits(profile, "trakt", clock=clock)
    transport = trakt_transport.Transport(cancelled=cancelled, rate_limits=limits,
        clock=monotonic, connection_factory=connection_factory)
    store = trakt_tokens.TokenStore(profile, clock=clock)
    session = trakt_session.Session(store, transport.oauth_request, _no_api,
                                    config["client_id"], config["redirect_uri"],
                                    clock=clock, monotonic=monotonic)
    return Runtime(store, session, transport.oauth_request)


class TestUI(AccountUI):
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
                "Authorize only at https://trakt.tv/activate on your own device; never share codes. "
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
                flow = AccountFlow(runtime.session, ui, ui.wait, ui.cancelled,
                                   clock, runtime.session.disconnect)
                result = flow.connect() if action == 2 else flow.disconnect()
                outcome = "Connection test: " + FlowResult(result).value + "."
                if action == 4:
                    outcome += " Local deletion is not remote revocation or backup erasure."
                else:
                    outcome += " Authorization does not validate refresh, lists or public preview activation."
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
