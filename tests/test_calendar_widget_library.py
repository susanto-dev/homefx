"""Calendar widget journeys use fabricated responses and isolated account stores."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.trakt_auth import AuthError
from resources.lib.trakt_client import ApiError
from resources.lib.trakt_library import Library
from resources.lib.trakt_preferences import AccountPreferences, PreferencesError

NOW = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)


def entry(ident=11, number=1, stamp='2026-11-15T00:00:00Z'):
    return {'first_aired': stamp,
            'show': {'ids': {'trakt': 20}, 'title': 'Synthetic show', 'year': 2026},
            'episode': {'ids': {'trakt': ident}, 'title': 'Synthetic episode',
                        'season': 1, 'number': number, 'first_aired': stamp}}


class CalendarSession:
    def __init__(self):
        self.generation, self.data_revision = 1, 0
        self.account, self.connected = 'synthetic-a', True
        self.calls, self.hook, self.payload_hook = [], None, None
        self.entries = [entry()]

    def cache_key(self):
        self.assert_current(self.generation)
        return self.generation

    def assert_current(self, generation):
        if not self.connected or generation != self.generation:
            raise AuthError('session_changed')

    def read(self, operation, *args):
        self.calls.append((operation,) + args)
        if self.hook:
            self.hook(operation)
        if operation == 'settings':
            return {'user': {'ids': {'uuid': self.account}}}
        if operation != 'calendar_shows':
            raise AssertionError('Unexpected operation')
        payload = {'start_date': args[0], 'days': args[1], 'entries': deepcopy(self.entries)}
        if self.payload_hook:
            self.payload_hook(payload)
        return payload


class CalendarWidgetLibraryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.profile = temporary.name
        self.preferences = AccountPreferences(self.profile)
        self.session = CalendarSession()
        self.library = self.reopen()

    def reopen(self):
        return Library(self.session, preferences=AccountPreferences(self.profile))

    def source(self):
        return self.library.widget_calendar_sources()['items'][0]['ref']

    def test_source_reads_only_identity_without_selected_lists(self):
        result = self.library.widget_calendar_sources()
        self.assertEqual(self.session.calls, [('settings',)])
        self.assertEqual(self.preferences.load('synthetic-a'), [])
        self.assertEqual(len(result['items']), 1)
        result['guard']()
        self.assertEqual(self.session.calls, [('settings',)])

    def test_future_rows_identity_unknown_state_details_and_reopen(self):
        self.session.entries = [entry(12, 2, '2026-11-20T23:59:59Z'), entry(),
                                entry(13, 3, '2026-11-14T12:00:00Z')]
        ref = self.source()
        result = self.library.widget_calendar(ref, now=NOW)
        self.assertEqual((result['start_date'], result['days']), ('2026-11-14', 7))
        rows = result['items']
        self.assertEqual([row['trakt_id'] for row in rows], [11, 12])
        self.assertTrue(all(row['watched'] is None and row['playable'] is False for row in rows))
        self.assertTrue(all(row['show_trakt_id'] == 20 and row['show_title'] == 'Synthetic show' for row in rows))
        self.assertTrue(all('progress' not in row and 'resume' not in row for row in rows))
        self.assertEqual(self.library.widget_calendar_details(ref, rows[0]['item_ref'], now=NOW)['items'], [rows[0]])
        self.assertEqual(self.reopen().widget_calendar(ref, now=NOW)['items'], rows)
        self.assertTrue(all(call[0] in {'settings', 'calendar_shows'} for call in self.session.calls))

    def test_utc_day_boundary_uses_seven_dates_not_rolling_hours(self):
        # Local Nov 15 is still Nov 14 UTC. The final date is Nov 20, not Nov 21.
        now = datetime(2026, 11, 15, 1, tzinfo=timezone(timedelta(hours=2)))
        self.library.widget_calendar(self.source(), now=now)
        self.assertEqual(self.session.calls[-1], ('calendar_shows', '2026-11-14', 7))
        self.session.entries = [entry(stamp='2026-11-21T00:00:00Z')]
        with self.assertRaisesRegex(ApiError, 'calendar_window_mismatch'):
            self.library.widget_calendar(self.source(), now=NOW)

    def test_invalid_clock_and_ref_fail_before_activation(self):
        for now in (True, 'private', NOW.replace(tzinfo=None), datetime.max.replace(tzinfo=timezone.utc)):
            with self.subTest(kind=type(now).__name__), self.assertRaises(ApiError):
                self.library.widget_calendar('a' * 64, now=now)
        for ref in ('private', True, None):
            with self.assertRaises(ApiError):
                self.library.widget_calendar(ref, now=NOW)
        self.assertEqual(self.session.calls, [])

    def test_cross_feed_account_and_item_references_fail_closed(self):
        ref = self.source()
        continuing = self.library.widget_continue_sources()['items'][0]['ref']
        self.session.calls.clear()
        with self.assertRaisesRegex(ApiError, 'unavailable_selection'):
            self.library.widget_calendar(continuing, now=NOW)
        self.assertFalse(any(call[0] == 'calendar_shows' for call in self.session.calls))
        row = self.reopen().widget_calendar(ref, now=NOW)['items'][0]
        epoch, _ = self.preferences.widget_feed_snapshot('synthetic-a')
        wrong_item = self.preferences.widget_feed_item_refs('synthetic-a', 'continue', [('episode', 11)], epoch)[0]
        with self.assertRaisesRegex(ApiError, 'unavailable_selection'):
            self.reopen().widget_calendar_details(ref, wrong_item, now=NOW)
        self.session.account = 'synthetic-b'
        self.session.generation += 1
        self.session.calls.clear()
        with self.assertRaisesRegex(ApiError, 'unavailable_selection'):
            self.reopen().widget_calendar_details(ref, row['item_ref'], now=NOW)
        self.assertEqual(self.session.calls, [('settings',)])

    def test_midnight_recomputes_window_and_old_item_membership(self):
        ref = self.source()
        row = self.library.widget_calendar(ref, now=NOW)['items'][0]
        later = datetime(2026, 11, 15, 1, tzinfo=timezone.utc)
        with self.assertRaisesRegex(ApiError, 'unavailable_selection'):
            self.library.widget_calendar_details(ref, row['item_ref'], now=later)
        self.assertEqual(self.session.calls[-1], ('calendar_shows', '2026-11-15', 7))
        self.assertEqual(self.library.widget_calendar(ref, now=later)['items'], [])

    def test_empty_success_is_distinct_from_failure_denial_and_malformed_window(self):
        ref = self.source()
        self.session.entries = []
        self.assertEqual(self.library.widget_calendar(ref, now=NOW)['items'], [])
        for error in (ApiError('service_unavailable'), ApiError('forbidden'), AuthError('authorization_required')):
            def fail(operation):
                if operation == 'calendar_shows':
                    raise error
            self.session.hook = fail
            with self.assertRaises(type(error)):
                self.reopen().widget_calendar(ref, now=NOW)
        self.session.hook = None
        self.session.payload_hook = lambda payload: payload.update(days=6)
        with self.assertRaisesRegex(ApiError, 'calendar_window_mismatch'):
            self.reopen().widget_calendar(ref, now=NOW)

    def test_account_revision_and_epoch_changes_during_read_reject_rows(self):
        for change in ('account', 'revision', 'epoch'):
            with self.subTest(change=change):
                self.session.hook = None
                self.library = self.reopen()
                ref = self.source()
                def mutate(operation):
                    if operation == 'calendar_shows':
                        if change == 'account': self.session.generation += 1
                        elif change == 'revision': self.session.data_revision += 1
                        else: self.preferences.clear_all()
                self.session.hook = mutate
                with self.assertRaises((AuthError, ApiError)):
                    self.library.widget_calendar(ref, now=NOW)
                self.assertEqual(len(self.library._cache._entries), 0)

    def test_clear_and_rotation_invalidate_pending_guard_but_not_same_account_reopen(self):
        ref = self.source()
        result = self.library.widget_calendar(ref, now=NOW)
        self.session.generation += 1
        with self.assertRaises(AuthError): result['guard']()
        self.assertEqual(self.reopen().widget_calendar_sources()['items'][0]['ref'], ref)
        result = self.reopen().widget_calendar(ref, now=NOW)
        self.preferences.clear_all()
        with self.assertRaises(PreferencesError): result['guard']()
        with self.assertRaisesRegex(ApiError, 'unavailable_selection'):
            self.reopen().widget_calendar(ref, now=NOW)
        self.session.connected = False
        before = len(self.session.calls)
        with self.assertRaises(AuthError): self.reopen().widget_calendar(ref, now=NOW)
        self.assertEqual(len(self.session.calls), before)

    def test_refs_issued_after_clear_cannot_escape_final_guard(self):
        ref = self.source()
        original = self.library._preferences.widget_feed_item_refs
        def changed(*args, **kwargs):
            refs = original(*args, **kwargs)
            self.preferences.clear_all()
            return refs
        with patch.object(self.library._preferences, 'widget_feed_item_refs', side_effect=changed):
            with self.assertRaises(PreferencesError):
                self.library.widget_calendar(ref, now=NOW)
