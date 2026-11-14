"""Inactive TMDB artwork contracts. No credentials, sockets or stores at import."""
from dataclasses import dataclass, field
import re
import time

from .request_limits import _retry_after

from .trakt_transport import Transport as HTTPS, TransportError, USER_AGENT


class ArtworkError(Exception):
    """Fixed categories only; never response text, identifiers or credentials."""
    def __init__(self, category='unavailable', wait=60):
        self.category = category if category in {'unavailable', 'limited', 'unauthorized', 'cancelled'} else 'unavailable'
        self.wait = wait if type(wait) is int and 1 <= wait <= 10**12 else 60
        super().__init__(self.category)


def key(kind, ident, language='en-US'):
    if (kind not in ('movie', 'show') or type(ident) is not int or not 1 <= ident < 2**63
            or type(language) is not str or not re.fullmatch(r'[a-z]{2}-[A-Z]{2}', language)):
        raise ArtworkError()
    return kind, ident, language


def image_path(value):
    if value is not None and (type(value) is not str
            or not re.fullmatch(r'/[A-Za-z0-9]{1,96}\.(?:jpg|png)', value)):
        raise ArtworkError()
    return value


@dataclass(frozen=True)
class Artwork:
    poster: str | None = field(default=None, repr=False)
    backdrop: str | None = field(default=None, repr=False)
    stale: bool = False

    def __post_init__(self):
        image_path(self.poster)
        image_path(self.backdrop)
        if type(self.stale) is not bool:
            raise ArtworkError()


class Client:
    """Explicit application-token reads; no account/session, search or image download.

    Reuse the bounded HTTPS engine without broadening Trakt's route allowlist.
    This class is not constructed by either Kodi entry point. A future activation
    must provide private credential delivery and approved attribution first.
    """
    def __init__(self, token, *, cancelled=lambda: False, connection_factory=None):
        if type(token) is not str or not re.fullmatch(r'[A-Za-z0-9._-]{16,4096}', token):
            raise ArtworkError('unauthorized')
        self._token = token
        options = dict(timeout=3, total_timeout=5, max_bytes=128*1024, cancelled=cancelled)
        if connection_factory is not None:
            options['connection_factory'] = connection_factory
        self._https = HTTPS(**options)

    def __repr__(self):
        return 'TMDBClient(<private application token>)'

    def fetch(self, lookup):
        if type(lookup) not in (list, tuple) or len(lookup) != 3:
            raise ArtworkError()
        kind, ident, language = key(*lookup)
        media = 'tv' if kind == 'show' else 'movie'
        path = '/3/' + media + '/' + str(ident) + '?language=' + language
        try:
            response = self._https._request('api.themoviedb.org', 'GET', path,
                {'Authorization': 'Bearer ' + self._token, 'Accept': 'application/json',
                 'User-Agent': USER_AGENT}, None)
        except TransportError as error:
            raise ArtworkError('cancelled' if str(error) == 'cancelled' else 'unavailable') from None
        if response.status in (401, 403):
            raise ArtworkError('unauthorized', 3600)
        if response.status == 429:
            raise ArtworkError('limited', _retry_after(response.headers, time.time()))
        if response.status == 404:
            return Artwork()  # Short negative cache, not a missing playable-source claim.
        body = response.body
        if (response.status != 200 or type(body) is not dict
                or type(body.get('id')) is not int or body['id'] != ident
                or 'poster_path' not in body or 'backdrop_path' not in body):
            raise ArtworkError()
        return Artwork(image_path(body['poster_path']), image_path(body['backdrop_path']))
