"""Playback attempts use fabricated links and callbacks; no player or service runs."""
from pathlib import Path
from types import SimpleNamespace
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.playback import PlaybackAttempt, PlaybackResult as Result

MOVIE = {'kind': 'movie', 'trakt_id': 42}
EPISODE = {'kind': 'episode', 'show_trakt_id': 12, 'season': 0, 'episode': 1}
SOURCE = 'https://files.example.org/authorized-file'
RESOLVED = 'https://cdn.example.org/media?private=synthetic'


class PlaybackTests(unittest.TestCase):
    def setUp(self):
        self.now, self.generation, self.cancel = 10.0, 3, False
        self.resolved, self.started = [], []

    def resolver(self, link):
        self.resolved.append(link)
        return SimpleNamespace(url=RESOLVED)

    def player(self, url, metadata, resume):
        self.started.append((url, metadata, resume))
        return True

    def attempt(self, resolver=None, player=None, **kwargs):
        return PlaybackAttempt(resolver or self.resolver, player or self.player,
                               lambda: self.cancel, lambda: self.generation, 3,
                               clock=lambda: self.now, **kwargs)

    def test_separate_source_and_identity_and_resume(self):
        for metadata in (MOVIE, EPISODE):
            with self.subTest(metadata=metadata):
                result = self.attempt().run(metadata, SOURCE, resume=12.5)
                self.assertEqual(result, Result.ACCEPTED)
                self.assertEqual(self.started[-1], (RESOLVED, metadata, 12.5))
                self.assertIsNot(self.started[-1][1], metadata)
        self.assertEqual(self.resolved, [SOURCE, SOURCE])

    def test_missing_source_never_resolves_metadata_as_link(self):
        for source in (None, ''):
            self.assertEqual(self.attempt().run(MOVIE, source), Result.SOURCE_MISSING)
        self.assertEqual(self.resolved, [])
        self.assertEqual(self.started, [])

    def test_invalid_identity_resume_or_source_stays_local(self):
        bad_metadata = [None, {}, {'kind': 'movie', 'trakt_id': True},
                        {'kind': 'movie', 'id': 42}, {'kind': 'movie', 'trakt_id': 0},
                        dict(MOVIE, title='unknown field'), dict(EPISODE, season=-1),
                        dict(EPISODE, episode=0), dict(EPISODE, show_trakt_id='12')]
        for metadata in bad_metadata:
            self.assertEqual(self.attempt().run(metadata, SOURCE), Result.INVALID_INPUT)
        for resume in (-1, float('nan'), float('inf'), True, '12', 604801, 10 ** 1000):
            self.assertEqual(self.attempt().run(MOVIE, SOURCE, resume), Result.INVALID_INPUT)
        for link in ('http://files.example.org/a', 'https://localhost/file',
                     'https://cdn.example.org/a|Cookie=secret', 'plugin://anything'):
            self.assertEqual(self.attempt().run(MOVIE, link), Result.INVALID_INPUT)
        self.assertEqual(self.resolved, [])

    def test_cancelled_or_changed_before_resolution(self):
        self.cancel = True
        self.assertEqual(self.attempt().run(MOVIE, SOURCE), Result.CANCELLED)
        self.cancel, self.generation = False, 4
        self.assertEqual(self.attempt().run(MOVIE, SOURCE), Result.SESSION_CHANGED)
        self.assertEqual(self.resolved, [])
        self.assertEqual(self.started, [])

    def test_cancellation_generation_and_expiry_after_resolution_prevent_dispatch(self):
        for state, value, result in [('cancel', True, Result.CANCELLED),
                                     ('generation', 4, Result.SESSION_CHANGED),
                                     ('now', 70.0, Result.EXPIRED)]:
            self.setUp()
            def resolve(link):
                setattr(self, state, value)
                return self.resolver(link)
            self.assertEqual(self.attempt(resolver=resolve).run(MOVIE, SOURCE), result)
            self.assertEqual(len(self.resolved), 1)
            self.assertEqual(self.started, [])

    def test_resolver_failure_and_unsafe_result_never_retry_or_dispatch(self):
        calls = []
        def failure(link):
            calls.append(link)
            raise OSError('private response ' + RESOLVED)
        attempt = self.attempt(resolver=failure)
        self.assertEqual(attempt.run(MOVIE, SOURCE), Result.RESOLVE_FAILED)
        self.assertEqual(attempt.run(MOVIE, SOURCE), Result.ALREADY_ATTEMPTED)
        self.assertEqual(calls, [SOURCE])
        for url in ('http://cdn.example.org/media', 'https://127.0.0.1/media',
                    'https://user:pass@cdn.example.org/a', 'https://cdn.example.org/a|x=y'):
            self.assertEqual(self.attempt(resolver=lambda link: SimpleNamespace(url=url)).run(
                MOVIE, SOURCE), Result.RESOLVE_FAILED)
        self.assertEqual(self.started, [])

    def test_player_failure_is_uncertain_never_replayed(self):
        def failure(url, metadata, resume):
            self.player(url, metadata, resume)
            raise OSError('private player ' + url)
        attempt = self.attempt(player=failure)
        self.assertEqual(attempt.run(MOVIE, SOURCE), Result.START_UNCERTAIN)
        self.assertEqual(attempt.run(MOVIE, SOURCE), Result.ALREADY_ATTEMPTED)
        self.assertEqual(len(self.started), 1)

    def test_player_false_rejected_unknown_response_uncertain(self):
        for response, result in [(False, Result.START_REJECTED),
                                 (None, Result.START_UNCERTAIN), (1, Result.START_UNCERTAIN)]:
            self.assertEqual(self.attempt(player=lambda *args: response).run(MOVIE, SOURCE), result)

    def test_state_change_during_dispatch_does_not_claim_playback_stopped(self):
        def player(url, metadata, resume):
            self.generation += 1
            return self.player(url, metadata, resume)
        self.assertEqual(self.attempt(player=player).run(MOVIE, SOURCE), Result.START_UNCERTAIN)
        self.assertEqual(len(self.started), 1)

    def test_reentrant_and_concurrent_invocations_cannot_dispatch_twice(self):
        nested = []
        def resolver(link):
            nested.append(attempt.run(MOVIE, SOURCE))
            thread = threading.Thread(target=lambda: nested.append(attempt.run(MOVIE, SOURCE)))
            thread.start()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
            return self.resolver(link)
        attempt = self.attempt(resolver=resolver)
        self.assertEqual(attempt.run(MOVIE, SOURCE), Result.ACCEPTED)
        self.assertEqual(nested, [Result.ALREADY_ATTEMPTED, Result.ALREADY_ATTEMPTED])
        self.assertEqual(attempt.run(MOVIE, SOURCE), Result.ALREADY_ATTEMPTED)
        self.assertEqual(len(self.started), 1)

    def test_callback_state_failure_and_bad_clock_fail_closed(self):
        def broken():
            raise RuntimeError('private state')
        attempt = PlaybackAttempt(self.resolver, self.player, broken, lambda: 3, 3)
        self.assertEqual(attempt.run(MOVIE, SOURCE), Result.STATE_UNAVAILABLE)
        for value in (float('nan'), float('inf'), -1, True):
            self.now = value
            self.assertEqual(self.attempt().run(MOVIE, SOURCE), Result.STATE_UNAVAILABLE)
        self.assertEqual(self.started, [])

    def test_private_data_is_absent_from_repr_outcomes(self):
        attempt = self.attempt()
        result = attempt.run(MOVIE, SOURCE)
        for text in (repr(attempt), str(result), repr(result)):
            self.assertNotIn(SOURCE, text)
            self.assertNotIn(RESOLVED, text)
            self.assertNotIn('trakt_id', text)

    def test_invalid_configuration(self):
        for duration in (0, 301, True, float('nan'), 10 ** 1000):
            with self.assertRaisesRegex(ValueError, '^invalid_playback_configuration$'):
                self.attempt(max_seconds=duration)
