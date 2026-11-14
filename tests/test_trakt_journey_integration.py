"""Factory-to-UI journeys over fabricated HTTPS framing; no real service traffic."""
import http.client
import json
from pathlib import Path
import ssl
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib import service_runtime as runtime
from resources.lib import trakt_widget_routes as routes
from resources.lib.account_flow import AccountFlow, FlowResult
from resources.lib.account_ui import AccountUI
from resources.lib.trakt_list_ui import TraktListUI
from resources.lib.trakt_widget_ui import WidgetDirectoryUI
from test_trakt_transport import MemorySocket, wire
from widget_fixtures import Item


class FramedService:
    """Only the HTTPS connection seam is replaced; actual HTTP parsing is retained."""
    def __init__(self, test):
        self.test = test
        self.elapsed = 0.0
        self.account, self.serial = 'a', 0
        self.requests, self.sockets = [], []
        self.tokens, self.refresh_tokens = {}, {}
        self.hook = lambda host, method, path: None
        self.poll_status = 200
        self.cancel_on_read = None
        self.empty = False

    def wall(self):
        return 1000 + self.elapsed

    def __call__(self, host, **kwargs):
        self.test.assertIn(host, ('auth.trakt.tv', 'api.trakt.tv'))
        self.test.assertEqual(kwargs['port'], 443)
        self.test.assertEqual(kwargs['context'].verify_mode, ssl.CERT_REQUIRED)
        self.test.assertTrue(kwargs['context'].check_hostname)
        service = self
        def read_tick():
            if service.cancel_on_read is not None:
                callback, service.cancel_on_read = service.cancel_on_read, None
                callback()
        memory = MemorySocket(b'', tick=read_tick)
        self.sockets.append(memory)

        class Connection(http.client.HTTPSConnection):
            def connect(self):
                self.sock = memory

            def request(self, method, path, body=None, headers=None, **options):
                data = json.loads(body) if body is not None else None
                service.requests.append((host, method, path, data))
                override = service.hook(host, method, path)
                status, response = override if override is not None else service.respond(host, method, path, data, headers)
                memory.wire = wire(json.dumps(response).encode('utf-8'), status=status)
                return super().request(method, path, body=body, headers=headers, **options)
        return Connection(host, **kwargs)

    def respond(self, host, method, path, body, headers):
        self.test.assertEqual(headers['User-Agent'], 'HomeFX (+https://github.com/susanto-dev/homefx)')
        self.test.assertEqual(headers['trakt-api-version'], '2')
        self.test.assertEqual(headers['Content-Type'], 'application/json')
        if host == 'auth.trakt.tv':
            self.test.assertEqual(headers['trakt-api-key'], body['client_id'])
            self.test.assertNotIn('Authorization', headers)
            self.test.assertEqual(method, 'POST')
            self.test.assertNotIn('client_secret', body)
            if path == '/oauth/device/code':
                self.test.assertEqual(body, {'client_id': 'synthetic-public'})
                return 200, {'device_code': 'synthetic-device-code', 'user_code': 'SYNTHETIC-CODE',
                             'verification_url': 'https://trakt.tv/activate', 'interval': 5, 'expires_in': 600}
            self.test.assertIn(path, ('/oauth/device/token', '/oauth/token'))
            account = self.account
            if path == '/oauth/device/token':
                self.test.assertEqual(body, {'client_id': 'synthetic-public', 'code': 'synthetic-device-code'})
                if self.poll_status != 200:
                    return self.poll_status, {}
            if path == '/oauth/token':
                self.test.assertEqual(set(body), {'client_id', 'redirect_uri', 'grant_type', 'refresh_token'})
                self.test.assertEqual(body['client_id'], 'synthetic-public')
                self.test.assertEqual(body['redirect_uri'], 'urn:homefx:synthetic')
                self.test.assertEqual(body['grant_type'], 'refresh_token')
                self.test.assertIn(body['refresh_token'], self.refresh_tokens)
                account = self.refresh_tokens.pop(body['refresh_token'])
            self.serial += 1
            access, refresh = 'synthetic-access-' + str(self.serial), 'synthetic-refresh-' + str(self.serial)
            self.tokens[access], self.refresh_tokens[refresh] = account, account
            return 200, {'access_token': access, 'refresh_token': refresh,
                         'token_type': 'bearer', 'created_at': self.wall(), 'expires_in': 3600}
        self.test.assertEqual(method, 'GET')
        self.test.assertIsNone(body)
        self.test.assertEqual(headers['trakt-api-key'], 'synthetic-public')
        self.test.assertTrue(headers['Authorization'].startswith('Bearer '))
        account = self.tokens[headers['Authorization'][7:]]
        if path == '/users/settings':
            return 200, {'user': {'ids': {'uuid': 'synthetic-account-' + account}}}
        if path.startswith('/users/me/lists?'):
            return 200, [{'ids': {'trakt': 1}, 'name': 'Synthetic personal ' + account}]
        if path.startswith('/users/likes/lists?'):
            return 200, [{'list': {'ids': {'trakt': 2}, 'name': 'Synthetic liked ' + account,
                                  'user': {'ids': {'slug': 'synthetic-owner'}}}}]
        if path.startswith(('/users/me/lists/1/items?', '/users/synthetic-owner/lists/2/items?')):
            return 200, [] if self.empty else [
                {'type': 'movie', 'movie': {'ids': {'trakt': 10}, 'title': 'Synthetic movie'}},
                {'type': 'show', 'show': {'ids': {'trakt': 20}, 'title': 'Synthetic show'}}]
        if path == '/shows/20/seasons?extended=full':
            return 200, [{'number': 1, 'ids': {'trakt': 201}, 'episode_count': 1}]
        if path == '/shows/20/seasons/1?extended=full':
            return 200, [{'season': 1, 'number': 1, 'ids': {'trakt': 21},
                          'title': 'Synthetic episode', 'first_aired': '2020-01-01T00:00:00Z'}]
        if path == '/shows/20/progress/watched?hidden=false&specials=false':
            return 200, {'seasons': [{'number': 1, 'episodes': [{'number': 1, 'completed': False}]}]}
        if path.startswith('/sync/playback?'):
            return 200, []
        self.test.fail('Unexpected read endpoint')


class Screen:
    def __init__(self, service):
        self.service = service
        self.abort, self.cancel = False, False
        self.answer, self.confirm = [0, 1], True
        self.events, self.rows, self.ends, self.details = [], [], [], []
        self.on_select = lambda: None
        self.on_wait = lambda: None
        self.on_item = lambda: None
        self.on_close = lambda: None

    def abortRequested(self): return self.abort
    def iscanceled(self): return self.cancel
    def waitForAbort(self, seconds):
        self.service.elapsed += seconds
        self.on_wait()
        return self.abort
    def create(self, title, text): self.events.append(('open', title, text))
    def update(self, percent): self.events.append(('update', percent))
    def close(self):
        self.events.append(('close',))
        self.on_close()
    def yesno(self, title, text):
        self.events.append(('confirm', title, text))
        return self.confirm
    def multiselect(self, title, labels, preselect):
        self.events.append(('select', tuple(preselect)))
        self.on_select()
        return self.answer
    def textviewer(self, title, text): self.details.append((title, text))
    def item(self, label):
        self.on_item()
        return Item(label)
    def setPluginCategory(self, handle, category): self.events.append(('category', category))
    def setContent(self, handle, content): self.events.append(('content', content))
    def addDirectoryItems(self, handle, items, totalItems):
        self.rows.extend(items)
        return totalItems == len(items)
    def endOfDirectory(self, handle, succeeded, cacheToDisc): self.ends.append((succeeded, cacheToDisc))


class Invocation:
    """Test fixture wires the actual existing UI adapters to one factory boundary."""
    def __init__(self, profile, service):
        self.screen = Screen(service)
        self.account_ui = AccountUI('trakt', self.screen, lambda: self.screen, self.screen)
        self.list_ui = TraktListUI(self.screen, lambda: self.screen, self.screen)
        self.widget_ui = WidgetDirectoryUI(self.screen, self.screen.item, lambda: self.screen,
                                           self.screen, dialog=self.screen, art_root='/synthetic/art/')
        self.active = self.account_ui
        self.bundle = runtime.build_trakt(profile, 'synthetic-public', 'urn:homefx:synthetic',
            clock=service.wall, monotonic=lambda: service.elapsed,
            cancelled=lambda: self.active.cancelled(), connection_factory=service)
        self.flow = AccountFlow(self.bundle.session, self.account_ui, self.account_ui.wait,
            self.account_ui.cancelled, lambda: service.elapsed, self.bundle.disconnect)

    def connect(self):
        self.active = self.account_ui
        return self.flow.connect()

    def choose(self):
        self.active = self.list_ui
        return self.list_ui.choose(self.bundle.library)

    def render(self, target, widget=False):
        self.active = self.widget_ui
        self.screen.rows, self.screen.ends = [], []
        return self.widget_ui.render(self.bundle.library, 1, urlsplit(target).query, widget=widget)

    def disconnect(self):
        self.active = self.account_ui
        return self.flow.disconnect()


class TraktJourneyIntegrationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.profile = Path(directory.name) / 'private'
        self.network_attempts = []
        for target in ('socket.create_connection', 'socket.getaddrinfo'):
            blocker = patch(target, side_effect=AssertionError('Unexpected real networking'))
            self.network_attempts.append(blocker.start())
            self.addCleanup(blocker.stop)
        self.service = FramedService(self)
        self.app = Invocation(self.profile, self.service)

    def tearDown(self):
        for attempt in self.network_attempts:
            attempt.assert_not_called()
        self.assertTrue(all(sock.closed for sock in self.service.sockets))
        self.assertTrue(all(method == 'GET' if host == 'api.trakt.tv' else
                            method == 'POST' and path in {'/oauth/device/code', '/oauth/device/token', '/oauth/token'}
                            for host, method, path, _ in self.service.requests))

    def ready(self):
        self.assertEqual(self.app.connect(), FlowResult.AUTHORIZED)
        self.assertEqual(self.app.choose().state, 'saved')
        self.assertEqual(self.app.render(routes.url('trakt_sources')).state, 'ready')
        return [row[0] for row in self.app.screen.rows]

    def test_complete_factory_login_selection_navigation_and_restart(self):
        self.assertEqual(self.service.requests, [])
        self.assertEqual(self.app.screen.events, [])
        targets = self.ready()
        self.assertEqual(len(targets), 2)
        self.assertEqual([request[:3] for request in self.service.requests[:2]], [
            ('auth.trakt.tv', 'POST', '/oauth/device/code'), ('auth.trakt.tv', 'POST', '/oauth/device/token')])
        code_events = [event for event in self.app.screen.events if 'SYNTHETIC-CODE' in str(event)]
        self.assertEqual(len(code_events), 1)
        self.assertTrue(all('synthetic' not in target and 'trakt-list' not in target for target in targets))
        self.assertEqual(self.app.render(targets[1], widget=True).state, 'ready')
        movie, show = [row[0] for row in self.app.screen.rows]
        self.assertEqual(self.app.render(movie).state, 'ready')
        self.assertIn('No playable source', self.app.screen.details[-1][1])
        self.assertEqual(self.app.render(show).state, 'ready')
        season = self.app.screen.rows[0][0]
        self.assertEqual(self.app.render(season).state, 'ready')
        episode = self.app.screen.rows[0][0]
        self.assertEqual(self.app.render(episode).state, 'ready')
        self.assertIn('unwatched', self.app.screen.details[-1][1])
        before = len(self.service.requests)
        fresh = Invocation(self.profile, self.service)
        self.assertEqual(len(self.service.requests), before)
        self.assertEqual(fresh.render(routes.url('trakt_sources'), widget=True).state, 'ready')
        self.assertEqual([row[0] for row in fresh.screen.rows], targets)
        self.assertEqual(fresh.render(targets[1], widget=True).state, 'ready')
        self.assertEqual(fresh.screen.ends, [(True, False)])
        self.assertEqual(fresh.screen.details, [])
        self.assertFalse(any(event[0] == 'open' for event in fresh.screen.events))

    def test_refresh_rotation_keeps_opaque_routes_and_registered_redirect(self):
        targets = self.ready()
        generation = self.app.bundle.session.status()['generation']
        self.service.elapsed += 3600
        fresh = Invocation(self.profile, self.service)
        self.assertEqual(fresh.render(targets[0], widget=True).state, 'ready')
        self.assertEqual(fresh.bundle.session.status()['generation'], generation + 1)
        refresh = [request for request in self.service.requests if request[2] == '/oauth/token']
        self.assertEqual(len(refresh), 1)
        self.assertEqual(refresh[0][3]['redirect_uri'], 'urn:homefx:synthetic')
        self.assertNotIn('client_secret', refresh[0][3])
        self.assertEqual(fresh.render(routes.url('trakt_sources'), widget=True).state, 'ready')
        self.assertEqual([row[0] for row in fresh.screen.rows], targets)

    def test_disconnect_invalidates_old_routes_after_same_account_reconnects(self):
        targets = self.ready()
        self.assertEqual(self.app.disconnect(), FlowResult.DISCONNECTED)
        fresh = Invocation(self.profile, self.service)
        self.assertEqual(fresh.render(targets[0], widget=True).state, 'authorization_needed')
        self.assertEqual(fresh.connect(), FlowResult.AUTHORIZED)
        self.assertEqual(fresh.choose().state, 'saved')
        self.assertEqual(fresh.render(targets[0], widget=True).state, 'unavailable')
        self.assertEqual(fresh.screen.rows, [])
        self.assertEqual(fresh.render(routes.url('trakt_sources'), widget=True).state, 'ready')
        self.assertNotEqual([row[0] for row in fresh.screen.rows], targets)

    def test_cancel_during_login_wait_closes_prompt_without_poll_or_account(self):
        self.app.screen.on_wait = lambda: setattr(self.app.screen, 'cancel', True)
        self.assertEqual(self.app.connect(), FlowResult.CANCELLED)
        self.assertEqual([request[2] for request in self.service.requests], ['/oauth/device/code'])
        self.assertEqual(self.app.bundle.session.status()['state'], 'disconnected')
        self.assertEqual(self.app.screen.events[-1], ('close',))

    def test_denied_device_grant_does_not_become_authorized_or_open_lists(self):
        self.service.poll_status = 418
        self.assertEqual(self.app.connect(), FlowResult.DENIED)
        self.assertEqual(self.app.bundle.session.status()['state'], 'disconnected')
        self.assertEqual(len(self.service.requests), 2)
        self.assertEqual(self.app.render(routes.url('trakt_sources'), widget=True).state, 'authorization_needed')
        self.assertEqual(len(self.service.requests), 2)

    def test_cancellation_during_real_transport_read_preserves_choices(self):
        targets = self.ready()
        fresh = Invocation(self.profile, self.service)
        self.service.cancel_on_read = lambda: setattr(fresh.screen, 'cancel', True)
        result = fresh.render(targets[0])
        self.assertEqual(result.state, 'cancelled')
        self.assertEqual(fresh.screen.rows, [])
        self.assertEqual(fresh.screen.ends, [(False, False)])
        later = Invocation(self.profile, self.service)
        self.assertEqual(later.render(routes.url('trakt_sources'), widget=True).state, 'ready')
        self.assertEqual([row[0] for row in later.screen.rows], targets)

    def test_cancel_during_item_staging_discards_rows_before_bulk_submission(self):
        targets = self.ready()
        fresh = Invocation(self.profile, self.service)
        fresh.screen.on_item = lambda: setattr(fresh.screen, 'cancel', True)
        result = fresh.render(targets[0])
        self.assertEqual(result.state, 'cancelled')
        self.assertEqual(fresh.screen.rows, [])
        self.assertEqual(fresh.screen.ends, [(False, False)])
        self.assertEqual(fresh.screen.details, [])

    def test_cancel_during_explicit_details_read_does_not_open_failure_dialog(self):
        targets = self.ready()
        self.assertEqual(self.app.render(targets[0], widget=True).state, 'ready')
        movie = self.app.screen.rows[0][0]
        fresh = Invocation(self.profile, self.service)
        self.service.cancel_on_read = lambda: setattr(fresh.screen, 'cancel', True)
        result = fresh.render(movie)
        self.assertEqual(result.state, 'cancelled')
        self.assertEqual(fresh.screen.rows, [])
        self.assertEqual(fresh.screen.details, [])
        self.assertEqual(fresh.screen.ends, [])

    def test_cancel_with_cleanup_failure_is_not_reported_as_clean_cancellation(self):
        targets = self.ready()
        fresh = Invocation(self.profile, self.service)
        fresh.screen.on_item = lambda: setattr(fresh.screen, 'cancel', True)
        def failed_close():
            fresh.screen.abort = True
            raise RuntimeError('synthetic-private-cleanup-detail')
        fresh.screen.on_close = failed_close
        result = fresh.render(targets[0])
        self.assertEqual(result.state, 'failed')
        self.assertNotIn('synthetic-private', result.message)
        self.assertEqual(fresh.screen.rows, [])
        self.assertEqual(fresh.screen.ends, [(False, False)])

    def test_cancel_list_dialog_retains_both_choices_after_reassembly(self):
        targets = self.ready()
        self.app.screen.answer = None
        self.assertEqual(self.app.choose().state, 'cancelled')
        fresh = Invocation(self.profile, self.service)
        self.assertEqual(fresh.render(routes.url('trakt_sources'), widget=True).state, 'ready')
        self.assertEqual([row[0] for row in fresh.screen.rows], targets)

    def test_401_clears_session_and_is_not_an_empty_list_or_login_popup(self):
        targets = self.ready()
        fresh = Invocation(self.profile, self.service)
        self.service.hook = lambda host, method, path: (401, {'private': 'synthetic-private'})
        result = fresh.render(targets[0], widget=True)
        self.assertEqual(result.state, 'authorization_needed')
        self.assertEqual(fresh.screen.rows, [])
        self.assertEqual(fresh.bundle.session.status()['state'], 'disconnected')
        self.assertFalse(any(event[0] == 'open' for event in fresh.screen.events))
        self.assertNotIn('synthetic-private', result.message)

    def test_offline_and_successful_empty_list_are_distinct(self):
        targets = self.ready()
        fresh = Invocation(self.profile, self.service)
        def offline(host, method, path):
            raise OSError('synthetic-private-network-detail')
        self.service.hook = offline
        result = fresh.render(targets[0], widget=True)
        self.assertEqual(result.state, 'offline')
        self.assertNotIn('synthetic-private', result.message)
        self.assertEqual(fresh.screen.rows, [])
        self.service.hook = lambda *args: None
        self.service.empty = True
        later = Invocation(self.profile, self.service)
        self.assertEqual(later.render(targets[0], widget=True).state, 'empty')
        self.assertEqual(later.screen.ends, [(True, False)])

    def test_account_replacement_during_chooser_cannot_save_into_new_account(self):
        targets = self.ready()
        other = Invocation(self.profile, self.service)
        def replace():
            self.service.account = 'b'
            self.assertEqual(other.connect(), FlowResult.AUTHORIZED)
        self.app.screen.on_select = replace
        self.app.screen.answer = [0]
        self.assertEqual(self.app.choose().state, 'changed')
        self.assertEqual(other.render(routes.url('trakt_sources'), widget=True).state, 'empty')
        self.assertEqual(other.render(targets[0], widget=True).state, 'unavailable')
        self.assertEqual(other.screen.rows, [])

    def test_rate_limit_survives_reassembly_without_repeating_network_request(self):
        targets = self.ready()
        self.service.hook = lambda *args: (429, {})
        first = Invocation(self.profile, self.service)
        self.assertEqual(first.render(targets[0], widget=True).state, 'limited')
        count = len(self.service.requests)
        self.service.hook = lambda *args: None
        second = Invocation(self.profile, self.service)
        self.assertEqual(second.render(targets[0], widget=True).state, 'limited')
        self.assertEqual(len(self.service.requests), count)
        self.assertEqual(second.screen.rows, [])
        self.service.elapsed += 61
        later = Invocation(self.profile, self.service)
        self.assertEqual(later.render(targets[0], widget=True).state, 'ready')

    def test_declined_replacement_keeps_account_choices_and_bound_widget_route(self):
        targets = self.ready()
        before = len(self.service.requests)
        self.app.screen.confirm = False
        self.assertEqual(self.app.connect(), FlowResult.CANCELLED)
        self.assertEqual(len(self.service.requests), before)
        fresh = Invocation(self.profile, self.service)
        self.assertEqual(fresh.render(routes.url('trakt_sources'), widget=True).state, 'ready')
        self.assertEqual([row[0] for row in fresh.screen.rows], targets)
        self.assertEqual(fresh.render(targets[0], widget=True).state, 'ready')

    def test_refresh_transport_failure_requires_login_without_replaying_refresh(self):
        targets = self.ready()
        self.service.elapsed += 3600
        fresh = Invocation(self.profile, self.service)
        def interrupt_refresh(host, method, path):
            if path == '/oauth/token':
                raise OSError('synthetic-lost-refresh-response')
            return None
        self.service.hook = interrupt_refresh
        first = fresh.render(targets[0], widget=True)
        self.assertNotIn(first.state, {'ready', 'empty'})
        self.assertEqual(fresh.render(targets[0], widget=True).state, 'authorization_needed')
        self.assertEqual(sum(request[2] == '/oauth/token' for request in self.service.requests), 1)
        self.assertEqual(fresh.screen.rows, [])
