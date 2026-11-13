"""Inactive Kodi-shaped read directory renderer with no imports or activation of Kodi."""
import unicodedata

from .trakt_auth import AuthError
from .trakt_client import ApiError
from .trakt_list_ui import ListResult, _error_state
from . import trakt_widget_routes as routes


def _text(value):
    if type(value) is not str or len(value) > 4096:
        raise ValueError('invalid_display_text')
    return ''.join(' ' if unicodedata.category(char).startswith('C') else
                   '(' if char == '[' else ')' if char == ']' else char for char in value)


class WidgetDirectoryUI:
    """Stage a complete read before submission; private Kodi disk caching is disabled.

    Inject xbmcplugin, xbmcgui.ListItem, DialogProgress and Monitor objects. Pass
    cancelled to the service factory before explicit reads. Constructor has no I/O.
    Kodi submission/finalization is not a transaction: final guard failures end the
    directory unsuccessfully, but actual skin retention/clearing needs device tests.
    """
    def __init__(self, plugin, list_item_factory, progress_factory, monitor, dialog=None, art_root=None):
        self._plugin, self._item = plugin, list_item_factory
        self._progress_factory, self._monitor = progress_factory, monitor
        self._progress = None
        self._dialog = dialog
        # The caller supplies the installed add-on's local original-art directory.
        if art_root is not None and (type(art_root) is not str or not art_root.startswith('/')
                or not art_root.endswith('/') or '://' in art_root or '..' in art_root.split('/')
                or any(unicodedata.category(c).startswith('C') for c in art_root)):
            raise ValueError('invalid_art_root')
        self._art = {} if art_root is None else {
            'thumb': art_root + 'poster.png', 'poster': art_root + 'poster.png',
            'icon': art_root + 'icon.png', 'fanart': art_root + 'fanart.png'}

    def __repr__(self):
        return 'WidgetDirectoryUI(<private interaction>)'

    def cancelled(self):
        aborted = self._monitor.abortRequested()
        if type(aborted) is not bool:
            raise ValueError('invalid_ui_result')
        if aborted:
            return True
        if self._progress is not None:
            cancelled = self._progress.iscanceled()
            if type(cancelled) is not bool:
                raise ValueError('invalid_ui_result')
            return cancelled
        return False

    def _close(self):
        progress, self._progress = self._progress, None
        if progress is not None:
            progress.close()

    @staticmethod
    def _read(library, route, params):
        if route == 'trakt_sources':
            return library.widget_sources()
        if route == 'trakt_list':
            return library.widget_list(params['ref'])
        if route == 'trakt_seasons':
            return library.widget_seasons(params['ref'], params['item'])
        if route == 'trakt_episodes':
            return library.widget_episodes(params['ref'], params['item'], params['season'])
        if route == 'trakt_episode_details':
            return library.widget_episode_details(params['ref'], params['item'], params['season'], params['episode'])
        return library.widget_details(params['ref'], params['item'])

    def _stage(self, route, params, rows):
        staged = []
        for row in rows:
            target, folder = '', False
            if route == 'trakt_sources':
                label = _text(row['name'])
                target, folder = routes.url('trakt_list', ref=row['ref']), True
            elif route == 'trakt_seasons':
                label = 'Season ' + str(row['season'])
                target = routes.url('trakt_episodes', ref=params['ref'], item=params['item'], season=row['season'])
                folder = True
            else:
                label = _text(row['title'])
                if route == 'trakt_list':
                    destination = 'trakt_seasons' if row['kind'] == 'show' else 'trakt_details'
                    target = routes.url(destination, ref=params['ref'], item=row['item_ref'])
                    folder = row['kind'] == 'show'
                elif route == 'trakt_episodes':
                    target = routes.url('trakt_episode_details', ref=params['ref'], item=params['item'],
                                        season=params['season'], episode=row['episode'])
            item = self._item(label=label)
            if self._art:
                item.setArt(dict(self._art))
            if route not in {'trakt_sources', 'trakt_seasons'}:
                tag = item.getVideoInfoTag()
                tag.setTitle(label)
                tag.setMediaType('tvshow' if row['kind'] == 'show' else row['kind'])
                year = row.get('year')
                if type(year) is int and 1 <= year <= 9999:
                    tag.setYear(year)
                watched = row.get('watched')
                if type(watched) is bool:
                    tag.setPlaycount(1 if watched else 0)
                status = 'watched' if watched is True else 'unwatched' if watched is False else 'unknown'
                release = row.get('release_at')
                date_text = release.isoformat() if release is not None else 'unknown'
                tag.setPlot('Watch status: ' + status + '. Release/air date: ' + _text(date_text)
                            + '. Date metadata does not establish a playable source.')
                if row['kind'] == 'episode':
                    tag.setSeason(row['season'])
                    tag.setEpisode(row['episode'])
            if 'ref' in params:
                full_list = routes.url('trakt_list', ref=params['ref'])
                item.addContextMenuItems([('Open full list', 'Container.Update(' + full_list + ')')])
            # No IsPlayable flag, player call, arbitrary service URL or mutation action.
            staged.append((target, item, folder))
        return staged

    def render(self, library, handle, query, widget=False):
        result, staged, guard = ListResult('failed'), [], None
        details, detail_rows = False, []
        cleanup_failed = False
        try:
            if type(handle) is not int or handle < 0 or type(widget) is not bool:
                raise ValueError('invalid_ui_configuration')
            route, params = routes.parse(query)
            details = route in {'trakt_details', 'trakt_episode_details'}
            if details and widget:
                raise ValueError('invalid_widget_action')
            if self.cancelled():
                result = ListResult('cancelled')
            else:
                if not widget:
                    self._progress = self._progress_factory()
                    self._progress.create('HomeFX — Trakt lists', 'Loading read-only account data…')
                    self._progress.update(0)
                if self.cancelled():
                    result = ListResult('cancelled')
                else:
                    payload = self._read(library, route, params)
                    guard = payload['guard']
                    guard()
                    rows, unsupported = payload['items'], payload['unsupported_count']
                    if details:
                        if len(rows) != 1:
                            raise ValueError('invalid_details')
                        detail_rows = rows
                    else:
                        staged = self._stage(route, params, rows)
                    result = ListResult('partial' if unsupported else 'ready' if rows else 'empty',
                                        unsupported_count=unsupported)
        except (AuthError, ApiError) as error:
            result = ListResult(_error_state(error))
        except Exception:
            result = ListResult('failed')
        finally:
            # Closing releases the progress object and its cancellation flag.
            # Preserve the user's decision before cleanup, including read errors.
            try:
                if self.cancelled():
                    result = ListResult('cancelled')
            except Exception:
                cleanup_failed = True
                result = ListResult('failed')
            try:
                self._close()
            except Exception:
                cleanup_failed = True
                result = ListResult('failed')
        try:
            if not cleanup_failed and self.cancelled():
                result = ListResult('cancelled')
            successful = result.state in {'ready', 'empty', 'partial'}
            if successful:
                guard()
            if details:
                if successful:
                    row = detail_rows[0]
                    title = _text(row['title'])
                    watched = row.get('watched')
                    status = 'watched' if watched is True else 'unwatched' if watched is False else 'unknown'
                    release = row.get('release_at')
                    date_text = release.isoformat() if release is not None else 'unknown'
                    body = 'Watch status: ' + status + '\nRelease/air date: ' + _text(date_text)
                    body += '\nMetadata only. No playable source or playback action.'
                    guard()
                    self._dialog.textviewer(title, body)
                    guard()
                elif not widget and result.state != 'cancelled':
                    if not self._detail_failure(result):
                        result = ListResult('failed')
                return result
            self._plugin.setPluginCategory(handle, result.message)
            self._plugin.setContent(handle, 'videos')
            if successful:
                guard()
                if staged and self._plugin.addDirectoryItems(handle, staged, totalItems=len(staged)) is not True:
                    raise ValueError('directory_submission_failed')
                guard()
                if self.cancelled():
                    result, successful = ListResult('cancelled'), False
                    self._plugin.setPluginCategory(handle, result.message)
                if successful:
                    guard()
            self._plugin.endOfDirectory(handle, succeeded=successful, cacheToDisc=False)
        except (AuthError, ApiError) as error:
            result = ListResult(_error_state(error))
            if details and not widget:
                if not self._detail_failure(result):
                    result = ListResult('failed')
            elif not details:
                if not self._fail_directory(handle, result):
                    result = ListResult('failed')
        except Exception:
            result = ListResult('failed')
            if details and not widget:
                if not self._detail_failure(result):
                    result = ListResult('failed')
            elif not details:
                if not self._fail_directory(handle, result):
                    result = ListResult('failed')
        return result

    def _detail_failure(self, result):
        try:
            self._dialog.textviewer('HomeFX', result.message)
            return True
        except Exception:
            return False

    def _fail_directory(self, handle, result):
        reported = True
        try:
            self._plugin.setPluginCategory(handle, result.message)
        except Exception:
            reported = False
        # A failed status display must not prevent best-effort failed finalization.
        try:
            self._plugin.endOfDirectory(handle, succeeded=False, cacheToDisc=False)
        except Exception:
            return False
        return reported
