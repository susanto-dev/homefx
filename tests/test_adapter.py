"""Exercise adapter wiring without claiming a Kodi runtime integration test."""
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / 'addons/plugin.video.homefx'
sys.path.insert(0, str(ADDON))
from resources.lib import routes, state


class Tag:
    def __init__(self):
        self.values = {}

    def setTitle(self, value): self.values['title'] = value
    def setMediaType(self, value): self.values['type'] = value
    def setPlot(self, value): self.values['plot'] = value
    def setPremiered(self, value): self.values['premiered'] = value
    def setPlaycount(self, value): self.values['playcount'] = value
    def setResumePoint(self, time, total): self.values['resume'] = (time, total)
    def setSeason(self, value): self.values['season'] = value
    def setEpisode(self, value): self.values['episode'] = value
    def setTvShowTitle(self, value): self.values['show'] = value


class ListItem:
    def __init__(self, label):
        self.label = label
        self.tag = Tag()
        self.art = {}
        self.menu = []

    def setArt(self, art): self.art = art
    def getVideoInfoTag(self): return self.tag
    def addContextMenuItems(self, actions): self.menu = actions


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.rows, self.ends, self.messages, self.commands = [], [], [], []
        self.content = []
        self.selection = [0, 2]
        self.answer = 'Lantern'
        self.last_default = None
        self.choices = []
        self.confirm = True
        owner = self

        class Addon:
            def getAddonInfo(self, key):
                return {'profile': owner.temp.name, 'path': str(ADDON)}[key]

        class Dialog:
            def ok(self, title, text): owner.messages.append(text)
            def notification(self, title, text): owner.messages.append(text)
            def yesno(self, title, text): return owner.confirm
            def multiselect(self, title, labels, preselect): return owner.selection
            def select(self, title, choices):
                owner.choices = choices
                return -1
            def input(self, title, defaultt):
                owner.last_default = defaultt
                return owner.answer

        self.modules = {
            'xbmcaddon': types.SimpleNamespace(Addon=Addon),
            'xbmcgui': types.SimpleNamespace(Dialog=Dialog, ListItem=ListItem),
            'xbmc': types.SimpleNamespace(executebuiltin=self.commands.append),
            'xbmcvfs': types.SimpleNamespace(translatePath=lambda path: path),
            'xbmcplugin': types.SimpleNamespace(
                addDirectoryItem=lambda handle, url, li, folder: self.rows.append((url, li, folder)),
                endOfDirectory=lambda handle, **kw: self.ends.append(kw),
                setPluginCategory=lambda *args: None,
                setContent=lambda handle, kind: self.content.append(kind),
                addSortMethod=lambda *args: None, SORT_METHOD_NONE=0)}

    def run_route(self, route='home', **params):
        self.rows.clear()
        self.ends.clear()
        with patch.dict(sys.modules, self.modules), patch.object(
                sys, 'argv', [routes.BASE, '1', '?' + urlsplit(routes.url(route, **params)).query]):
            spec = importlib.util.spec_from_file_location('preview', ADDON / 'default.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.main()

    def test_root_selection_and_folder_routes(self):
        self.run_route('select')
        self.run_route()
        self.assertEqual([li.label for _, li, _ in self.rows[:2]],
                         ['Weekend movies (demo)', 'My series (demo)'])
        self.assertEqual(self.ends, [{'succeeded': True, 'cacheToDisc': False}])
        self.assertTrue(self.rows[0][2])

    def test_movie_metadata_actions_and_non_playback_click(self):
        self.run_route('list', id='weekend')
        self.assertEqual(len(self.rows), 4)
        url, li, folder = self.rows[0]
        self.assertFalse(folder)
        self.assertEqual(li.tag.values['type'], 'movie')
        self.assertEqual(li.tag.values['resume'], (2520, 6000))
        self.assertIn('Similar movies (demo)', [label for label, _ in li.menu])
        self.assertTrue(all(Path(path).is_file() for path in li.art.values()))
        route, params = routes.parse(urlsplit(url).query)
        self.run_route(route, **params)
        self.assertIn('no playback', self.messages[-1])
        self.assertEqual(self.commands, [])

    def test_episode_watched_action_refreshes_and_clears_demo_resume(self):
        self.run_route('watched', id='e2', value='1')
        self.assertEqual(self.commands, ['Container.Refresh'])
        self.run_route('next')
        self.assertEqual(self.rows[0][1].tag.values['episode'], 4)
        self.run_route('show', id='s1')
        tag = self.rows[1][1].tag.values
        self.assertEqual(tag['playcount'], 1)
        self.assertNotIn('resume', tag)

    def test_prefilled_editable_search_and_empty_cancel(self):
        self.run_route('search', q='The Lantern Harbour')
        self.assertEqual(self.last_default, 'The Lantern Harbour')
        self.assertEqual(len(self.rows), 1)
        self.answer = ''
        self.run_route('search')
        self.assertEqual(self.rows, [])
        self.assertTrue(self.ends[0]['succeeded'])

    def test_continuation_choices_do_not_execute_playback(self):
        self.run_route('sequence', id='e2')
        self.assertEqual(self.choices, ['Replay: The Familiar Path',
                         'Next aired unwatched: An Unopened Letter', 'Stop'])
        self.assertEqual(self.commands, [])

    def test_bad_id_and_bad_watch_value_do_not_modify_state(self):
        self.run_route('watched', id='unknown', value='1')
        self.assertFalse(self.ends[0]['succeeded'])
        self.run_route('watched', id='m1', value='yes')
        self.assertEqual(state.load(Path(self.temp.name) / 'demo.json')['watched'], {})
        self.assertEqual(self.commands, [])

    def test_reset_and_cancel_selection(self):
        self.run_route('watched', id='m1', value='1')
        self.run_route('reset')
        self.assertEqual(state.load(Path(self.temp.name) / 'demo.json')['watched'], {})
        self.selection = None
        self.commands.clear()
        self.run_route('select')
        self.assertEqual(self.commands, [])

    def test_setup_is_information_only_without_network_or_token_storage(self):
        with patch('socket.create_connection', side_effect=AssertionError('Unexpected network')):
            self.run_route('setup')
        self.assertIn('not enabled', self.messages[-1])
        self.assertIn('Never enter or share a client secret', self.messages[-1])
        self.assertFalse((Path(self.temp.name) / 'trakt').exists())
        self.assertEqual(self.commands, [])

    def test_upcoming_movie_collection_is_persistent_and_idempotent(self):
        self.run_route('list', id='weekend')
        upcoming = next(li for _, li, _ in self.rows if li.tag.values['title'] == "Tomorrow's Orchard")
        menu = dict(upcoming.menu)
        self.assertIn('Add to my movie list (demo)', menu)
        self.assertIn('Open my movie list (demo)', menu)
        self.run_route('collect', id='m3', value='1')
        self.run_route('collect', id='m3', value='1')
        self.assertEqual(state.load(Path(self.temp.name) / 'demo.json')['saved_movies'], ['m3'])
        self.run_route('list', id='saved')
        self.assertEqual(len(self.rows), 1)
        self.assertIn('Upcoming', self.rows[0][1].label)
        self.assertIn('Remove from my movie list (demo)', dict(self.rows[0][1].menu))
        self.assertEqual(self.rows[0][1].tag.values['type'], 'movie')
        self.assertTrue(all(command == 'Container.Refresh' for command in self.commands))
        self.assertIn('Trakt is not connected', self.messages[-1])

    def test_cancelled_collection_removal_and_invalid_actions_preserve_state(self):
        self.run_route('collect', id='m3', value='1')
        path = Path(self.temp.name) / 'demo.json'
        before = path.read_bytes()
        self.commands.clear()
        self.confirm = False
        self.run_route('collect', id='m3', value='0')
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.commands, [])
        for ident, value in [('e2', '1'), ('unknown', '1'), ('m3', 'anything')]:
            self.run_route('collect', id=ident, value=value)
            self.assertFalse(self.ends[-1]['succeeded'])
            self.assertEqual(path.read_bytes(), before)
        self.confirm = True
        self.run_route('collect', id='m3', value='0')
        self.run_route('collect', id='m3', value='0')
        self.assertEqual(state.load(path)['saved_movies'], [])

    def test_episode_filter_context_and_all_episode_fallback(self):
        self.run_route('list', id='series')
        menu = dict(self.rows[0][1].menu)
        self.assertIn('filter=aired_unwatched', menu['Browse aired unwatched episodes (demo)'])
        self.run_route('show', id='s1', filter='aired_unwatched')
        self.assertEqual([li.tag.values['episode'] for _, li, _ in self.rows], [2, 4])
        self.assertIn('resume', self.rows[0][1].tag.values)
        self.assertIn('filter=all', dict(self.rows[0][1].menu)['Browse all episodes (demo)'])
        self.run_route('watched', id='e2', value='1')
        self.run_route('show', id='s1', filter='aired_unwatched')
        self.assertEqual([li.tag.values['episode'] for _, li, _ in self.rows], [4])
        self.run_route('show', id='s1', filter='all')
        self.assertEqual([li.tag.values['episode'] for _, li, _ in self.rows], [1, 2, 3, 4, 5, 6])
        self.run_route('show', id='s1', filter='invalid')
        self.assertFalse(self.ends[-1]['succeeded'])

    def test_collection_selection_and_reset_preserve_expected_preferences(self):
        self.run_route('collect', id='m3', value='1')
        self.selection = [3]
        self.run_route('select')
        self.run_route()
        self.assertEqual(self.rows[0][1].label, 'My movie list (demo)')
        self.assertIn('id=saved', self.rows[0][0])
        self.run_route('reset')
        restored = state.load(Path(self.temp.name) / 'demo.json')
        self.assertEqual(restored['saved_movies'], [])
        self.assertEqual(restored['watched'], {})
