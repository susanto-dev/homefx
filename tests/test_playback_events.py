"""Fabricated playback events; no Kodi player, network or watch-history writes."""
from dataclasses import FrozenInstanceError
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib.playback_events import PlaybackEvents, EventResult as Result, EventError


class PlaybackEventTests(unittest.TestCase):
    def setUp(self):
        self.now, self.generation, self.cancelled = 10, 2, False
        self.observer = PlaybackEvents(42, 2, lambda: self.cancelled, lambda: self.generation,
                                       clock=lambda: self.now)

    def event(self, sequence, event, **kwargs):
        return self.observer.observe(42, 2, sequence, event, **kwargs)

    def test_av_start_required_before_progress_or_completion(self):
        self.assertEqual(self.observer.snapshot().state, "waiting")
        self.assertEqual(self.event(1, "sample", position=50, duration=100), Result.INVALID)
        self.assertEqual(self.event(1, "ended"), Result.INVALID)
        self.assertIsNone(self.observer.snapshot().progress)
        self.assertEqual(self.event(1, "av_started"), Result.ACCEPTED)
        self.assertIsNone(self.observer.snapshot().progress)
        self.assertEqual(self.event(2, "sample", position=50, duration=100), Result.ACCEPTED)
        self.assertEqual(self.observer.snapshot().progress, 50)
        self.assertEqual(self.event(3, "ended"), Result.ACCEPTED)
        result = self.observer.snapshot()
        self.assertEqual((result.state, result.position, result.progress, result.watched),
                         ("ended", 50, 50, None))
        self.assertEqual(self.event(4, "sample", position=100, duration=100), Result.TERMINAL)

    def test_pause_resume_seek_and_unknown_duration(self):
        self.event(1, "av_started")
        self.event(2, "sample", position=90, duration=100)
        self.assertEqual(self.event(3, "paused"), Result.ACCEPTED)
        self.assertEqual(self.event(4, "paused"), Result.INVALID)
        self.assertEqual(self.event(4, "sample", position=12, duration=100), Result.ACCEPTED)
        self.assertEqual(self.event(5, "resumed"), Result.ACCEPTED)
        self.assertEqual(self.event(6, "resumed"), Result.INVALID)
        self.assertEqual(self.event(6, "sample", position=15), Result.ACCEPTED)
        result = self.observer.snapshot()
        self.assertEqual((result.state, result.position, result.duration, result.progress),
                         ("playing", 15, None, None))
        self.assertEqual(self.event(7, "stopped"), Result.ACCEPTED)
        self.assertIsNone(self.observer.snapshot().watched)

    def test_duplicate_wrong_attempt_and_out_of_order_events_are_ignored(self):
        self.event(5, "av_started")
        for identity, generation, sequence in ((42, 2, 5), (42, 2, 4), (43, 2, 6), (42, 3, 6)):
            self.assertEqual(self.observer.observe(identity, generation, sequence, "error"), Result.STALE)
        self.assertEqual(self.observer.snapshot().state, "playing")
        self.assertEqual(self.event(6, "av_started"), Result.INVALID)
        self.assertEqual(self.event(6, "sample", position=1, duration=2), Result.ACCEPTED)

    def test_account_switch_revokes_progress_even_after_end(self):
        self.event(1, "av_started")
        self.event(2, "sample", position=100, duration=100)
        self.event(3, "ended")
        self.generation = 3
        result = self.observer.snapshot()
        self.assertEqual((result.state, result.position, result.progress, result.watched),
                         ("session_changed", None, None, None))
        self.generation = 2
        self.assertEqual(self.event(4, "av_started"), Result.TERMINAL)

    def test_cancellation_and_startup_timeout_do_not_claim_player_stopped(self):
        self.cancelled = True
        self.assertEqual(self.event(1, "av_started"), Result.TERMINAL)
        self.assertEqual(self.observer.snapshot().state, "cancelled")
        self.setUp()
        self.now = 40
        self.assertEqual(self.event(1, "av_started"), Result.TERMINAL)
        self.assertEqual(self.observer.snapshot().state, "expired")
        self.setUp()
        self.event(1, "av_started")
        self.now = 4000
        self.assertEqual(self.event(2, "sample", position=3600, duration=7200), Result.ACCEPTED)

    def test_malformed_samples_never_replace_valid_progress(self):
        self.event(1, "av_started")
        self.event(2, "sample", position=10, duration=100)
        for position, duration in ((-1, 10), (True, 10), (float("nan"), 10),
                                   (1, float("inf")), (1, 0), (2, 1),
                                   (1, True), (604801, None), (10 ** 1000, None)):
            self.assertEqual(self.event(3, "sample", position=position, duration=duration), Result.INVALID)
        self.assertEqual(self.event(3, "ended", position=100, duration=100), Result.INVALID)
        self.assertEqual(self.observer.snapshot().progress, 10)
        self.assertEqual(self.event(3, "sample", position=100, duration=100), Result.ACCEPTED)
        self.assertIsNone(self.observer.snapshot().watched)

    def test_error_before_start_is_terminal_without_fabricated_progress(self):
        self.assertEqual(self.event(1, "error"), Result.ACCEPTED)
        result = self.observer.snapshot()
        self.assertEqual((result.state, result.position, result.progress), ("error", None, None))
        self.assertEqual(self.event(2, "av_started"), Result.TERMINAL)

    def test_bad_clocks_and_callbacks_fail_closed_and_redact(self):
        for now in (9, float("nan"), float("inf"), True, "private"):
            self.setUp()
            self.event(1, "av_started")
            self.event(2, "sample", position=10, duration=100)
            self.now = now
            self.assertEqual(self.event(3, "paused"), Result.TERMINAL)
            result = self.observer.snapshot()
            self.assertEqual((result.state, result.position), ("unavailable", None))
        def broken():
            raise RuntimeError("private callback data")
        observer = PlaybackEvents(1, 2, broken, lambda: 2)
        self.assertEqual(observer.snapshot().state, "unavailable")
        self.assertNotIn("private callback data", repr(observer))

    def test_account_change_during_cancellation_probe_invalidates_samples(self):
        def cancelled():
            self.generation = 3
            return False
        observer = PlaybackEvents(42, 2, cancelled, lambda: self.generation,
                                  clock=lambda: self.now)
        self.assertEqual(observer.observe(42, 2, 1, "av_started"), Result.TERMINAL)
        self.assertEqual(observer.snapshot().state, "session_changed")

    def test_reentrant_callback_cannot_mutate_observation(self):
        nested = []
        def cancelled():
            nested.append(self.observer.observe(42, 2, 3, "error"))
            with self.assertRaisesRegex(EventError, "^event_observer_busy$"):
                self.observer.snapshot()
            return False
        self.observer = PlaybackEvents(42, 2, cancelled, lambda: 2)
        self.assertEqual(self.event(1, "av_started"), Result.ACCEPTED)
        self.assertEqual(nested, [Result.BUSY])

    def test_configuration_event_validation_and_frozen_snapshot(self):
        for ident, gen, timeout in ((True, 2, 30), (0, 2, 30), (1, -1, 30),
                                   (1, 2, 0), (1, 2, float("inf")), (1, 2, 301)):
            with self.assertRaisesRegex(EventError, "^invalid_event_configuration$"):
                PlaybackEvents(ident, gen, lambda: False, lambda: 2, startup_timeout=timeout)
        for ident, gen, seq, name in ((True, 2, 1, "av_started"), (42, True, 1, "av_started"),
                                    (42, 2, True, "av_started"), (42, 2, 1, "unknown"),
                                    (42, 2, 1, [])):
            self.assertEqual(self.observer.observe(ident, gen, seq, name), Result.INVALID)
        result = self.observer.snapshot()
        with self.assertRaises(FrozenInstanceError):
            result.state = "ended"
        self.assertNotIn("42", repr(self.observer))
