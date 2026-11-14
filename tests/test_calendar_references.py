"""Personal-calendar references remain separate from lists and other feeds."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.trakt_preferences import AccountPreferences, PreferencesError


class CalendarReferenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.profile = Path(temporary.name)
        self.store = AccountPreferences(self.profile)

    def test_calendar_domains_are_distinct_and_continue_reference_is_unchanged(self):
        epoch, continuing = self.store.widget_feed_snapshot('synthetic-a')
        before = (self.profile / 'trakt/preferences.sqlite3').read_bytes()
        _, calendar = self.store.widget_feed_snapshot('synthetic-a', 'calendar')
        identity = [('episode', 11)]
        continued_item = self.store.widget_feed_item_refs('synthetic-a', 'continue', identity, epoch)[0]
        calendar_item = self.store.widget_feed_item_refs('synthetic-a', 'calendar', identity, epoch)[0]
        self.assertEqual(len({continuing, calendar, continued_item, calendar_item}), 4)
        self.assertEqual(self.store.widget_feed_snapshot('synthetic-a'), (epoch, continuing))
        self.assertEqual((self.profile / 'trakt/preferences.sqlite3').read_bytes(), before)
        reopened = AccountPreferences(self.profile)
        self.assertEqual(reopened.widget_feed_snapshot('synthetic-a', 'calendar'), (epoch, calendar))
        self.assertEqual(reopened.widget_feed_item_refs('synthetic-a', 'calendar', identity, epoch), [calendar_item])
        self.store.save('synthetic-a', ['trakt-list:1'])
        self.assertEqual(self.store.widget_feed_snapshot('synthetic-a', 'calendar'), (epoch, calendar))
        self.assertNotEqual(self.store.widget_feed_snapshot('synthetic-b', 'calendar')[1], calendar)
        self.store.clear_all()
        self.assertNotEqual(self.store.widget_feed_snapshot('synthetic-a', 'calendar')[1], calendar)
        with self.assertRaisesRegex(PreferencesError, 'preferences_changed'):
            self.store.widget_feed_item_refs('synthetic-a', 'calendar', identity, epoch)

    def test_calendar_has_episode_only_bound_without_relaxing_continue_limit(self):
        epoch, _ = self.store.widget_feed_snapshot('synthetic-a', 'calendar')
        identities = [('episode', number) for number in range(1, 1001)]
        refs = self.store.widget_feed_item_refs('synthetic-a', 'calendar', identities, epoch)
        self.assertEqual(len(set(refs)), 1000)
        with patch.object(self.store, '_transaction', side_effect=AssertionError('unexpected storage access')):
            for values in (identities + [('episode', 1001)], [('movie', 1)], [('show', 1)],
                           [('episode', True)], [('episode', 0)], [('episode', 2**63)],
                           [('episode', 1), ('episode', 1)]):
                with self.subTest(length=len(values)), self.assertRaises(PreferencesError):
                    self.store.widget_feed_item_refs('synthetic-a', 'calendar', values, epoch)
            with self.assertRaises(PreferencesError):
                self.store.widget_feed_item_refs('synthetic-a', 'continue', identities[:51], epoch)
