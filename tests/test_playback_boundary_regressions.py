"""Composition contracts for injected playback callbacks; no adapter is exercised."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.playback import PlaybackAttempt, PlaybackResult
from resources.lib.playback_events import PlaybackEvents, EventResult


class PlaybackBoundaryRegressions(unittest.TestCase):
    def setUp(self):
        self.generation = 8
        self.dispatched = []

    def attempt(self, player):
        return PlaybackAttempt(
            lambda link: type('Resolved', (), {'url': 'https://media.example/video'})(),
            player, lambda: False, lambda: self.generation, self.generation,
            clock=lambda: 10)

    def observer(self, attempt_id, generation):
        return PlaybackEvents(attempt_id, generation, lambda: False,
                              lambda: self.generation, clock=lambda: 10)

    def test_player_events_then_account_switch_make_dispatch_uncertain_and_clear_progress(self):
        observer = self.observer(71, self.generation)

        def player(url, identity, resume):
            self.dispatched.append((url, identity, resume))
            self.assertEqual(observer.snapshot().state, 'waiting')
            self.assertEqual(observer.snapshot().progress, None)
            self.assertEqual(observer.snapshot().watched, None)
            self.assertEqual(observer.observe(71, self.generation, 1, 'av_started'),
                             EventResult.ACCEPTED)
            self.assertEqual(observer.observe(71, self.generation, 2, 'sample',
                                              position=40, duration=100), EventResult.ACCEPTED)
            self.generation += 1
            return True

        attempt = self.attempt(player)
        result = attempt.run({'kind': 'movie', 'trakt_id': 21},
                             'https://source.example/file')

        self.assertEqual(result, PlaybackResult.START_UNCERTAIN)
        self.assertEqual(attempt.run({'kind': 'movie', 'trakt_id': 21},
                                     'https://source.example/file'),
                         PlaybackResult.ALREADY_ATTEMPTED)
        self.assertEqual(len(self.dispatched), 1)
        snapshot = observer.snapshot()
        self.assertEqual((snapshot.state, snapshot.position, snapshot.progress,
                          snapshot.watched),
                         ('session_changed', None, None, None))

    def test_old_player_callback_cannot_start_or_mutate_a_new_attempt(self):
        old = self.observer(71, self.generation)
        current = self.observer(72, self.generation)
        self.assertEqual(old.observe(71, self.generation, 1, 'av_started'),
                         EventResult.ACCEPTED)

        self.assertEqual(current.observe(71, self.generation, 2, 'av_started'),
                         EventResult.STALE)
        self.assertEqual(current.snapshot().state, 'waiting')
        self.assertEqual(current.observe(72, self.generation, 1, 'av_started'),
                         EventResult.ACCEPTED)
        self.assertEqual(current.observe(71, self.generation, 3, 'ended'),
                         EventResult.STALE)
        self.assertEqual(current.snapshot().state, 'playing')

    def test_account_switch_after_acceptance_clears_late_player_progress(self):
        observer = self.observer(71, self.generation)
        attempt = self.attempt(lambda *args: True)
        self.assertEqual(attempt.run({'kind': 'movie', 'trakt_id': 21},
                                     'https://source.example/file'), PlaybackResult.ACCEPTED)
        self.assertEqual(observer.observe(71, self.generation, 1, 'av_started'),
                         EventResult.ACCEPTED)
        self.assertEqual(observer.observe(71, self.generation, 2, 'sample',
                                          position=40, duration=100), EventResult.ACCEPTED)

        self.generation += 1

        self.assertEqual(observer.observe(71, self.generation - 1, 3, 'ended'),
                         EventResult.TERMINAL)
        snapshot = observer.snapshot()
        self.assertEqual((snapshot.state, snapshot.position, snapshot.progress,
                          snapshot.watched),
                         ('session_changed', None, None, None))


if __name__ == '__main__':
    unittest.main()
