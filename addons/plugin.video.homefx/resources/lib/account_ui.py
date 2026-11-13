"""Inactive device-code dialogs using injected UI objects, without Kodi imports."""
import math


_PROVIDERS = {
    "trakt": ("Trakt", "https://trakt.tv/activate"),
    "realdebrid": ("Real-Debrid", "https://real-debrid.com/device"),
}


class UIError(Exception):
    """A fixed diagnostic without user codes, URLs or callback exception text."""


class AccountUI:
    """AccountFlow adapter; construction opens no dialog and reads no account.

    Inject Dialog, a DialogProgress factory and Monitor objects. Device codes are
    passed only to the display callback; the adapter does not store their strings.
    Injected objects are trusted code and must not log messages or exceptions.
    This adapter is not constructed or wired by the preview's Kodi entry point.
    """
    def __init__(self, provider, dialog, progress_factory, monitor):
        if (type(provider) is not str or provider not in _PROVIDERS
                or not callable(progress_factory)
                or not callable(getattr(dialog, "yesno", None))
                or not callable(getattr(monitor, "abortRequested", None))
                or not callable(getattr(monitor, "waitForAbort", None))):
            raise UIError("invalid_ui_configuration")
        self._provider = provider
        self._dialog, self._factory, self._monitor = dialog, progress_factory, monitor
        self._progress, self._failed = None, False

    def __repr__(self):
        return "AccountUI(<private interaction>)"

    def _check(self):
        if self._failed:
            raise UIError("ui_failed")

    def _fail(self):
        self._failed = True
        try:
            self.close()
        except UIError:
            pass
        raise UIError("ui_failed") from None

    def _confirm(self, message):
        self._check()
        try:
            result = self._dialog.yesno("HomeFX — " + _PROVIDERS[self._provider][0], message)
            if type(result) is not bool:
                raise ValueError()
            return result
        except Exception:
            self._fail()

    def confirm_replace(self):
        return self._confirm(
            "Replace the local account connection? Starting a new login removes the current "
            "local credentials even if login is cancelled. This does not revoke service access "
            "or erase backups.")

    def confirm_disconnect(self):
        details = ("Local Trakt credentials and all saved HomeFX list choices will be removed. "
                   if self._provider == "trakt" else
                   "Local Real-Debrid credentials will be removed. Trakt list choices are unchanged. ")
        return self._confirm(details + "This does not revoke service authorization or erase backups. "
                             "Disconnect locally?")

    def show_code(self, code, url):
        self._check()
        if (type(code) is not str or not 1 <= len(code) <= 128
                or any(not 32 < ord(char) < 127 or char in "[]" for char in code)
                or type(url) is not str or url != _PROVIDERS[self._provider][1]):
            self._fail()
        if self._progress is not None:
            self._fail()
        try:
            progress = self._factory()
            self._progress = progress
            if any(not callable(getattr(progress, method, None))
                   for method in ("create", "update", "close", "iscanceled")):
                raise ValueError()
            progress.create("HomeFX — Connect " + _PROVIDERS[self._provider][0],
                            "On another device, open " + url + "\nEnter code: " + code +
                            "\nKeep this dialog open. Cancel to stop. Do not share this code.")
            progress.update(0)
        except Exception:
            self._fail()

    def close(self):
        # Clear ownership before calling external cleanup: repeated close is safe.
        progress, self._progress = self._progress, None
        if progress is not None:
            try:
                progress.close()
            except Exception:
                self._failed = True
                raise UIError("ui_cleanup_failed") from None

    def cancelled(self):
        self._check()
        try:
            aborted = self._monitor.abortRequested()
            if type(aborted) is not bool:
                raise ValueError()
            if aborted:
                return True
            if self._progress is not None:
                cancelled = self._progress.iscanceled()
                if type(cancelled) is not bool:
                    raise ValueError()
                return cancelled
            return False
        except Exception:
            self._fail()

    def wait(self, seconds):
        """Wait in at most 600 short slices; return True on abort/UI cancellation.

        The monitor must honor each requested timeout. This loop never polls
        indefinitely if a fake/broken monitor returns immediately; AccountFlow's
        separate monotonic-clock check rejects a non-advancing scheduler.
        """
        self._check()
        if (type(seconds) not in (int, float) or not 0 <= seconds <= 60
                or not math.isfinite(seconds)):
            self._fail()
        if self.cancelled():
            return True
        count = math.ceil(seconds / 0.1)
        for index in range(count):
            delay = min(0.1, seconds - index * 0.1)
            try:
                aborted = self._monitor.waitForAbort(delay)
                if type(aborted) is not bool:
                    raise ValueError()
            except Exception:
                self._fail()
            if aborted or self.cancelled():
                return True
        return False
