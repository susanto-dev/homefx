"""Personal-calendar directories use fabricated service responses only."""
from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from widget_fixtures import WidgetDirectoryFixture
from resources.lib.trakt_auth import TokenSet
from resources.lib.trakt_client import ApiError, Response
from resources.lib import trakt_views
from resources.lib import trakt_widget_routes as routes
from resources.lib.trakt_widget_ui import WidgetDirectoryUI


def airing(ident, number, stamp, show=20, title='Synthetic episode'):
    return {'first_aired': stamp,
            'show': {'ids': {'trakt': show}, 'title': '[B]Synthetic show ' + str(show) + '[/B]', 'year': 2026},
            'episode': {'ids': {'trakt': ident}, 'season': 2, 'number': number,
                        'title': title, 'first_aired': stamp}}


class CalendarWidgetUITests(WidgetDirectoryFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.library.select_lists([])
        self.current = datetime(2026, 11, 14, 12, tzinfo=timezone.utc)
        self.entries = [airing(202, 2, '2026-11-16T00:00:00Z', 30),
                        airing(201, 1, '2026-11-14T13:00:00Z'),
                        airing(203, 3, '2026-11-14T10:00:00Z')]
        self.intercept = self.responses
        self.library = self.reopen()
        self.ui = WidgetDirectoryUI(self, self.item, lambda: self, self, dialog=self,
                                    addon_id='plugin.video.homefx.development')
        fixed = patch.object(trakt_views, '_now', side_effect=lambda now=None: self.current)
        fixed.start()
        self.addCleanup(fixed.stop)
        self.calls.clear()

    def responses(self, path):
        if path.startswith(('/users/me/lists?', '/users/likes/lists?', '/sync/', '/shows/')):
            raise AssertionError('Calendar does not request selected lists, pauses or watched progress')
        if path.startswith('/calendars/my/shows/'):
            self.assertEqual(path, '/calendars/my/shows/' + self.current.date().isoformat() + '/7?extended=full')
            return Response(200, body=self.entries)
        return None

    def url(self, route, **params):
        return routes.url(route, addon_id='plugin.video.homefx.development', **params)

    def render(self, target, widget=True):
        return super().render(target, widget=widget)

    def feed(self):
        self.assertEqual(self.render(self.url('trakt_calendar_sources')).state, 'ready')
        self.assertEqual(len(self.rows), 1)
        self.assertTrue(self.rows[0][2])
        return self.rows[0][0]

    def test_static_picker_and_account_source_do_not_read_calendar(self):
        class Forbidden:
            def __getattribute__(self, name):
                raise AssertionError('Static menu opened runtime')
        self.assertEqual(self.ui.render(Forbidden(), 1, '?route=trakt_widget_menu', widget=True).state, 'ready')
        self.assertEqual(self.rows[-1][1].label, 'Upcoming episodes (personal calendar)')
        self.assertEqual(routes.parse(urlsplit(self.rows[-1][0]).query), ('trakt_calendar_sources', {}))
        self.assertEqual(self.calls, [])
        target = self.feed()
        self.assertEqual(routes.parse(urlsplit(target).query)[0], 'trakt_calendar')
        self.assertFalse(any('/calendars/' in path for path in self.calls))
        self.assertEqual(self.events, [])

    def test_future_rows_show_parent_identity_unknown_watch_and_calendar_only_actions(self):
        target = self.feed()
        self.assertEqual(self.render(target).state, 'ready')
        self.assertEqual(len(self.rows), 2)
        first = self.rows[0][1]
        self.assertEqual(first.label, '(B)Synthetic show 20(/B) — S2E1 — Synthetic episode')
        self.assertEqual(first.tag.values['ids'], ({'trakt': '201', 'tvshow.trakt': '20'}, 'trakt'))
        self.assertEqual(first.tag.values['show_title'], '(B)Synthetic show 20(/B)')
        self.assertEqual((first.tag.values['season'], first.tag.values['episode']), (2, 1))
        for url, item, folder in self.rows:
            self.assertFalse(folder)
            self.assertEqual(item.tag.values['type'], 'episode')
            self.assertNotIn('playcount', item.tag.values)
            self.assertIn('Watch status: unknown', item.tag.values['plot'])
            self.assertNotIn('Unfinished progress', item.tag.values['plot'])
            self.assertEqual(routes.parse(urlsplit(url).query)[0], 'trakt_calendar_details')
            self.assertEqual(item.actions, [('Open personal calendar', 'Container.Update(' + target + ')')])
        self.assertIn('2026-11-14 through 2026-11-20', self.categories[-1])
        self.assertIn('not every selected-list show', self.categories[-1])
        self.assertEqual(self.ends, [(True, False)])
        self.assertEqual(self.events, [])

    def test_detail_is_metadata_with_parent_title_and_not_a_widget_action(self):
        self.assertEqual(self.render(self.feed()).state, 'ready')
        target = self.rows[0][0]
        self.assertEqual(self.render(target, widget=False).state, 'ready')
        self.assertEqual(self.details[-1][0], '(B)Synthetic show 20(/B) — S2E1 — Synthetic episode')
        self.assertIn('Watch status: unknown', self.details[-1][1])
        self.assertIn('No playable source or playback action', self.details[-1][1])
        self.assertNotIn('Unfinished progress', self.details[-1][1])
        self.assertEqual(self.render(target, widget=True).state, 'failed')
        self.assertEqual(len(self.details), 1)

    def test_routes_reject_dates_public_ids_and_wrong_scope_before_reads(self):
        ref, item = 'a' * 64, 'b' * 64
        for query in ['?route=trakt_calendar', '?route=trakt_calendar&ref=20',
                      '?route=trakt_calendar&ref=' + ref + '&start=2026-11-14',
                      '?route=trakt_calendar&ref=' + ref + '&days=7',
                      '?route=trakt_calendar&ref=' + ref + '&ref=' + ref,
                      '?route=trakt_calendar_sources&ref=' + ref,
                      '?route=trakt_calendar_details&ref=' + ref + '&item=' + item + '&season=2']:
            self.assertEqual(self.render(query).state, 'failed')
        self.assertEqual(self.calls, [])
        for route, params in [('trakt_calendar', {'ref': ref}),
                              ('trakt_calendar_details', {'ref': ref, 'item': item})]:
            self.assertEqual(routes.parse(urlsplit(self.url(route, **params)).query), (route, params))

    def test_empty_offline_denied_and_authorization_are_not_interchangeable(self):
        target = self.feed()
        self.entries = []
        self.assertEqual(self.render(target).state, 'empty')
        self.assertEqual(self.ends, [(True, False)])
        def offline(path):
            raise ApiError('transport')
        self.intercept = offline
        self.library = self.reopen()
        self.assertEqual(self.render(target).state, 'offline')
        self.assertEqual(self.ends, [(False, False)])
        self.intercept = lambda path: Response(403, body={}) if '/calendars/' in path else None
        self.library = self.reopen()
        self.assertNotIn(self.render(target).state, {'ready', 'empty', 'partial'})
        self.assertEqual(self.rows, [])
        self.store.disconnect()
        self.assertEqual(self.render(target).state, 'authorization_needed')
        self.assertEqual(self.details, [])

    def test_final_guard_and_cancellation_prevent_submission(self):
        target = self.feed()
        self.on_item = self.store.disconnect
        self.assertNotIn(self.render(target).state, {'ready', 'empty', 'partial'})
        self.assertEqual(self.rows, [])
        self.assertEqual(self.ends, [(False, False)])
        self.calls.clear()
        self.abort = True
        self.assertEqual(self.render(target).state, 'cancelled')
        self.assertEqual(self.calls, [])
        self.assertEqual(self.events, [])

    def test_saved_feed_reopens_but_not_under_replacement_account(self):
        target = self.feed()
        self.assertEqual(self.render(target).state, 'ready')
        expected = [(url, item.label, folder) for url, item, folder in self.rows]
        self.library = self.reopen()
        self.assertEqual(self.render(target).state, 'ready')
        self.assertEqual([(url, item.label, folder) for url, item, folder in self.rows], expected)
        self.store.install(TokenSet('synthetic-b', 'synthetic-refresh-b', 10000))
        self.library = self.reopen()
        self.assertNotIn(self.render(target).state, {'ready', 'empty', 'partial'})
        self.assertEqual(self.rows, [])

    def test_detail_rechecks_new_day_membership_instead_of_old_metadata(self):
        target = self.feed()
        self.assertEqual(self.render(target).state, 'ready')
        detail = self.rows[0][0]
        self.current = datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
        self.entries = []
        self.library = self.reopen()
        self.assertEqual(self.render(detail, widget=False).state, 'unavailable')
        self.assertNotIn('Synthetic episode', self.details[-1][1])
        self.assertEqual(self.render(target).state, 'empty')
        self.assertIn('2026-11-15 through 2026-11-21', self.categories[-1])
