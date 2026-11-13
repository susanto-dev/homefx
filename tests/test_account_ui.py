"""Injected device-code UI tests; no Kodi, service, account or profile access."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.account_ui import AccountUI, UIError


class Dialog:
    def __init__(self):
        self.prompts, self.answer = [], True

    def yesno(self, title, message):
        self.prompts.append((title, message))
        return self.answer


class Progress:
    def __init__(self):
        self.messages, self.updates, self.closed = [], [], 0
        self.cancel = False
        self.failure = None

    def create(self, title, message):
        self.messages.append((title, message))
        if self.failure == 'create':
            raise RuntimeError('synthetic-private-code')

    def update(self, percent):
        self.updates.append(percent)
        if self.failure == 'update':
            raise RuntimeError('synthetic-private-code')

    def iscanceled(self):
        if self.failure == 'cancel':
            raise RuntimeError('synthetic-private-code')
        return self.cancel

    def close(self):
        self.closed += 1
        if self.failure == 'close':
            raise RuntimeError('synthetic-private-code')


class Monitor:
    def __init__(self):
        self.abort = False
        self.waits = []
        self.on_wait = lambda: None

    def abortRequested(self):
        return self.abort

    def waitForAbort(self, seconds):
        self.waits.append(seconds)
        self.on_wait()
        return self.abort


class AccountUITests(unittest.TestCase):
    def make(self, provider='trakt'):
        self.dialog, self.progress, self.monitor = Dialog(), Progress(), Monitor()
        self.creations = 0

        def factory():
            self.creations += 1
            return self.progress
        return AccountUI(provider, self.dialog, factory, self.monitor)

    def test_construction_is_inactive_and_only_explicit_display_receives_code(self):
        ui = self.make()
        self.assertEqual(self.creations, 0)
        self.assertEqual(self.dialog.prompts, [])
        self.assertEqual(self.monitor.waits, [])
        ui.show_code('SYNTHETIC-CODE', 'https://trakt.tv/activate')
        self.assertEqual(self.creations, 1)
        self.assertIn('SYNTHETIC-CODE', self.progress.messages[0][1])
        self.assertEqual(self.progress.updates, [0])
        self.assertNotIn('SYNTHETIC', repr(ui))
        self.assertFalse(any(isinstance(value, str) and 'SYNTHETIC' in value
                             for value in vars(ui).values()))
        ui.close()
        ui.close()
        self.assertEqual(self.progress.closed, 1)
        self.assertIsNone(ui._progress)

    def test_provider_specific_confirmations_do_not_promise_remote_revocation(self):
        for provider in ('trakt', 'realdebrid'):
            ui = self.make(provider)
            self.assertTrue(ui.confirm_replace())
            self.assertTrue(ui.confirm_disconnect())
            replace, disconnect = [message for _, message in self.dialog.prompts]
            self.assertIn('cancelled', replace)
            self.assertIn('does not revoke', disconnect)
            self.assertIn('backups', disconnect)
            if provider == 'trakt':
                self.assertIn('all saved HomeFX list choices', disconnect)
            else:
                self.assertIn('Trakt list choices are unchanged', disconnect)
            self.dialog.answer = False
            self.assertFalse(ui.confirm_disconnect())
            self.assertEqual(self.creations, 0)

    def test_known_provider_urls_only_and_invalid_prompts_never_open_dialog(self):
        for provider, url in [('trakt', 'https://auth.trakt.tv/activate'),
                              ('trakt', 'https://trakt.tv/activate'),
                              ('realdebrid', 'https://real-debrid.com/device')]:
            ui = self.make(provider)
            ui.show_code('DEMO-123', url)
            self.assertIn(url, self.progress.messages[0][1])
        bad = [('DEMO', 'https://evil.invalid/activate'),
               ('DEMO', 'https://trakt.tv/activate?code=private'),
               ('DEMO', 'https://trakt.tv.evil.invalid/activate'),
               ('DEMO', 'http://trakt.tv/activate'),
               ('DEMO', 'https://trakt.tv/activate#private'),
               ('DEMO', 'https://real-debrid.com/device'),
               ('', 'https://trakt.tv/activate'),
               ('x' * 129, 'https://trakt.tv/activate'),
               ('[COLOR red]secret', 'https://trakt.tv/activate'),
               ('secret\ncode', 'https://trakt.tv/activate')]
        for code, url in bad:
            ui = self.make()
            with self.assertRaisesRegex(UIError, '^ui_failed$'):
                ui.show_code(code, url)
            self.assertEqual(self.creations, 0)
            self.assertEqual(self.progress.messages, [])

    def test_activation_url_variants_never_open_a_dialog_or_leak_prompt(self):
        for base in ('https://auth.trakt.tv/activate', 'https://trakt.tv/activate'):
            urls = (base + '/', base + '?code=PRIVATE', base + '#PRIVATE',
                    base.replace('/activate', '/other'),
                    base.replace('https://', 'http://'),
                    base.replace('https://', 'https://name:PRIVATE@'),
                    base.replace('/activate', ':443/activate'),
                    base.replace('/activate', ':8443/activate'),
                    base.replace('.tv/', '.tv.evil.invalid/'),
                    base.replace('/activate', '/%61ctivate'),
                    base + '\nPRIVATE')
            for url in urls:
                with self.subTest(url=url):
                    ui = self.make()
                    with self.assertRaisesRegex(UIError, '^ui_failed$') as caught:
                        ui.show_code('PRIVATE-CODE', url)
                    self.assertEqual(self.creations, 0)
                    self.assertEqual(self.progress.messages, [])
                    self.assertNotIn('PRIVATE', str(caught.exception))
                    self.assertNotIn('PRIVATE', repr(ui))
        ui = self.make('realdebrid')
        with self.assertRaisesRegex(UIError, '^ui_failed$'):
            ui.show_code('PRIVATE-CODE', 'https://auth.trakt.tv/activate')
        self.assertEqual(self.creations, 0)

    def test_partial_create_and_update_failures_close_once_and_fail_closed(self):
        for failure in ('create', 'update'):
            ui = self.make()
            self.progress.failure = failure
            with self.assertRaisesRegex(UIError, '^ui_failed$') as caught:
                ui.show_code('SYNTHETIC-CODE', 'https://trakt.tv/activate')
            self.assertNotIn('synthetic', str(caught.exception))
            self.assertEqual(self.progress.closed, 1)
            ui.close()
            self.assertEqual(self.progress.closed, 1)
            with self.assertRaisesRegex(UIError, '^ui_failed$'):
                ui.cancelled()

    def test_close_failure_is_redacted_and_does_not_repeat_cleanup(self):
        ui = self.make()
        ui.show_code('DEMO', 'https://trakt.tv/activate')
        self.progress.failure = 'close'
        with self.assertRaisesRegex(UIError, '^ui_cleanup_failed$'):
            ui.close()
        ui.close()
        self.assertEqual(self.progress.closed, 1)
        self.assertIsNone(ui._progress)

    def test_wait_slices_and_stops_on_progress_cancel_or_system_abort(self):
        for signal in ('cancel', 'abort'):
            ui = self.make()
            ui.show_code('DEMO', 'https://trakt.tv/activate')
            def stop():
                if len(self.monitor.waits) == 3:
                    if signal == 'cancel':
                        self.progress.cancel = True
                    else:
                        self.monitor.abort = True
            self.monitor.on_wait = stop
            self.assertTrue(ui.wait(60))
            self.assertEqual(len(self.monitor.waits), 3)
            self.assertTrue(all(0 < item <= 0.1 for item in self.monitor.waits))
        ui = self.make()
        self.monitor.abort = True
        self.assertTrue(ui.wait(1))
        self.assertEqual(self.monitor.waits, [])

    def test_nonadvancing_monitor_is_bounded_and_zero_wait_is_nonblocking(self):
        ui = self.make()
        self.assertFalse(ui.wait(0))
        self.assertEqual(self.monitor.waits, [])
        self.assertFalse(ui.wait(60))
        self.assertEqual(len(self.monitor.waits), 600)
        self.assertAlmostEqual(sum(self.monitor.waits), 60)
        self.assertTrue(all(0 < item <= 0.1 for item in self.monitor.waits))

    def test_invalid_wait_and_probe_results_fail_closed_without_raw_details(self):
        for seconds in (True, -1, 61, float('nan'), float('inf'), '1'):
            ui = self.make()
            with self.assertRaisesRegex(UIError, '^ui_failed$'):
                ui.wait(seconds)
            self.assertEqual(self.monitor.waits, [])
        ui = self.make()
        self.monitor.abort = 'private-value'
        with self.assertRaisesRegex(UIError, '^ui_failed$'):
            ui.cancelled()
        ui = self.make()
        ui.show_code('DEMO', 'https://trakt.tv/activate')
        self.progress.failure = 'cancel'
        with self.assertRaisesRegex(UIError, '^ui_failed$'):
            ui.cancelled()
        self.assertEqual(self.progress.closed, 1)
        ui = self.make()
        self.dialog.answer = 'private-value'
        with self.assertRaisesRegex(UIError, '^ui_failed$'):
            ui.confirm_disconnect()

    def test_duplicate_display_cannot_replace_or_leak_an_existing_prompt(self):
        ui = self.make()
        ui.show_code('FIRST', 'https://trakt.tv/activate')
        with self.assertRaisesRegex(UIError, '^ui_failed$'):
            ui.show_code('SECOND', 'https://trakt.tv/activate')
        self.assertEqual(len(self.progress.messages), 1)
        self.assertEqual(self.progress.closed, 1)
        self.assertEqual(self.creations, 1)
