"""Synthetic browsing contracts: dates and watched state never assert playability."""
from datetime import date, timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib import catalogue as model

TODAY = date(2026, 11, 12)


class BrowsingTests(unittest.TestCase):
    def setUp(self):
        self.items = model.catalogue(TODAY)
        self.state = {'saved_movies': ['m3', 'm4', 'm1', 'm2', 'e1', 's1', 'missing']}

    def ids(self, **kwargs):
        return [row['id'] for row in model.view('list', self.items, self.state,
                                               'saved', today=TODAY, **kwargs)]

    def test_list_filters_keep_resume_first_and_future_unwatched(self):
        self.assertEqual(self.ids(), ['m1', 'm2', 'm3', 'm4'])
        self.assertEqual(self.ids(list_filter='unwatched'), ['m1', 'm2', 'm3'])
        self.assertEqual(self.ids(list_filter='released_unwatched'), ['m1', 'm2'])
        self.assertEqual(self.ids(list_filter='upcoming'), ['m3'])
        self.assertEqual([r['id'] for r in model.view('list', self.items, {}, 'weekend',
                         today=TODAY, list_filter='released_unwatched')], ['m1', 'm2'])

    def test_mark_watched_removes_resume_and_mark_unwatched_does_not_restore_progress(self):
        original = self.items['m1'].copy()
        self.items = model.apply_state(self.items, {'watched': {'m1': True}})
        self.assertEqual(self.ids(list_filter='released_unwatched'), ['m2'])
        self.items = model.apply_state(self.items, {'watched': {'m1': False}})
        self.assertEqual(self.ids(list_filter='released_unwatched'), ['m2', 'm1'])
        self.assertEqual(self.items['m1']['progress'], 0)
        self.assertEqual(original['progress'], 42)

    def test_unknown_release_dates_are_not_released_or_upcoming(self):
        for unknown in (None, '', 'unknown', '2026-02-30'):
            with self.subTest(unknown=unknown):
                self.items['m2']['date'] = unknown
                self.assertEqual(self.ids(list_filter='released_unwatched'), ['m1'])
                self.assertEqual(self.ids(list_filter='upcoming'), ['m3'])
                self.assertIn('m2', self.ids(list_filter='unwatched'))

    def test_today_is_released_and_upcoming_is_strictly_future(self):
        self.items['m3']['date'] = TODAY.isoformat()
        self.assertEqual(self.ids(list_filter='upcoming'), [])
        self.assertEqual(self.ids(list_filter='released_unwatched'), ['m1', 'm3', 'm2'])

    def test_upcoming_movies_use_only_saved_movies_nearest_first(self):
        self.items['m2']['date'] = (TODAY + timedelta(days=1)).isoformat()
        self.items['m5']['date'] = (TODAY + timedelta(days=2)).isoformat()
        self.items['m2']['progress'] = 90
        rows = model.view('upcoming_movies', self.items, self.state, today=TODAY)
        self.assertEqual([r['id'] for r in rows], ['m2', 'm3'])
        self.assertEqual(model.view('upcoming_movies', self.items, {}, today=TODAY), [])

    def test_season_counts_include_specials_unknown_dates_and_narrative_order(self):
        self.items['special'] = dict(self.items['e1'], id='special', season=0)
        self.items['s2e1'] = dict(self.items['e4'], id='s2e1', season=2, episode=1)
        self.items['s2e2'] = dict(self.items['e5'], id='s2e2', season=2, episode=2)
        self.items['unknown'] = dict(self.items['e6'], id='unknown', season=2, episode=3, date=None)
        counts = model.seasons(self.items, 's1', TODAY)
        self.assertEqual(counts, [
            {'season': 0, 'total': 1, 'watched': 1, 'aired_unwatched': 0, 'upcoming': 0},
            {'season': 1, 'total': 6, 'watched': 2, 'aired_unwatched': 2, 'upcoming': 2},
            {'season': 2, 'total': 3, 'watched': 0, 'aired_unwatched': 1, 'upcoming': 1},
        ])
        rows = model.view('show', self.items, {}, 's1', today=TODAY, season=2)
        self.assertEqual([r['id'] for r in rows], ['s2e1', 's2e2', 'unknown'])
        rows = model.view('show', self.items, {}, 's1', today=TODAY, season=2,
                          episode_filter='aired_unwatched')
        self.assertEqual([r['id'] for r in rows], ['s2e1'])
        self.assertEqual(model.view('show', self.items, {}, 's1', season=999), [])

    def test_counts_refresh_after_watched_change_and_do_not_include_other_series(self):
        self.items['other'] = dict(self.items['e2'], id='other', show='other-show')
        changed = model.apply_state(self.items, {'watched': {'e2': True}})
        self.assertEqual(model.seasons(changed, 's1', TODAY)[0]['aired_unwatched'], 1)
        self.assertEqual(model.seasons(changed, 's1', TODAY)[0]['watched'], 3)
        self.assertEqual(model.seasons(self.items, 's1', TODAY)[0]['total'], 6)

    def test_bad_filters_and_series_identifiers_are_rejected(self):
        for value in (None, [], {}, 'invalid', True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.ids(list_filter=value)
        for value in (-1, 1000, True, '1', 1.5, []):
            with self.subTest(value=value), self.assertRaises(ValueError):
                model.view('show', self.items, {}, 's1', season=value)
        for key in ('m1', 'e1', 'missing', None, []):
            with self.subTest(key=key), self.assertRaises(ValueError):
                model.view('show', self.items, {}, key)
            with self.subTest(key=key), self.assertRaises(ValueError):
                model.seasons(self.items, key)


if __name__ == '__main__':
    unittest.main()
