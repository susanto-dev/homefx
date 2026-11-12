"""Fabricated single-write contracts never call Trakt or alter watched state."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.trakt_actions import MutationClient, prepare
from resources.lib.trakt_client import ApiError, ListRef, Response

NOW = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
OWN = ListRef(7, 'me', 'Synthetic list', True)


def history(added=1, updated=0, missing=None, media='movies'):
    return {'added': {'movies': 0, 'episodes': 0, **{media: added}},
            'updated': {'movies': 0, 'episodes': 0, **{media: updated}},
            'not_found': {} if missing is None else {media: [{'ids': {'trakt': missing}}]}}


def listed(added=1, existing=0, missing=None):
    empty = {'movies': 0, 'shows': 0, 'seasons': 0, 'episodes': 0}
    return {'added': dict(empty, movies=added), 'existing': dict(empty, movies=existing),
            'not_found': {} if missing is None else {'movies': [{'ids': {'trakt': missing}}]},
            'list': {'updated_at': '2026-11-12T12:00:00Z', 'item_count': 4}}


class ActionTests(unittest.TestCase):
    def client(self, response):
        self.calls = []
        def request(*args):
            self.calls.append(args)
            return response
        return MutationClient(request, 'synthetic-client', 'synthetic-access')

    def test_history_contract_is_one_explicit_id_and_utc_timestamp(self):
        for kind in ('movie', 'episode'):
            plan = prepare('mark_watched', kind, 11, NOW.astimezone(timezone(timedelta(hours=8))))
            client = self.client(Response(200, body=history(media=kind + 's')))
            self.assertEqual(client.execute(plan).outcome, 'confirmed')
            method, path, headers, body = self.calls[0]
            self.assertEqual((method, path), ('POST', '/sync/history'))
            self.assertEqual(body, {kind + 's': [{'ids': {'trakt': 11}, 'watched_at': '2026-11-12T12:00:00Z'}]})
            self.assertNotIn('synthetic-access', repr(client))
            self.assertNotIn('11', repr(plan))
            self.assertEqual(len(self.calls), 1)

    def test_own_list_add_supports_future_metadata_without_release_gate(self):
        plan = prepare('add_movie_to_list', OWN, 11)
        client = self.client(Response(201, body=listed()))
        self.assertEqual(client.execute(plan).outcome, 'confirmed')
        self.assertEqual(self.calls[0][1], '/users/me/lists/7/items')
        self.assertEqual(self.calls[0][3], {'movies': [{'ids': {'trakt': 11}}]})

    def test_existing_and_not_found_are_not_false_new_watches(self):
        cases = [('mark_watched', ('movie', 11, NOW), Response(200, body=history(0, 1)), 'confirmed'),
                 ('mark_watched', ('movie', 11, NOW), Response(200, body=history(0, 0, 11)), 'not_found'),
                 ('add_movie_to_list', (OWN, 11), Response(201, body=listed(0, 1)), 'already_present'),
                 ('add_movie_to_list', (OWN, 11), Response(201, body=listed(0, 0, 11)), 'not_found')]
        for operation, args, response, expected in cases:
            self.assertEqual(self.client(response).execute(prepare(operation, *args)).outcome, expected)

    def test_invalid_identity_kind_time_and_liked_list_rejected(self):
        cases = [('mark_watched', 'show', 11, NOW), ('mark_watched', 'movie', True, NOW),
                 ('mark_watched', 'movie', 10 ** 30, NOW), ('mark_watched', 'movie', 11, datetime(2026, 1, 1)),
                 ('add_movie_to_list', ListRef(7, 'other', 'Liked', False), 11),
                 ('add_movie_to_list', ListRef(7, 'me', 'Synthetic', False), 11),
                 ('mark_unwatched', 'movie', 11), ('delete_history', 11)]
        for case in cases:
            with self.subTest(operation=case[0]), self.assertRaises(ApiError):
                prepare(*case)

    def test_malformed_counts_and_partial_results_are_uncertain(self):
        bad = [None, {}, history(0), history(1, 1), history(0, 0, 999), history(2), history(True)]
        cross_kind = history()
        cross_kind['added']['episodes'] = 1
        bad.append(cross_kind)
        extra = history()
        extra['unexpected'] = 'synthetic-private'
        bad.append(extra)
        for body in bad:
            result = self.client(Response(200, body=body)).execute(prepare('mark_watched', 'movie', 11, NOW))
            self.assertEqual((result.outcome, result.reason), ('uncertain', 'invalid_response'))
            self.assertEqual(len(self.calls), 1)
        body = listed()
        del body['list']
        self.assertEqual(self.client(Response(201, body=body)).execute(
            prepare('add_movie_to_list', OWN, 11)).outcome, 'uncertain')

    def test_failure_categories_do_not_retry_or_leak_response(self):
        for status, reason in [(401, 'reauthenticate'), (403, 'forbidden'), (404, 'unavailable'),
                               (420, 'account_limit'), (429, 'rate_limit')]:
            result = self.client(Response(status, {'Retry-After': '90'}, {'private': 'synthetic'})).execute(
                prepare('mark_watched', 'movie', 11, NOW))
            self.assertEqual((result.outcome, result.reason), ('failed', reason))
            self.assertEqual(result.retry_after, 90 if status == 429 else None)
            self.assertNotIn('synthetic', repr(result))
            self.assertEqual(len(self.calls), 1)

    def test_ambiguous_statuses_and_timeout_are_never_replayed(self):
        plan = prepare('mark_watched', 'movie', 11, NOW)
        for status in (201, 204, 302, 500, 503):
            self.assertEqual(self.client(Response(status)).execute(plan).outcome, 'uncertain')
            self.assertEqual(len(self.calls), 1)
        calls = []
        def timeout(*args):
            calls.append(args)
            raise OSError('synthetic-secret-body')
        result = MutationClient(timeout, 'synthetic-client', 'synthetic-access').execute(plan)
        self.assertEqual(result.outcome, 'uncertain')
        self.assertNotIn('synthetic', repr(result))
        self.assertEqual(len(calls), 1)

    def test_action_body_tampering_rejected_before_callback(self):
        plan = prepare('mark_watched', 'movie', 11, NOW)
        plan.body['client_secret'] = 'synthetic-value'
        client = self.client(Response(200, body=history()))
        with self.assertRaisesRegex(ApiError, 'invalid_action'):
            client.execute(plan)
        self.assertEqual(self.calls, [])
