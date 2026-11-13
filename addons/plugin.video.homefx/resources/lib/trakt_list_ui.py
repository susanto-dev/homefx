"""Inactive read-only list interaction using the existing Library and injected UI.

No Kodi imports, routes, account configuration or transport construction. Results
contain private invocation data; callers must not log them or cache them on disk.
"""
from dataclasses import dataclass, field

from .trakt_auth import AuthError
from .trakt_client import ApiError


_MESSAGES = {
    "ready": "Titles are metadata; no playable availability is established.",
    "empty": "No entries in this view.",
    "partial": "Some list entry types are not supported; this is not the complete list.",
    "saved": "HomeFX list choices saved. Configure each skin widget row separately.",
    "cancelled": "Cancelled. No new results are shown.",
    "authorization_needed": "Trakt authorization is needed. Open account setup in HomeFX.",
    "offline": "Connection unavailable. Check network/TLS and try again explicitly.",
    "changed": "Account or list choices changed. Reopen the view before continuing.",
    "busy": "A request or refresh is already in progress. Try again later.",
    "limited": "Service or account limit reached. Try again later.",
    "unavailable": "This list or view is unavailable. Review your choices in HomeFX.",
    "failed": "The view could not be loaded safely. No new results are shown.",
}


@dataclass(frozen=True)
class ListResult:
    state: str
    rows: tuple = field(default=(), repr=False)
    unsupported_count: int = 0

    @property
    def message(self):
        return _MESSAGES[self.state]


def _error_state(error):
    kind = getattr(error, "kind", error.args[0] if error.args else "")
    if kind in {"reauthenticate", "reauthentication_required"}:
        return "authorization_needed"
    if kind in {"session_changed", "data_changed", "preferences_changed"}:
        return "changed"
    if kind in {"refresh_busy", "action_in_progress"}:
        return "busy"
    if kind in {"rate_limit", "account_limit"}:
        return "limited"
    if kind in {"unavailable", "unavailable_selection"}:
        return "unavailable"
    if kind == "transport":
        return "offline"
    return "failed"


class TraktListUI:
    """A narrow adapter for the future gated Kodi entry point.

    Inject Dialog.multiselect, DialogProgress and Monitor objects. Pass cancelled
    to the service factory too so transport observes cancellation during reads.
    Widget reads never open dialogs. Results must be rendered as one completed
    directory, with failures clearing prior rows; no partial rows are emitted here.
    No widget URL identity or public route is allocated by this adapter.
    """
    def __init__(self, dialog, progress_factory, monitor):
        self._dialog = dialog
        self._factory, self._monitor = progress_factory, monitor
        self._progress = None

    def __repr__(self):
        return "TraktListUI(<private interaction>)"

    def cancelled(self):
        aborted = self._monitor.abortRequested()
        if type(aborted) is not bool:
            raise ValueError("invalid_ui_result")
        if aborted:
            return True
        if self._progress is not None:
            cancelled = self._progress.iscanceled()
            if type(cancelled) is not bool:
                raise ValueError("invalid_ui_result")
            return cancelled
        return False

    def _close(self):
        progress, self._progress = self._progress, None
        if progress is not None:
            progress.close()

    def _run(self, library, operation, widget=False, choosing=False):
        result = ListResult("failed")
        guard = None
        try:
            if self.cancelled():
                return ListResult("cancelled")
            if not widget:
                self._progress = self._factory()
                self._progress.create("HomeFX — Trakt lists", "Loading read-only account data…")
                self._progress.update(0)
            if self.cancelled():
                self._close()
                return ListResult("cancelled")
            payload = operation()
            if payload is not None:
                guard = library.capture_view_guard()
            if payload is None or (not choosing and self.cancelled()):
                result = ListResult("cancelled")
            elif choosing:
                result = ListResult("saved", tuple(payload))
            else:
                rows, unsupported = payload["items"], payload["unsupported_count"]
                state = "partial" if unsupported else "ready" if rows else "empty"
                result = ListResult(state, tuple(rows), unsupported)
        except (AuthError, ApiError) as error:
            try:
                result = ListResult("cancelled" if self.cancelled() else _error_state(error))
            except Exception:
                result = ListResult("failed")
        except Exception:
            result = ListResult("failed")
        finally:
            try:
                self._close()
            except Exception:
                result = ListResult("failed")
        if result.state in {"ready", "empty", "partial", "saved"}:
            try:
                if not choosing and self.cancelled():
                    return ListResult("cancelled")
                guard()
            except (AuthError, ApiError) as error:
                return ListResult(_error_state(error))
            except Exception:
                return ListResult("failed")
        return result

    def choose(self, library):
        """Explicit local selection only; cancellation never becomes an empty save."""
        def chooser(refs, selected):
            cancelled = self.cancelled()
            self._close()
            if cancelled or self.cancelled():
                return None
            # Names are display-only. Commands/URLs never contain service text.
            labels = [ref.name.replace("[", "(").replace("]", ")") for ref in refs]
            answer = self._dialog.multiselect("Select Trakt lists for HomeFX", labels,
                       preselect=[i for i, ref in enumerate(refs) if ref.key in selected])
            if answer is None or self.cancelled():
                return None
            if (type(answer) is not list or len(set(answer)) != len(answer)
                    or any(type(i) is not int or not 0 <= i < len(refs) for i in answer)):
                raise ValueError("invalid_ui_result")
            return [refs[i].key for i in answer]
        return self._run(library, lambda: library.choose_lists(chooser), choosing=True)

    def list(self, library, key, widget=False):
        return self._run(library, lambda: library.browse_list(key), widget=widget)

    def seasons(self, library, show_id):
        return self._run(library, lambda: {"items": library.series_seasons(show_id),
                                 "unsupported_count": 0})

    def episodes(self, library, show_id, season):
        return self._run(library, lambda: {"items": library.episode_view(show_id, season),
                                 "unsupported_count": 0})
