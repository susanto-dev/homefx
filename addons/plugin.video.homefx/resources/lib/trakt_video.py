"""Joined read-only video interactions; the public preview does not dispatch these.

The caller supplies a trusted, lazy runtime factory bound to the video add-on's
own profile and reviewed public configuration. No test credentials are imported.
This module imports no Kodi APIs and constructs no runtime on import or creation.
"""
import time

from .account_flow import AccountFlow, FlowResult
from .account_ui import AccountUI
from .trakt_list_ui import ListResult, TraktListUI
from .trakt_widget_ui import WidgetDirectoryUI
from . import trakt_widget_routes


class TraktVideo:
    """One invocation joins shared auth, local selection and read-only directories.

    factory(cancelled=callback) must return the existing read-only Trakt bundle.
    The same active UI cancellation callback reaches transport and interaction.
    Returned chooser rows are private invocation data, never diagnostics or URLs.
    This boundary is not an activation gate or an application configuration loader.
    """
    def __init__(self, factory, dialog, progress_factory, monitor, plugin,
                 list_item_factory, *, clock=time.monotonic, art_root=None, addon_id='plugin.video.homefx'):
        if not all(callable(item) for item in (factory, progress_factory, list_item_factory, clock)):
            raise ValueError('invalid_video_configuration')
        trakt_widget_routes.url('trakt_sources', addon_id=addon_id)
        self._addon_id = addon_id
        self._factory, self._dialog, self._progress = factory, dialog, progress_factory
        self._monitor, self._plugin, self._item = monitor, plugin, list_item_factory
        self._clock, self._art = clock, art_root

    def __repr__(self):
        return 'TraktVideo(<private interaction>)'

    def dispatch(self, action, *, handle=None, query='', widget=False):
        """Run one explicit action; bad routes never create stores or contact services.

        Account/selection actions require consent before opening local stores.
        Reads never initiate login, show consent, or silently substitute demo data.
        Widgets use monitor cancellation without opening progress or error dialogs.
        The caller must independently authorize live wiring before invoking this.
        """
        ui, route = None, None
        try:
            if type(widget) is not bool or type(query) is not str:
                raise ValueError()
            if action == 'browse':
                if type(handle) is not int or handle < 0:
                    raise ValueError()
                route, _ = trakt_widget_routes.parse(query)
                if widget and route in {'trakt_details', 'trakt_episode_details'}:
                    raise ValueError()
            elif action not in {'connect', 'disconnect', 'choose'} or widget or handle is not None or query:
                raise ValueError()
        except (TypeError, ValueError):
            if action == 'browse' and type(handle) is int and handle >= 0:
                return self._unstarted_read(None, handle, ListResult('failed'))
            return ListResult('failed')

        try:
            if action == 'browse':
                ui = WidgetDirectoryUI(self._plugin, self._item, self._progress,
                    self._monitor, dialog=self._dialog, art_root=self._art, addon_id=self._addon_id)
            elif action == 'choose':
                ui = TraktListUI(self._dialog, self._progress, self._monitor)
            else:
                ui = AccountUI('trakt', self._dialog, self._progress, self._monitor)
            if ui.cancelled():
                if action == 'browse':
                    return self._unstarted_read(route, handle, ListResult('cancelled'))
                return FlowResult.CANCELLED if action in {'connect', 'disconnect'} else ListResult('cancelled')
            if action != 'browse':
                consent = self._dialog.yesno('HomeFX — Trakt', self._consent(action))
                if type(consent) is not bool:
                    raise ValueError()
                if not consent or ui.cancelled():
                    return FlowResult.CANCELLED if action in {'connect', 'disconnect'} else ListResult('cancelled')
            runtime = self._factory(cancelled=ui.cancelled)
            if action == 'browse':
                return ui.render(runtime.library, handle, query, widget=widget)
            if action == 'choose':
                return ui.choose(runtime.library)
            flow = AccountFlow(runtime.session, ui, ui.wait, ui.cancelled,
                               self._clock, runtime.disconnect)
            return flow.connect() if action == 'connect' else flow.disconnect()
        except Exception:
            if action == 'browse':
                # Construction can fail before the renderer owns directory cleanup.
                # Never expose an exception, profile, public identity or credential.
                return self._unstarted_read(route, handle, ListResult('failed'))
            return FlowResult.FAILED if action in {'connect', 'disconnect'} else ListResult('failed')

    def _unstarted_read(self, route, handle, result):
        if route in {'trakt_details', 'trakt_episode_details'}:
            if result.state != 'cancelled':
                try:
                    self._dialog.textviewer('HomeFX', result.message)
                except Exception:
                    result = ListResult('failed')
        else:
            for callback in (
                lambda: self._plugin.setPluginCategory(handle, result.message),
                lambda: self._plugin.endOfDirectory(handle, succeeded=False, cacheToDisc=False),
            ):
                try:
                    callback()
                except Exception:
                    result = ListResult('failed')
        return result

    @staticmethod
    def _consent(action):
        if action == 'connect':
            return ('Connect Trakt in this video add-on? This contacts Trakt and stores unencrypted '
                    'credentials in its own private profile. Other Kodi code and backups may access them. '
                    'No test credentials are imported. No playback or history/list writes are enabled.')
        if action == 'choose':
            return ('Read your personal and liked Trakt lists and save choices locally in HomeFX? '
                    'This may refresh your connection. Configure skin widget rows separately. '
                    'No remote list/history changes or playback are enabled.')
        return ('Open this video add-on\'s local Trakt account state to disconnect? '
                'A separate confirmation removes credentials and saved HomeFX list choices. '
                'No network request is made. This does not revoke service access or erase backups.')
