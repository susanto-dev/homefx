"""Real Development video adapter with fabricated grants and isolated profiles."""
import hashlib
import io
import subprocess
from zipfile import ZipFile, ZIP_DEFLATED
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'addons/plugin.video.homefx'))
sys.path.insert(0, str(ROOT / 'tools'))
from resources.lib import service_runtime, trakt_widget_routes as routes
from test_trakt_journey_integration import FramedService, Screen
import build_development_test as builder
import development_download

spec = importlib.util.spec_from_file_location('resources.lib.development_video',
    ROOT / 'addons/plugin.video.homefx.development/resources/lib/development_video.py')
video = importlib.util.module_from_spec(spec)
spec.loader.exec_module(video)
CONFIG = {'schema': 1, 'environment': 'Development', 'client_id': 'synthetic-public',
          'redirect_uri': 'urn:homefx:synthetic'}
ENV = {'HOMEFX_TRAKT_ENVIRONMENT': 'Development', 'TRAKT_CLIENT_ID': CONFIG['client_id'],
       'TRAKT_REDIRECT_URI': CONFIG['redirect_uri']}


class VideoScreen(Screen):
    def addDirectoryItem(self, handle, target, item, folder):
        self.rows.append((target, item, folder))
        return True


class DevelopmentVideoTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.install = self.root / 'install'
        (self.install / 'resources').mkdir(parents=True)
        (self.install / 'resources/development.json').write_text(json.dumps(CONFIG))
        self.profile = self.root / 'profiles' / video.ADDON_ID
        self.program = self.root / 'profiles/script.homefx.development'
        self.program.mkdir(parents=True)
        (self.program / 'sentinel').write_bytes(b'synthetic unrelated profile')
        self.service = FramedService(self)
        self.factories = []
        self.paths = []
        for name in ('socket.create_connection', 'socket.getaddrinfo'):
            guard = patch(name, side_effect=AssertionError('real network forbidden'))
            mocked = guard.start()
            self.addCleanup(guard.stop)
            self.addCleanup(mocked.assert_not_called)

    def invoke(self, query='', *, confirm=True, addon_id=video.ADDON_ID, probe=None, abort_on_consent=False):
        screen = VideoScreen(self.service)
        screen.confirm = confirm
        original_confirm = screen.yesno
        def consent(title, message):
            answer = original_confirm(title, message)
            if abort_on_consent:
                screen.abort = True
            return answer
        screen.yesno = consent
        class Addon:
            def getAddonInfo(inner, key):
                return {'id': addon_id, 'path': str(self.install)}[key]
        def translate(path):
            self.paths.append(path)
            self.assertEqual(path, 'special://profile/addon_data/' + video.ADDON_ID + '/')
            return str(self.profile)
        def factory(profile, client_id, redirect_uri, *, cancelled):
            self.factories.append(profile)
            return service_runtime.build_trakt(profile, client_id, redirect_uri,
                cancelled=cancelled, clock=self.service.wall,
                monotonic=lambda: self.service.elapsed, connection_factory=self.service)
        result = video.run(['plugin://' + addon_id + '/', '1', query], Addon(), screen,
            lambda: screen, screen, screen, screen.item, translate, runtime_factory=factory,
            probe=probe or (lambda profile: 'Overall: passed'), clock=lambda: self.service.elapsed)
        return result, screen

    def test_root_invalid_and_declined_actions_have_no_storage_or_network(self):
        result, screen = self.invoke()
        self.assertTrue(result)
        self.assertEqual(len(screen.rows), 6)
        for query in ('?action=connect', '?action=choose', '?action=status', '?action=probe'):
            self.invoke(query, confirm=False)
        for query in ('?action=connect&action=choose', '?action=write', '?route=trakt_sources&private=1'):
            self.assertFalse(self.invoke(query)[0])
        self.assertFalse(self.invoke('?action=connect', addon_id='plugin.video.homefx')[0])
        self.assertFalse(self.profile.exists())
        self.assertEqual(self.factories, [])
        self.assertEqual(self.paths, [])
        self.assertEqual(self.service.requests, [])

    def test_abort_during_local_confirmation_does_not_open_storage(self):
        for action in ('probe', 'status'):
            self.assertFalse(self.invoke('?action=' + action, abort_on_consent=True)[0])
        self.assertEqual(self.paths, [])
        self.assertEqual(self.factories, [])
        self.assertFalse(self.profile.exists())

    def test_real_factory_login_choice_widget_restart_and_disconnect(self):
        _, screen = self.invoke('?action=connect')
        self.assertIn('Connection: authorized.', screen.details[-1][1])
        self.assertTrue(self.invoke('?action=choose')[0])
        success, sources = self.invoke('?route=trakt_sources')
        self.assertTrue(success)
        self.assertEqual(len(sources.rows), 2)
        source = sources.rows[0][0]
        self.assertTrue(source.startswith('plugin://' + video.ADDON_ID + '/'))
        success, listing = self.invoke('?' + urlsplit(source).query)
        self.assertTrue(success)
        self.assertTrue(listing.rows)
        self.assertFalse(any(event[0] in {'confirm', 'open'} for event in listing.events))
        for target, item, _ in listing.rows:
            self.assertTrue(target.startswith('plugin://' + video.ADDON_ID + '/'))
            self.assertTrue(item.art)
            self.assertTrue(all('plugin://plugin.video.homefx/?' not in command for _, command in item.actions))
        # Open show seasons and episodes through actual candidate-generated URLs.
        show = next(row[0] for row in listing.rows if 'trakt_seasons' in row[0])
        success, seasons = self.invoke('?' + urlsplit(show).query)
        self.assertTrue(success)
        self.assertTrue(seasons.rows)
        success, episodes = self.invoke('?' + urlsplit(seasons.rows[0][0]).query)
        self.assertTrue(success)
        self.assertTrue(episodes.rows)
        before = len(self.service.requests)
        _, disconnected = self.invoke('?action=disconnect')
        self.assertIn('Connection: disconnected.', disconnected.details[-1][1])
        self.assertEqual(len(self.service.requests), before)
        self.assertFalse(self.invoke('?' + urlsplit(source).query)[0])
        self.assertEqual(len(self.service.requests), before)
        self.assertEqual((self.program / 'sentinel').read_bytes(), b'synthetic unrelated profile')
        self.assertEqual(routes.url('trakt_sources'), 'plugin://plugin.video.homefx/?route=trakt_sources')

    def test_failed_storage_and_invalid_public_config_never_connect(self):
        _, screen = self.invoke('?action=connect', probe=lambda profile: 'Overall: not passed')
        self.assertTrue(any('Overall: not passed' in body for _, body in screen.details))
        self.assertEqual(self.factories, [])
        (self.install / 'resources/development.json').write_text(json.dumps(dict(CONFIG, environment='Production')))
        self.invoke('?action=connect')
        self.assertEqual(self.factories, [])
        self.assertEqual(self.service.requests, [])

    def test_packaged_native_entry_opens_only_own_menu_without_profile_or_network(self):
        archive = builder.build(self.root / 'native-package', ENV, video=True)
        with ZipFile(archive) as zipped:
            zipped.extractall(self.root / 'native')
        installed = self.root / 'native' / video.ADDON_ID
        child = r"""
import socket, sys, types
from pathlib import Path
root = Path(sys.argv[1])
ident = 'plugin.video.homefx.development'
rows, ends = [], []
def forbidden(*args, **kwargs): raise AssertionError('unexpected side effect')
socket.create_connection = socket.getaddrinfo = forbidden
class Addon:
    def getAddonInfo(self, key):
        assert key == 'id'
        return ident
class Item:
    def __init__(self, label): self.label = label
class Plugin:
    def setPluginCategory(self, handle, category): assert handle == 1
    def addDirectoryItem(self, handle, target, item, folder):
        rows.append((target, folder))
        return True
    def endOfDirectory(self, handle, succeeded, cacheToDisc):
        ends.append((succeeded, cacheToDisc))
sys.modules['xbmc'] = types.SimpleNamespace(Monitor=lambda: object())
sys.modules['xbmcaddon'] = types.SimpleNamespace(Addon=Addon)
sys.modules['xbmcgui'] = types.SimpleNamespace(Dialog=lambda: object(), DialogProgress=forbidden, ListItem=Item)
sys.modules['xbmcplugin'] = Plugin()
sys.modules['xbmcvfs'] = types.SimpleNamespace(translatePath=forbidden)
sys.path.insert(0, str(root))
sys.argv = ['plugin://' + ident + '/', '1', '']
exec(compile((root / 'default.py').read_bytes(), str(root / 'default.py'), 'exec'), {'__name__': '__main__'})
assert len(rows) == 6 and ends == [(True, False)]
assert all(url.startswith('plugin://' + ident + '/?') for url, _ in rows)
assert sum(folder for _, folder in rows) == 1
"""
        result = subprocess.run([sys.executable, '-c', child, str(installed)],
                                capture_output=True, timeout=15, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stdout, b'')
        self.assertFalse(self.profile.exists())

    def test_rehashed_video_config_and_entry_tampering_are_rejected(self):
        archive = builder.build(self.root / 'tamper-package', ENV, video=True)
        for filename, replacement in (
                ('resources/development.json', json.dumps(dict(CONFIG, environment='Production')).encode()),
                ('resources/development.json', json.dumps(dict(CONFIG, client_secret='synthetic-forbidden')).encode()),
                ('default.py', b'raise RuntimeError("unreviewed entry")')):
            output = io.BytesIO()
            with ZipFile(archive) as source, ZipFile(output, 'w', compression=ZIP_DEFLATED) as target:
                for entry in source.infolist():
                    value = replacement if entry.filename == video.ADDON_ID + '/' + filename else source.read(entry)
                    target.writestr(entry, value)
            raw = output.getvalue()
            digest = hashlib.sha256(raw).hexdigest()
            name = video.ADDON_ID + '-0.1.0-' + digest + '.zip'
            pair = {name: raw, name + '.sha256': (digest + '  ' + name + '\n').encode()}
            with self.assertRaises(development_download.DownloadError):
                development_download.verify(pair, video=True)

    def test_video_package_is_separate_verified_and_content_addressed(self):
        archive = builder.build(self.root / 'package', ENV, video=True)
        pair = {path.name: path.read_bytes() for path in archive.parent.iterdir()}
        self.assertEqual(development_download.verify(pair, video=True), archive.name)
        self.assertIsNone(development_download.verify(pair))
        second = builder.build(self.root / 'again', ENV, video=True)
        self.assertEqual(archive.read_bytes(), second.read_bytes())
        with self.assertRaises(builder.BuildError):
            builder.build(self.root / 'production', dict(ENV, HOMEFX_TRAKT_ENVIRONMENT='Production'), video=True)
        altered = dict(pair)
        altered[archive.name] = archive.read_bytes() + b'extra'
        with self.assertRaises(development_download.DownloadError):
            development_download.verify(altered, video=True)
