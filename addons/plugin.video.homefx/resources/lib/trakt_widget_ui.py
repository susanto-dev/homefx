"""Inactive Kodi-shaped read directory renderer with no imports or activation of Kodi."""
from datetime import date, timedelta
import math
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


def _description(row):
    parts = []
    overview = row.get('overview')
    if overview:
        parts.append(_text(overview))
    rating, votes = row.get('trakt_rating'), row.get('trakt_votes')
    if (type(rating) in (int, float) and 0 <= rating <= 10 and math.isfinite(rating)
            and type(votes) is int and 0 < votes <= 2147483647):
        parts.append('Trakt rating: ' + format(rating, '.1f') + '/10 (' + str(votes) + ' votes).')
    return '\n\n'.join(parts)


def _progress_text(row):
    if row.get('kind') not in {'movie', 'episode'} or row.get('watched') is True:
        return ''
    value = row.get('progress', 0)
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value < 100:
        raise ValueError('invalid_progress')
    if value == 0:
        return ''
    # Percentage is not a resume timestamp. Avoid rounding an unfinished value to 100.
    text = str(value)
    if text.endswith('.0'):
        text = text[:-2]
    return 'Unfinished progress: ' + text + '%.'


def _season_plot(row):
    fields = [('total', 'Total episodes'), ('watched', 'Watched'),
              ('aired_unwatched', 'Aired unwatched'), ('upcoming', 'Upcoming dates'),
              ('unknown_watched', 'Unknown watched status'), ('unknown_date', 'Unknown dates')]
    values = []
    for key, label in fields:
        count = row[key]
        if type(count) is not int or not 0 <= count <= 5000:
            raise ValueError('invalid_season_count')
        values.append(label + ': ' + str(count))
    return '. '.join(values) + '. Counts overlap; dates do not establish playable availability.'


def _media_identity(tag, row):
    """Expose public metadata IDs through Kodi's native typed interface only."""
    fields = [('trakt_id', 'trakt')]
    if row.get('kind') in {'movie', 'show'}:
        fields.append(('tmdb_id', 'tmdb'))
    fields.extend([('show_trakt_id', 'tvshow.trakt'), ('show_tmdb_id', 'tvshow.tmdb')])
    ids = {name: str(row[key]) for key, name in fields
           if type(row.get(key)) is int and 1 <= row[key] < 2**63}
    if ids:
        tag.setUniqueIDs(ids, 'trakt' if 'trakt' in ids else 'tvshow.trakt')
    if 'show_title' in row:
        tag.setTvShowTitle(_text(row['show_title']))


def _calendar_title(row):
    return (_text(row['show_title']) + ' — S' + str(row['season']) + 'E' +
            str(row['episode']) + ' — ' + _text(row['title']))


def _calendar_window(payload):
    start, days = payload['start_date'], payload['days']
    if type(start) is not str or len(start) != 10 or type(days) is not int or days != 7:
        raise ValueError('invalid_calendar_window')
    begin = date.fromisoformat(start)
    return begin.isoformat() + ' through ' + (begin + timedelta(days=days - 1)).isoformat()


def _episode_actions(params, season, addon_id):
    return [(label, 'Container.Update(' + routes.url('trakt_episodes', addon_id=addon_id, ref=params['ref'],
             item=params['item'], season=season, filter=selection) + ')')
            for label, selection in [('All episodes in this season', 'all'),
                                     ('Aired unwatched episodes in this season', 'aired_unwatched')]]


class WidgetDirectoryUI:
    """Stage a complete read before submission; private Kodi disk caching is disabled.

    Inject xbmcplugin, xbmcgui.ListItem, DialogProgress and Monitor objects. Pass
    cancelled to the service factory before explicit reads. Constructor has no I/O.
    Kodi submission/finalization is not a transaction: final guard failures end the
    directory unsuccessfully, but actual skin retention/clearing needs device tests.
    """
    def __init__(self, plugin, list_item_factory, progress_factory, monitor, dialog=None, art_root=None, addon_id='plugin.video.homefx'):
        self._plugin, self._item = plugin, list_item_factory
        self._progress_factory, self._monitor = progress_factory, monitor
        self._progress = None
        routes.url('trakt_sources', addon_id=addon_id)
        self._addon_id = addon_id
        self._dialog = dialog
        # The caller supplies the installed add-on's local original-art directory.
        if art_root is not None and (type(art_root) is not str or not art_root.startswith('/')
                or not art_root.endswith('/') or '://' in art_root or '..' in art_root.split('/')
                or any(unicodedata.category(c).startswith('C') for c in art_root)):
            raise ValueError('invalid_art_root')
        self._art = {} if art_root is None else {
            'thumb': art_root + 'poster.png', 'poster': art_root + 'poster.png',
            'icon': art_root + 'icon.png', 'fanart': art_root + 'fanart.png'}

    def _url(self, route, **params):
        return routes.url(route, addon_id=self._addon_id, **params)

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
        if route == 'trakt_widget_menu':
            return {'items': [
                {'name': 'Selected lists', 'route': 'trakt_sources'},
                {'name': 'Movie progress (reads Trakt history)', 'route': 'trakt_movie_sources'},
                {'name': 'Shows and episodes (progress views read Trakt history)', 'route': 'trakt_show_sources'},
                {'name': 'Continue watching (account-wide; reads history)', 'route': 'trakt_continue_sources'},
                {'name': 'Upcoming episodes (personal calendar)', 'route': 'trakt_calendar_sources'},
            ], 'unsupported_count': 0, 'guard': lambda: None}
        if route == 'trakt_calendar_sources':
            return library.widget_calendar_sources()
        if route == 'trakt_calendar':
            return library.widget_calendar(params['ref'])
        if route == 'trakt_calendar_details':
            return library.widget_calendar_details(params['ref'], params['item'])
        if route == 'trakt_continue_sources':
            return library.widget_continue_sources()
        if route == 'trakt_continue':
            return library.widget_continue(params['ref'])
        if route == 'trakt_continue_details':
            return library.widget_continue_details(params['ref'], params['item'])
        if route in {'trakt_sources', 'trakt_movie_sources', 'trakt_show_sources'}:
            return library.widget_sources()
        if route == 'trakt_shows':
            return library.widget_shows(params['ref'])
        if route == 'trakt_show_views':
            result = library.widget_details(params['ref'], params['item'])
            if len(result['items']) != 1 or result['items'][0]['kind'] != 'show':
                raise ApiError('unavailable_selection')
            return dict(result, items=[
                {'name': 'Seasons and episodes (reads Trakt history)', 'route': 'trakt_seasons'},
                {'name': 'Aired unwatched episodes — all regular seasons', 'route': 'trakt_show_unwatched'},
            ] + [{'name': label + ' — this show, regular seasons',
                  'route': 'trakt_show_progress', 'view': view}
                 for view, label in routes.SHOW_PROGRESS_VIEWS.items()])
        if route == 'trakt_movie_views':
            result = library.widget_sources()
            if not any(row['ref'] == params['ref'] for row in result['items']):
                raise ApiError('unavailable_selection')
            return dict(result, items=[{'filter': value, 'name': label}
                        for value, label in routes.MOVIE_FILTERS.items()])
        if route == 'trakt_list':
            return (library.widget_list(params['ref'], movie_filter=params['filter'])
                    if 'filter' in params else library.widget_list(params['ref']))
        if route == 'trakt_seasons':
            return library.widget_seasons(params['ref'], params['item'])
        if route == 'trakt_show_unwatched':
            return library.widget_show_unwatched(params['ref'], params['item'])
        if route == 'trakt_show_progress':
            return library.widget_show_progress(params['ref'], params['item'], params['view'])
        if route == 'trakt_episodes':
            return library.widget_episodes(params['ref'], params['item'], params['season'],
                                           episode_filter=params.get('filter', 'all'))
        if route == 'trakt_episode_details':
            return library.widget_episode_details(params['ref'], params['item'], params['season'], params['episode'])
        return (library.widget_details(params['ref'], params['item'], movie_filter=params['filter'])
                if 'filter' in params else library.widget_details(params['ref'], params['item']))

    def _stage(self, route, params, rows):
        staged = []
        for row in rows:
            target, folder = '', False
            if route == 'trakt_widget_menu':
                label = _text(row['name'])
                target, folder = self._url(row['route']), True
            elif route == 'trakt_show_views':
                label = _text(row['name'])
                target, folder = self._url(row['route'], ref=params['ref'], item=params['item'],
                    **({'view': row['view']} if 'view' in row else {})), True
            elif route in {'trakt_continue_sources', 'trakt_calendar_sources'}:
                label = _text(row['name'])
                destination = 'trakt_calendar' if route == 'trakt_calendar_sources' else 'trakt_continue'
                target, folder = self._url(destination, ref=row['ref']), True
            elif route in {'trakt_sources', 'trakt_movie_sources', 'trakt_show_sources'}:
                label = _text(row['name'])
                destination = {'trakt_movie_sources': 'trakt_movie_views',
                               'trakt_show_sources': 'trakt_shows'}.get(route, 'trakt_list')
                target, folder = self._url(destination, ref=row['ref']), True
            elif route == 'trakt_movie_views':
                label = _text(row['name'])
                target, folder = self._url('trakt_list', ref=params['ref'], filter=row['filter']), True
            elif route == 'trakt_seasons':
                label = 'Season ' + str(row['season'])
                target = self._url('trakt_episodes', ref=params['ref'], item=params['item'], season=row['season'])
                folder = True
            else:
                label = _text(row['title'])
                if route == 'trakt_calendar':
                    label = _calendar_title(row)
                    target = self._url('trakt_calendar_details', ref=params['ref'], item=row['item_ref'])
                elif route == 'trakt_continue':
                    target = self._url('trakt_continue_details', ref=params['ref'], item=row['item_ref'])
                    if row['kind'] == 'episode':
                        label = 'S' + str(row['season']) + 'E' + str(row['episode']) + ' — ' + label
                elif route == 'trakt_shows':
                    target, folder = self._url('trakt_show_views', ref=params['ref'], item=row['item_ref']), True
                elif route == 'trakt_list':
                    destination = 'trakt_seasons' if row['kind'] == 'show' else 'trakt_details'
                    target = self._url(destination, ref=params['ref'], item=row['item_ref'],
                                       **({'filter': params['filter']} if 'filter' in params else {}))
                    folder = row['kind'] == 'show'
                elif route in {'trakt_episodes', 'trakt_show_unwatched', 'trakt_show_progress'}:
                    target = self._url('trakt_episode_details', ref=params['ref'], item=params['item'],
                                        season=row['season'], episode=row['episode'])
                    if route in {'trakt_show_unwatched', 'trakt_show_progress'}:
                        label = 'S' + str(row['season']) + 'E' + str(row['episode']) + ' — ' + label
            item = self._item(label=label)
            if self._art:
                item.setArt(dict(self._art))
            if route == 'trakt_seasons':
                tag = item.getVideoInfoTag()
                tag.setTitle(label)
                tag.setMediaType('season')
                _media_identity(tag, row)
                tag.setSeason(row['season'])
                tag.setPlot(_season_plot(row))
                item.addContextMenuItems(_episode_actions(params, row['season'], self._addon_id))
            if route not in {'trakt_widget_menu', 'trakt_sources', 'trakt_movie_sources', 'trakt_movie_views',
                             'trakt_show_sources', 'trakt_show_views', 'trakt_seasons', 'trakt_continue_sources', 'trakt_calendar_sources'}:
                tag = item.getVideoInfoTag()
                tag.setTitle(label)
                tag.setMediaType('tvshow' if row['kind'] == 'show' else row['kind'])
                _media_identity(tag, row)
                year = row.get('year')
                if type(year) is int and 1 <= year <= 9999:
                    tag.setYear(year)
                watched = row.get('watched')
                if type(watched) is bool:
                    tag.setPlaycount(1 if watched else 0)
                status = 'watched' if watched is True else 'unwatched' if watched is False else 'unknown'
                release = row.get('release_at')
                date_text = release.isoformat() if release is not None else 'unknown'
                description = _description(row)
                if 'trakt_rating' in row and 'trakt_votes' in row:
                    tag.setRating(row['trakt_rating'], row['trakt_votes'], 'trakt', True)
                tag.setPlot((description + '\n\n' if description else '') + 'Watch status: ' + status + '. Release/air date: ' + _text(date_text)
                            + '. ' + _progress_text(row)
                            + ' Date metadata does not establish a playable source.')
                if row['kind'] == 'episode':
                    tag.setSeason(row['season'])
                    tag.setEpisode(row['episode'])
                    if route not in {'trakt_continue', 'trakt_calendar'}:
                        item.addContextMenuItems(_episode_actions(params, row['season'], self._addon_id))
            if route == 'trakt_list' and row.get('kind') == 'show':
                show_view = self._url('trakt_show_unwatched', ref=params['ref'], item=row['item_ref'])
                item.addContextMenuItems([('Aired unwatched episodes — all regular seasons',
                                          'Container.Update(' + show_view + ')')])
            elif route in {'trakt_seasons', 'trakt_episodes', 'trakt_show_unwatched', 'trakt_show_progress'}:
                show_view = self._url('trakt_show_unwatched', ref=params['ref'], item=params['item'])
                item.addContextMenuItems([('Aired unwatched episodes — all regular seasons',
                                          'Container.Update(' + show_view + ')')])
            if route == 'trakt_calendar':
                full_feed = self._url('trakt_calendar', ref=params['ref'])
                item.addContextMenuItems([('Open personal calendar', 'Container.Update(' + full_feed + ')')])
            elif route == 'trakt_continue':
                full_feed = self._url('trakt_continue', ref=params['ref'])
                item.addContextMenuItems([('Open Continue watching', 'Container.Update(' + full_feed + ')')])
            elif 'ref' in params:
                full_list = self._url('trakt_list', ref=params['ref'])
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
            details = route in {'trakt_details', 'trakt_episode_details', 'trakt_continue_details', 'trakt_calendar_details'}
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
                    if route == 'trakt_calendar_details':
                        title = _calendar_title(row)
                    elif route == 'trakt_continue_details' and row['kind'] == 'episode':
                        title = 'S' + str(row['season']) + 'E' + str(row['episode']) + ' — ' + title
                    watched = row.get('watched')
                    status = 'watched' if watched is True else 'unwatched' if watched is False else 'unknown'
                    release = row.get('release_at')
                    date_text = release.isoformat() if release is not None else 'unknown'
                    description = _description(row)
                    body = (description + '\n\n' if description else '') + 'Watch status: ' + status + '\nRelease/air date: ' + _text(date_text)
                    progress = _progress_text(row)
                    if progress:
                        body += '\n' + progress
                    body += '\nMetadata only. No playable source or playback action.'
                    guard()
                    self._dialog.textviewer(title, body)
                    guard()
                elif not widget and result.state != 'cancelled':
                    if not self._detail_failure(result):
                        result = ListResult('failed')
                return result
            category = result.message
            if successful and route == 'trakt_list' and 'filter' in params:
                category = routes.MOVIE_FILTERS[params['filter']] + ' — this selected list only. ' + category
            if successful and route == 'trakt_show_unwatched':
                category = 'Aired unwatched — this show, regular seasons only. ' + category
            if successful and route == 'trakt_show_progress':
                category = routes.SHOW_PROGRESS_VIEWS[params['view']] + ' — this show, regular seasons only. ' + category
                if params['view'] == 'upcoming':
                    category += ' Dates are not playable availability or a complete personal calendar.'
            if successful and route in {'trakt_continue_sources', 'trakt_continue'}:
                category = ('Continue watching — this account, not limited to selected lists. '
                            'Reads paused titles, details and watched history; unknown watched status remains unknown. ' + category)
            if successful and route in {'trakt_calendar_sources', 'trakt_calendar'}:
                category = ('Upcoming episodes — personal calendar, next 7 UTC dates. '
                            'Watched/collected/watchlisted scope; not every selected-list show. '
                            'Watched status unknown; dates do not establish playable availability. ' + category)
                if route == 'trakt_calendar':
                    category += ' UTC dates: ' + _calendar_window(payload) + '.'
            self._plugin.setPluginCategory(handle, category)
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
