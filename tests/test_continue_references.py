"""Account-wide feed locators use only fabricated identities and temporary stores."""
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.trakt_preferences import AccountPreferences, PreferencesError


class ContinueReferenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.profile = Path(temporary.name)
        self.store = AccountPreferences(self.profile)
        self.path = self.profile / 'trakt/preferences.sqlite3'

    def test_empty_selection_feed_and_items_survive_reopen_without_persisting_data(self):
        before = self.path.read_bytes()
        epoch, feed = self.store.widget_feed_snapshot('synthetic-a')
        identities = [('movie', 10), ('episode', 20)]
        refs = self.store.widget_feed_item_refs('synthetic-a', 'continue', identities, epoch)
        self.assertEqual(self.store.load('synthetic-a'), [])
        self.assertEqual(self.path.read_bytes(), before)
        reopened = AccountPreferences(self.profile)
        self.assertEqual(reopened.widget_feed_snapshot('synthetic-a'), (epoch, feed))
        self.assertEqual(reopened.widget_feed_item_refs('synthetic-a', 'continue', identities, epoch), refs)
        for value in [feed, *refs]:
            self.assertRegex(value, r'^[a-f0-9]{64}$')
        with sqlite3.connect(self.path) as connection:
            self.assertEqual(connection.execute('PRAGMA user_version').fetchone(), (3,))
            self.assertEqual({row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")},
                {'selections', 'preference_state', 'widget_identity'})
            self.assertEqual(connection.execute('SELECT COUNT(*) FROM selections').fetchone(), (0,))

    def test_account_profile_kind_and_list_domains_are_distinct(self):
        self.store.save('synthetic-a', ['trakt-list:1'])
        epoch, feed = self.store.widget_feed_snapshot('synthetic-a')
        identities = [('movie', 10), ('episode', 10)]
        refs = self.store.widget_feed_item_refs('synthetic-a', 'continue', identities, epoch)
        list_ref = self.store.widget_snapshot('synthetic-a')[2][0]
        list_item = self.store.widget_item_refs('synthetic-a', 'trakt-list:1', [('movie', 10)], epoch)[0]
        other_epoch, other_feed = self.store.widget_feed_snapshot('synthetic-b')
        other_refs = self.store.widget_feed_item_refs('synthetic-b', 'continue', identities, other_epoch)
        with tempfile.TemporaryDirectory() as other_profile:
            other = AccountPreferences(other_profile)
            profile_epoch, profile_feed = other.widget_feed_snapshot('synthetic-a')
            profile_refs = other.widget_feed_item_refs('synthetic-a', 'continue', identities, profile_epoch)
        values = [feed, *refs, list_ref, list_item, other_feed, *other_refs, profile_feed, *profile_refs]
        self.assertEqual(len(values), len(set(values)))

    def test_saved_list_changes_do_not_change_account_feed_identity(self):
        before = self.store.widget_feed_snapshot('synthetic-a')
        refs = self.store.widget_feed_item_refs('synthetic-a', 'continue', [('movie', 10)], before[0])
        self.store.save('synthetic-a', ['trakt-list:1', 'trakt-list:2'])
        self.store.save('synthetic-a', [])
        self.assertEqual(self.store.widget_feed_snapshot('synthetic-a'), before)
        self.assertEqual(self.store.widget_feed_item_refs('synthetic-a', 'continue', [('movie', 10)], before[0]), refs)

    def test_clear_epoch_invalidates_feed_items_and_old_derivation(self):
        for clear in (lambda: self.store.clear('synthetic-a'), self.store.clear_all):
            epoch, feed = self.store.widget_feed_snapshot('synthetic-a')
            refs = self.store.widget_feed_item_refs('synthetic-a', 'continue', [('episode', 20)], epoch)
            clear()
            next_epoch, next_feed = self.store.widget_feed_snapshot('synthetic-a')
            self.assertGreater(next_epoch, epoch)
            self.assertNotEqual(feed, next_feed)
            self.assertNotEqual(refs, self.store.widget_feed_item_refs(
                'synthetic-a', 'continue', [('episode', 20)], next_epoch))
            with self.assertRaisesRegex(PreferencesError, '^preferences_changed$'):
                self.store.widget_feed_item_refs('synthetic-a', 'continue', [('episode', 20)], epoch)

    def test_invalid_feed_account_identity_or_epoch_fails_before_transaction(self):
        with patch.object(self.store, '_transaction', side_effect=AssertionError('unexpected storage access')):
            for feed in (None, True, [], '', 'Continue', 'next', 'continue\n'):
                with self.subTest(feed_type=type(feed).__name__):
                    with self.assertRaisesRegex(PreferencesError, '^invalid_widget_reference$'):
                        self.store.widget_feed_snapshot('synthetic-a', feed)
                    with self.assertRaisesRegex(PreferencesError, '^invalid_widget_reference$'):
                        self.store.widget_feed_item_refs('synthetic-a', feed, [], 0)
            for account in (None, True, '', 'private\naccount'):
                with self.assertRaisesRegex(PreferencesError, '^invalid_account_identity$'):
                    self.store.widget_feed_snapshot(account)
            for epoch in (None, True, -1, 2**63, 0.0, '0'):
                with self.assertRaisesRegex(PreferencesError, '^invalid_widget_reference$'):
                    self.store.widget_feed_item_refs('synthetic-a', 'continue', [], epoch)

    def test_item_identity_bounds_types_duplicates_and_order(self):
        epoch, _ = self.store.widget_feed_snapshot('synthetic-a')
        bad = [None, {}, 'movie', [('movie', True)], [('movie', 0)], [('movie', 2**63)],
               [('movie', 1.0)], [('show', 1)], [(None, 1)], [('movie',)],
               [('movie', 1, 2)], [('movie', 1), ['movie', 1]],
               [('movie', number) for number in range(1, 52)]]
        with patch.object(self.store, '_transaction', side_effect=AssertionError('unexpected storage access')):
            for identities in bad:
                with self.subTest(identity_type=type(identities).__name__), self.assertRaisesRegex(
                        PreferencesError, '^invalid_widget_reference$'):
                    self.store.widget_feed_item_refs('synthetic-a', 'continue', identities, epoch)
        self.assertEqual(self.store.widget_feed_item_refs('synthetic-a', 'continue', [], epoch), [])
        identities = [('movie', number) for number in range(1, 51)]
        refs = self.store.widget_feed_item_refs('synthetic-a', 'continue', identities, epoch)
        self.assertEqual(len(refs), 50)
        self.assertEqual(len(set(refs)), 50)
        self.assertEqual(self.store.widget_feed_item_refs(
            'synthetic-a', 'continue', tuple(reversed(identities)), epoch), list(reversed(refs)))

    def test_missing_store_is_not_recreated_by_feed_reads(self):
        epoch, _ = self.store.widget_feed_snapshot('synthetic-a')
        self.path.unlink()
        for read in (lambda: self.store.widget_feed_snapshot('synthetic-a'),
                     lambda: self.store.widget_feed_item_refs('synthetic-a', 'continue', [('movie', 10)], epoch)):
            with self.assertRaisesRegex(PreferencesError, '^preferences_unavailable$'):
                read()
            self.assertFalse(self.path.exists())


if __name__ == '__main__':
    unittest.main()
