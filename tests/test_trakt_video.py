"""Joined video entry acceptance over synthetic HTTP; no real provider traffic."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.trakt_video import TraktVideo
from resources.lib.account_flow import FlowResult
from resources.lib import service_runtime, trakt_widget_routes as routes
from test_trakt_journey_integration import FramedService, Screen


class TraktVideoTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.profile = Path(directory.name) / 'video-private'
        self.service = FramedService(self)
        self.calls = []
        for name in ('socket.create_connection', 'socket.getaddrinfo'):
            blocker = patch(name, side_effect=AssertionError('Real network forbidden'))
            mock = blocker.start()
            self.addCleanup(blocker.stop)
            self.addCleanup(mock.assert_not_called)

    def app(self, factory=None):
        screen = Screen(self.service)
        def assemble(*, cancelled):
            self.calls.append(cancelled)
            return service_runtime.build_trakt(self.profile, 'synthetic-public',
                'urn:homefx:synthetic', clock=self.service.wall,
                monotonic=lambda: self.service.elapsed, cancelled=cancelled,
                connection_factory=self.service)
        app = TraktVideo(factory or assemble, screen, lambda: screen, screen,
                         screen, screen.item, clock=lambda: self.service.elapsed,
                         art_root='/synthetic/art/')
        return app, screen

    def browse(self, app, query, widget=False):
        return app.dispatch('browse', handle=1, query=urlsplit(query).query, widget=widget)

    def tearDown(self):
        self.assertTrue(all(sock.closed for sock in self.service.sockets))
        self.assertTrue(all(method == 'GET' if host == 'api.trakt.tv' else
            method == 'POST' and path in {'/oauth/device/code', '/oauth/device/token', '/oauth/token'}
            for host, method, path, _ in self.service.requests))

    def test_login_selection_widget_restart_and_disconnect_share_real_runtime(self):
        app, screen = self.app()
        self.assertFalse(self.profile.exists())
        self.assertEqual(app.dispatch('connect'), FlowResult.AUTHORIZED)
        self.assertEqual(app.dispatch('choose').state, 'saved')
        self.assertEqual(self.browse(app, routes.url('trakt_sources')).state, 'ready')
        targets = [row[0] for row in screen.rows]
        self.assertEqual(len(targets), 2)
        restarted, widget = self.app()
        self.assertEqual(self.browse(restarted, targets[0], widget=True).state, 'ready')
        self.assertFalse(any(event[0] in {'confirm', 'open'} for event in widget.events))
        self.assertTrue(widget.rows)
        self.assertEqual(widget.ends, [(True, False)])
        before = len(self.service.requests)
        self.assertEqual(restarted.dispatch('disconnect'), FlowResult.DISCONNECTED)
        self.assertEqual(len(self.service.requests), before)
        following, empty = self.app()
        self.assertEqual(self.browse(following, targets[0], widget=True).state, 'authorization_needed')
        self.assertEqual(empty.rows, [])
        self.assertEqual(empty.ends, [(False, False)])
        self.assertEqual(len(self.service.requests), before)
        self.assertEqual(following.dispatch('connect'), FlowResult.AUTHORIZED)
        final, sources = self.app()
        self.assertEqual(self.browse(final, routes.url('trakt_sources')).state, 'empty')
        self.assertEqual(sources.rows, [])

    def test_invalid_queries_and_widget_actions_never_construct_runtime(self):
        app, screen = self.app()
        cases = [dict(action='unknown'), dict(action='connect', widget=True),
            dict(action='choose', query='private'), dict(action='browse', handle=True, query='route=trakt_sources'),
            dict(action='browse', handle=1, query='route=trakt_list&ref=private'),
            dict(action='browse', handle=1, query='route=trakt_sources&extra=1'),
            dict(action='browse', handle=1, widget=True,
                 query='route=trakt_details&ref=' + 'a' * 64 + '&item=' + 'b' * 64)]
        for case in cases:
            self.assertEqual(app.dispatch(**case).state, 'failed')
        self.assertEqual(self.calls, [])
        self.assertTrue(all(event[0] == 'category' for event in screen.events))
        self.assertEqual(screen.ends, [(False, False)] * 3)
        self.assertFalse(self.profile.exists())

    def test_declined_consent_and_abort_leave_profile_untouched(self):
        app, screen = self.app()
        screen.confirm = False
        for action in ('connect', 'disconnect'):
            self.assertEqual(app.dispatch(action), FlowResult.CANCELLED)
        self.assertEqual(app.dispatch('choose').state, 'cancelled')
        screen.confirm = True
        screen.abort = True
        self.assertEqual(app.dispatch('connect'), FlowResult.CANCELLED)
        self.assertEqual(self.browse(app, routes.url('trakt_sources'), widget=True).state, 'cancelled')
        self.assertEqual(screen.ends, [(False, False)])
        self.assertEqual(self.calls, [])
        self.assertFalse(self.profile.exists())

    def test_cancellation_uses_active_ui_for_factory_and_controller(self):
        app, screen = self.app()
        observed = []
        def cancel():
            screen.cancel = True
            observed.append(self.calls[-1]())
        screen.on_wait = cancel
        self.assertEqual(app.dispatch('connect'), FlowResult.CANCELLED)
        self.assertEqual(len(self.service.requests), 1)
        self.assertEqual(observed, [True])
        screen.cancel = False
        self.assertEqual(app.dispatch('connect'), FlowResult.CANCELLED)
        self.assertFalse(any(host == 'api.trakt.tv' for host, _, _, _ in self.service.requests))

    def test_chooser_cancellation_reaches_transport_and_keeps_prior_choices(self):
        app, _ = self.app()
        self.assertEqual(app.dispatch('connect'), FlowResult.AUTHORIZED)
        self.assertEqual(app.dispatch('choose').state, 'saved')
        chooser, screen = self.app()
        observed = []
        def cancel_read():
            screen.cancel = True
            observed.append(self.calls[-1]())
        self.service.cancel_on_read = cancel_read
        self.assertEqual(chooser.dispatch('choose').state, 'cancelled')
        self.assertEqual(observed, [True])
        restored, sources = self.app()
        self.assertEqual(self.browse(restored, routes.url('trakt_sources')).state, 'ready')
        self.assertEqual(len(sources.rows), 2)

    def test_failed_runtime_finalizes_widget_without_dialog_or_private_error(self):
        def fail(**kwargs):
            raise ValueError('PRIVATE-TOKEN-PATH')
        app, screen = self.app(fail)
        result = self.browse(app, routes.url('trakt_sources'), widget=True)
        self.assertEqual(result.state, 'failed')
        self.assertEqual(screen.rows, [])
        self.assertEqual(screen.ends, [(False, False)])
        self.assertEqual(screen.details, [])
        self.assertFalse(any(event[0] in {'confirm', 'open'} for event in screen.events))
        self.assertNotIn('PRIVATE', repr(result) + repr(app) + str(screen.events))

    def test_cancelled_startup_cleanup_failure_is_failed_and_still_finishes(self):
        app, screen = self.app()
        screen.abort = True
        def fail(*args, **kwargs):
            raise ValueError('PRIVATE CLEANUP ERROR')
        screen.setPluginCategory = fail
        result = self.browse(app, routes.url('trakt_sources'), widget=True)
        self.assertEqual(result.state, 'failed')
        self.assertEqual(screen.ends, [(False, False)])
        self.assertEqual(self.calls, [])
        screen.endOfDirectory = fail
        self.assertEqual(self.browse(app, routes.url('trakt_sources'), widget=True).state, 'failed')
        self.assertEqual(screen.details, [])
        self.assertFalse(self.profile.exists())

    def test_empty_and_offline_reads_do_not_trigger_login_or_demo_fallback(self):
        app, _ = self.app()
        self.assertEqual(app.dispatch('connect'), FlowResult.AUTHORIZED)
        self.assertEqual(app.dispatch('choose').state, 'saved')
        sources, screen = self.app()
        self.assertEqual(self.browse(sources, routes.url('trakt_sources')).state, 'ready')
        target = screen.rows[0][0]
        self.service.empty = True
        empty, screen = self.app()
        self.assertEqual(self.browse(empty, target, widget=True).state, 'empty')
        self.assertEqual(screen.rows, [])
        def fail(host, method, path):
            raise OSError('PRIVATE ERROR')
        self.service.hook = fail
        failed, screen = self.app()
        before = len(self.service.requests)
        self.assertEqual(self.browse(failed, target, widget=True).state, 'offline')
        self.assertEqual(screen.rows, [])
        self.assertEqual(screen.ends, [(False, False)])
        self.assertTrue(all(host == 'api.trakt.tv' for host, _, _, _ in self.service.requests[before:]))


if __name__ == '__main__':
    unittest.main()
