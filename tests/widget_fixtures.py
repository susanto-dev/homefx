"""Synthetic widget fixtures shared by directory and picker tests.

This module contains no discovered test cases and performs no service traffic.
"""
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addons/plugin.video.homefx'))
from resources.lib.trakt_auth import TokenSet
from resources.lib.trakt_client import Response
from resources.lib.trakt_library import Library
from resources.lib.trakt_preferences import AccountPreferences
from resources.lib.trakt_session import Session
from resources.lib.trakt_tokens import TokenStore
from resources.lib.trakt_widget_ui import WidgetDirectoryUI
from resources.lib import trakt_widget_routes as routes


class Tag:
    def __init__(self):
        self.values = {}

    def setTitle(self, value): self.values['title'] = value
    def setMediaType(self, value): self.values['type'] = value
    def setYear(self, value): self.values['year'] = value
    def setPlaycount(self, value): self.values['playcount'] = value
    def setPlot(self, value): self.values['plot'] = value
    def setRating(self, rating, votes, source, default):
        self.values['rating'] = (rating, votes, source, default)

    def setUniqueIDs(self, values, default): self.values['ids'] = (values, default)
    def setTvShowTitle(self, value): self.values['show_title'] = value

    def setSeason(self, value): self.values['season'] = value
    def setEpisode(self, value): self.values['episode'] = value


class Item:
    def __init__(self, label):
        self.label, self.tag, self.actions, self.art = label, Tag(), [], {}

    def setArt(self, art): self.art = art
    def getVideoInfoTag(self): return self.tag
    def addContextMenuItems(self, actions): self.actions.extend(actions)


class WidgetDirectoryFixture:
    """Shared setup and Kodi doubles; inherit before unittest.TestCase."""
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.profile = temporary.name
        self.store = TokenStore(self.profile)
        self.store.install(TokenSet('synthetic-a', 'synthetic-refresh', 10000))
        self.preferences = AccountPreferences(self.profile)
        self.calls, self.rows, self.ends, self.events, self.categories = [], [], [], [], []
        self.abort, self.progress_cancel, self.submission = False, False, True
        self.details = []
        self.on_item = lambda: None
        self.on_close = lambda: None
        self.on_add = lambda: None
        self.on_abort_probe = lambda: None
        self.intercept = lambda path: None
        self.items = [{'type': 'movie', 'movie': {'ids': {'trakt': 10}, 'title': '[B]Synthetic movie[/B]'}},
                      {'type': 'show', 'show': {'ids': {'trakt': 20}, 'title': 'Synthetic show'}}]
        self.library = self.reopen()
        self.library.select_lists(['trakt-list:1'])
        self.calls.clear()
        self.ui = WidgetDirectoryUI(self, self.item, lambda: self, self, dialog=self, art_root="/synthetic/art/")

    def reopen(self):
        def api(method, path, headers, body=None):
            self.assertEqual(method, 'GET')
            self.assertIsNone(body)
            self.calls.append(path)
            response = self.intercept(path)
            if response is not None:
                return response
            if path == '/users/settings':
                account = 'b' if headers['Authorization'].endswith('synthetic-b') else 'a'
                return Response(200, body={'user': {'ids': {'uuid': 'synthetic-' + account}}})
            if path.startswith('/users/me/lists?'):
                return Response(200, body=[{'ids': {'trakt': 1}, 'name': '[B]Synthetic list[/B]'}])
            if path.startswith('/users/likes/lists?'):
                return Response(200, body=[])
            return Response(200, body=self.items)

        def no_auth(*args):
            raise AssertionError('No authentication expected')
        return Library(Session(TokenStore(self.profile), no_auth, api, 'synthetic-client',
                       'https://example.invalid/callback', clock=lambda: 1000),
                       preferences=AccountPreferences(self.profile))

    def item(self, label):
        self.on_item()
        return Item(label)

    def abortRequested(self):
        self.on_abort_probe()
        return self.abort
    def iscanceled(self): return self.progress_cancel
    def create(self, title, message): self.events.append(('loading', message))
    def update(self, percent): self.events.append(('update', percent))
    def close(self):
        self.events.append(('close',))
        self.on_close()

    def textviewer(self, title, text): self.details.append((title, text))

    def setPluginCategory(self, handle, category): self.categories.append(category)
    def setContent(self, handle, content): self.assertEqual(content, 'videos')
    def addDirectoryItems(self, handle, items, totalItems):
        self.assertEqual(totalItems, len(items))
        self.rows.extend(items)
        self.on_add()
        return self.submission

    def endOfDirectory(self, handle, succeeded, cacheToDisc):
        self.ends.append((succeeded, cacheToDisc))

    def render(self, target, widget=False):
        self.rows, self.ends = [], []
        return self.ui.render(self.library, 1, urlsplit(target).query, widget=widget)

    def source(self):
        return routes.url('trakt_list', ref=self.library.widget_sources()['items'][0]['ref'])

