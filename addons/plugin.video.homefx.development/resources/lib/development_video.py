"""Deliberate Development video wiring using shared read-only components."""
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

from . import development_config, service_runtime, storage_probe, trakt_tokens
from . import trakt_widget_routes as routes
from .trakt_video import TraktVideo
from .trakt_widget_ui import WidgetDirectoryUI
from .account_flow import FlowResult

ADDON_ID = 'plugin.video.homefx.development'
TITLE = 'HomeFX Development Video'
ACTIONS = {'probe', 'status', 'connect', 'choose', 'disconnect', 'widget_help', 'device_info'}
STATES = {'disconnected': 'disconnected', 'ready': 'credentials stored',
          'refresh_required': 'refresh required', 'refreshing': 'refresh in progress',
          'reauth': 'login required'}


def _finish(plugin, handle, succeeded):
    if type(handle) is int and handle >= 0:
        plugin.endOfDirectory(handle, succeeded=succeeded, cacheToDisc=False)


def run(argv, addon, dialog, progress_factory, monitor, plugin, item_factory, translate,
        *, runtime_factory=service_runtime.build_trakt, probe=storage_probe.report, clock=time.monotonic, local_info=None):
    """Menus open no stores. Account data belongs only to this add-on's own profile.

    Directory reads are deliberately silent, including skin widget refreshes.
    Kodi owns directory loading display; details are explicit nonfolder actions.
    No arbitrary endpoint, profile, identity, write or playback input is accepted.
    """
    handle = None
    try:
        if (addon.getAddonInfo('id') != ADDON_ID or len(argv) < 2
                or argv[0] != 'plugin://' + ADDON_ID + '/'):
            raise ValueError()
        handle = int(argv[1])
        query = argv[2] if len(argv) > 2 else ''
        if type(query) is not str or len(query) > 512:
            raise ValueError()
        query = query[1:] if query.startswith('?') else query
        if not query:
            if handle < 0:
                raise ValueError()
            plugin.setPluginCategory(handle, TITLE + ' — read-only; no playback')
            for label, action in (
                ('Widget folders (choose in your skin)', 'widget_menu'),
                ('Widget setup help', 'widget_help'),
                ('Device / build information (no network)', 'device_info'),
                ('Test this video add-on\'s private storage', 'probe'),
                ('Local connection status (no network)', 'status'),
                ('Connect Development Trakt', 'connect'),
                ('Choose personal or liked lists', 'choose'),
                ('Selected lists / widget sources', 'sources'),
                ('Movie progress views / widgets (reads Trakt history)', 'movie_sources'),
                ('Disconnect this video add-on locally', 'disconnect')):
                target = (routes.url('trakt_' + action, addon_id=ADDON_ID) if action in {'sources', 'movie_sources', 'widget_menu'}
                          else 'plugin://' + ADDON_ID + '/?' + urlencode({'action': action}))
                if plugin.addDirectoryItem(handle, target, item_factory(label=label), action in {'sources', 'movie_sources', 'widget_menu'}) is False:
                    raise ValueError()
            _finish(plugin, handle, True)
            return True
        pairs = parse_qsl(query, strict_parsing=True, keep_blank_values=True, max_num_fields=5)
        data = dict(pairs)
        if len(data) != len(pairs):
            raise ValueError()
        if 'action' in data:
            if set(data) != {'action'} or data['action'] not in ACTIONS:
                raise ValueError()
            action, route = data['action'], None
        else:
            route, _ = routes.parse(query)
            action = 'browse'
        if monitor.abortRequested():
            _finish(plugin, handle, False)
            return False

        if action == 'widget_help':
            dialog.textviewer(TITLE + ' — Widget setup',
                '1. Keep your current skin. Choose personal or liked lists in HomeFX first.\n'
                '2. In the skin widget picker, browse Video add-ons > HomeFX Development Video > Widget folders.\n'
                '3. Choose Selected lists, Movie progress, or Shows and episodes. Select the final content folder, not a category.\n'
                '4. Create each skin row separately. HomeFX never edits your skin configuration.\n'
                'Use a separate full-list menu shortcut if the row heading cannot open it.\n'
                'Movie progress reads history; show views can read every regular season. Titles are not playable sources.\n'
                'Keep existing login and lists after updates. Restart Kodi, then check Back, focus and first/repeat load times.\n'
                'Exact skin picker behavior remains a TV check. No network or account storage was accessed by this help.')
            _finish(plugin, handle, False)
            return True
        if action == 'device_info':
            message = local_info() if callable(local_info) else 'Local device/build information unavailable.'
            dialog.textviewer(TITLE + ' — Device / build information', message)
            _finish(plugin, handle, False)
            return True
        if route == 'trakt_widget_menu':
            result = WidgetDirectoryUI(plugin, item_factory, progress_factory, monitor,
                dialog=dialog, addon_id=ADDON_ID).render(None, handle, query, widget=True)
            return result.state == 'ready'

        def context():
            config = development_config.load_config(
                Path(addon.getAddonInfo('path')) / 'resources' / 'development.json')
            profile = development_config.scoped_profile(
                translate('special://profile/addon_data/' + ADDON_ID + '/'), config)
            return profile, config

        if action in {'probe', 'status'}:
            if (dialog.yesno(TITLE, 'Check this video add-on\'s own local storage? No network request. '
                             'Never share tokens, codes, profile paths or backups.') is not True
                    or monitor.abortRequested()):
                _finish(plugin, handle, False)
                return False
            profile, _ = context()
            if action == 'probe':
                message = probe(profile)
            else:
                status = trakt_tokens.TokenStore(profile).snapshot().state
                message = 'Local status: ' + STATES.get(status, 'unavailable') + '. No network test was run.'
            dialog.textviewer(TITLE, message)
            _finish(plugin, handle, False)
            return True

        def factory(*, cancelled):
            if cancelled():
                raise ValueError()
            profile, config = context()
            if action == 'connect':
                report = probe(profile)
                if 'Overall: passed' not in report.splitlines():
                    dialog.textviewer(TITLE + ' — private storage', report)
                    raise ValueError()
            if cancelled():
                raise ValueError()
            return runtime_factory(profile, config['client_id'], config['redirect_uri'], cancelled=cancelled)

        app = TraktVideo(factory, dialog, progress_factory, monitor, plugin, item_factory,
                         clock=clock, addon_id=ADDON_ID, art_root=str(Path(addon.getAddonInfo('path')) / 'resources' / 'art') + '/')
        if action == 'browse':
            # Widget refresh must never open consent/progress/error dialogs.
            details = route in {'trakt_details', 'trakt_episode_details', 'trakt_continue_details'}
            result = app.dispatch('browse', handle=handle, query=query, widget=not details)
            return result.state in {'ready', 'partial', 'empty'}
        result = app.dispatch(action)
        message = ('Connection: ' + result.value + '.' if isinstance(result, FlowResult)
                   else result.message)
        dialog.textviewer(TITLE, message + '\nRead-only Development candidate. No playback or remote writes.')
        _finish(plugin, handle, False)
        return True
    except Exception:
        # Untrusted exceptions, service text and configuration never enter UI/logs.
        try:
            _finish(plugin, handle, False)
        except Exception:
            return False
        return False
