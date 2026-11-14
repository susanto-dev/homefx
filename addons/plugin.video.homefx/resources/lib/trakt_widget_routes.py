"""Private opaque read routes; the public preview does not dispatch these routes."""
import re
from urllib.parse import parse_qsl, urlencode

BASE = 'plugin://plugin.video.homefx/'
_FIELDS = {
    'trakt_sources': set(),
    'trakt_movie_sources': set(),
    'trakt_movie_views': {'ref'},
    'trakt_list': {'ref'},
    'trakt_seasons': {'ref', 'item'},
    'trakt_show_unwatched': {'ref', 'item'},
    'trakt_episodes': {'ref', 'item', 'season'},
    'trakt_details': {'ref', 'item'},
    'trakt_episode_details': {'ref', 'item', 'season', 'episode'},
}


MOVIE_FILTERS = {
    'all': 'All movies with progress',
    'unwatched': 'Unwatched movies',
    'released_unwatched': 'Released unwatched movies',
    'unfinished': 'Unfinished released movies',
    'upcoming': 'Upcoming movies',
}

def _validate(route, params):
    if type(route) is not str or route not in _FIELDS:
        raise ValueError('invalid_widget_route')
    expected = _FIELDS[route]
    if route in {'trakt_episodes', 'trakt_list', 'trakt_details'} and 'filter' in params:
        expected = expected | {'filter'}
    if set(params) != expected:
        raise ValueError('invalid_widget_route')
    filters = {'all', 'aired_unwatched'} if route == 'trakt_episodes' else MOVIE_FILTERS
    if 'filter' in params and (type(params['filter']) is not str or params['filter'] not in filters):
        raise ValueError('invalid_widget_route')
    for key in ('ref', 'item'):
        if key in params and (type(params[key]) is not str or
                              not re.fullmatch(r'[0-9a-f]{64}', params[key])):
            raise ValueError('invalid_widget_route')
    for key, minimum in [('season', 0), ('episode', 1)]:
        if key in params and (type(params[key]) is not int or not minimum <= params[key] <= 10000):
            raise ValueError('invalid_widget_route')


def url(route, *, addon_id='plugin.video.homefx', **params):
    if addon_id not in {'plugin.video.homefx', 'plugin.video.homefx.development'}:
        raise ValueError('invalid_widget_addon')
    _validate(route, params)
    return 'plugin://' + addon_id + '/' + '?' + urlencode(dict(route=route, **params))


def parse(query):
    if type(query) is not str or not 1 <= len(query) <= 512:
        raise ValueError('invalid_widget_route')
    try:
        pairs = parse_qsl(query[1:] if query.startswith('?') else query,
                          keep_blank_values=True, strict_parsing=True, max_num_fields=5)
        data = dict(pairs)
        if len(data) != len(pairs) or 'route' not in data:
            raise ValueError()
        route = data.pop('route')
        for key in ('season', 'episode'):
            if key in data:
                if not re.fullmatch(r'0|[1-9][0-9]{0,4}', data[key]):
                    raise ValueError()
                data[key] = int(data[key])
        _validate(route, data)
        return route, data
    except (ValueError, TypeError):
        raise ValueError('invalid_widget_route') from None
