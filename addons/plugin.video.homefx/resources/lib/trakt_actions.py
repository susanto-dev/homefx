"""Explicit single-item action contracts; no UI, retries or offline write queue.

A lost response may hide a successful write. Reconcile service state before a
manual retry: Trakt does not deduplicate repeated history plays. This module never
changes local watched state and does not support deleting watch history.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import re

from .trakt_client import ApiError, ListRef, retry_delay
from .trakt_auth import _text


@dataclass(frozen=True)
class ActionResult:
    outcome: str
    reason: str
    retry_after: object = None


@dataclass(frozen=True, repr=False)
class ActionRequest:
    path: str = field(repr=False)
    body: dict = field(repr=False)
    media: str
    trakt_id: int
    success_status: int

    def __repr__(self):
        return 'ActionRequest(<private action>)'


def _ident(value):
    return type(value) is int and 0 < value < 10 ** 20


def _date(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ApiError('invalid_action')
    try:
        return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    except (ValueError, OverflowError):
        raise ApiError('invalid_action') from None


def validate_request(path, body):
    """Strict write boundary shared with transport; returns the requested item."""
    if not isinstance(path, str) or not isinstance(body, dict):
        raise ApiError('invalid_action')
    history = path == '/sync/history'
    if not history and not re.fullmatch(r'/users/me/lists/[1-9][0-9]{0,19}/items', path):
        raise ApiError('invalid_action')
    kinds = {'movies', 'episodes'} if history else {'movies'}
    if len(body) != 1 or next(iter(body), None) not in kinds:
        raise ApiError('invalid_action')
    media = next(iter(body))
    items = body[media]
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], dict):
        raise ApiError('invalid_action')
    item = items[0]
    if set(item) != ({'ids', 'watched_at'} if history else {'ids'}):
        raise ApiError('invalid_action')
    ids = item['ids']
    if not isinstance(ids, dict) or set(ids) != {'trakt'} or not _ident(ids['trakt']):
        raise ApiError('invalid_action')
    if history:
        stamp = item['watched_at']
        if not isinstance(stamp, str) or not re.fullmatch(
                r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z', stamp):
            raise ApiError('invalid_action')
        try:
            datetime.fromisoformat(stamp[:-1] + '+00:00')
        except ValueError:
            raise ApiError('invalid_action') from None
    return media, ids['trakt']


def prepare(operation, *args):
    """Validate before any token refresh or service request is attempted."""
    if operation == 'mark_watched' and len(args) == 3:
        kind, ident, watched_at = args
        if not isinstance(kind, str) or kind not in {'movie', 'episode'} or not _ident(ident):
            raise ApiError('invalid_action')
        path = '/sync/history'
        body = {kind + 's': [{'ids': {'trakt': ident}, 'watched_at': _date(watched_at)}]}
        status = 200
    elif operation == 'add_movie_to_list' and len(args) == 2:
        ref, ident = args
        if (not isinstance(ref, ListRef) or ref.owner != 'me' or ref.writable is not True
                or not _ident(ref.trakt_id) or not _ident(ident)):
            raise ApiError('invalid_action')
        path = '/users/me/lists/' + str(ref.trakt_id) + '/items'
        body, status = {'movies': [{'ids': {'trakt': ident}}]}, 201
    else:
        raise ApiError('unsupported_action')
    media, ident = validate_request(path, body)
    return ActionRequest(path, body, media, ident, status)


def _counts(value, fields, media):
    if (not isinstance(value, dict) or set(value) != fields or
            any(type(v) is not int or v not in (0, 1) for v in value.values()) or
            any(value[k] != 0 for k in fields if k != media)):
        raise ValueError()
    return value[media]


def _missing(value, request):
    fields = {'movies', 'shows', 'seasons', 'episodes'}
    if not isinstance(value, dict) or not set(value) <= fields:
        raise ValueError()
    missing = 0
    for media, entries in value.items():
        if entries is None:
            continue
        if not isinstance(entries, list) or len(entries) > 1:
            raise ValueError()
        for item in entries:
            if (media != request.media or not isinstance(item, dict) or
                    not set(item) <= {'ids', 'watched_at'} or
                    not isinstance(item.get('ids'), dict) or
                    set(item['ids']) != {'trakt'} or not _ident(item['ids']['trakt']) or
                    item['ids']['trakt'] != request.trakt_id):
                raise ValueError()
            if 'watched_at' in item and item['watched_at'] != request.body[media][0].get('watched_at'):
                raise ValueError()
            missing += 1
    return missing


def _confirmed(body, request):
    history = request.path == '/sync/history'
    fields = {'movies', 'episodes'} if history else {'movies', 'shows', 'seasons', 'episodes'}
    secondary = 'updated' if history else 'existing'
    expected = {'added', secondary, 'not_found'} | (set() if history else {'list'})
    if not isinstance(body, dict) or set(body) != expected:
        raise ValueError()
    added = _counts(body['added'], fields, request.media)
    other = _counts(body[secondary], fields, request.media)
    missing = _missing(body['not_found'], request)
    if added + other + missing != 1:
        raise ValueError()
    if not history:
        summary = body['list']
        if (not isinstance(summary, dict) or set(summary) != {'updated_at', 'item_count'} or
                type(summary['item_count']) is not int or summary['item_count'] < 0):
            raise ValueError()
        stamp = summary['updated_at']
        if not isinstance(stamp, str) or len(stamp) > 40:
            raise ValueError()
        parsed = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
    if missing:
        return ActionResult('not_found', 'item_not_found')
    if not history and other:
        return ActionResult('already_present', 'already_in_list')
    return ActionResult('confirmed', 'updated' if other else 'added')


class MutationClient:
    """Send exactly one validated action; unknown outcomes must not be replayed."""
    def __init__(self, request, client_id, access_token):
        if not _text(client_id, 256) or not _text(access_token, 4096):
            raise ApiError('invalid_credentials')
        self._request, self._client_id, self._token = request, client_id, access_token

    def __repr__(self):
        return 'MutationClient(<private account>)'

    def execute(self, request):
        if not isinstance(request, ActionRequest):
            raise ApiError('invalid_action')
        media, ident = validate_request(request.path, request.body)
        expected_status = 200 if request.path == '/sync/history' else 201
        if (media, ident, expected_status) != (request.media, request.trakt_id, request.success_status):
            raise ApiError('invalid_action')
        headers = {'Authorization': 'Bearer ' + self._token, 'trakt-api-key': self._client_id,
                   'trakt-api-version': '2', 'Content-Type': 'application/json'}
        try:
            response = self._request('POST', request.path, headers, request.body)
        except Exception:
            return ActionResult('uncertain', 'request_outcome_unknown')
        status = getattr(response, 'status', None)
        if type(status) is not int or not isinstance(getattr(response, 'headers', None), dict):
            return ActionResult('uncertain', 'invalid_response')
        if status in (400, 401, 403, 404, 420, 422, 429):
            reasons = {400: 'rejected', 401: 'reauthenticate', 403: 'forbidden',
                       404: 'unavailable', 420: 'account_limit', 422: 'rejected', 429: 'rate_limit'}
            return ActionResult('failed', reasons[status], retry_delay(response.headers) if status == 429 else None)
        if status != request.success_status:
            return ActionResult('uncertain', 'request_outcome_unknown')
        try:
            return _confirmed(response.body, request)
        except (AttributeError, TypeError, ValueError, OverflowError):
            return ActionResult('uncertain', 'invalid_response')
