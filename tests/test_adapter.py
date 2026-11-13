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
from resources.lib import routes, state, storage_probe


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
        self.content, self.categories = [], []
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
                setPluginCategory=lambda handle, label: self.categories.append(label),
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

    def test_cancelled_directory_stops_row_preparation_without_error_dialog(self):
        for route, params, stop_after in [
                ('home', {}, 2), ('widgets', {}, 2),
                ('list', {'id': 'weekend'}, 2), ('show', {'id': 's1'}, 2),
                ('seasons', {'id': 's1'}, 1)]:
            with self.subTest(route=route):
                prepared, submitted, sorted_methods = [], [], []
                def make_item(label):
                    prepared.append(label)
                    return ListItem(label)
                def submit(handle, url, item, folder):
                    submitted.append(url)
                    return len(submitted) < stop_after
                self.modules['xbmcgui'].ListItem = make_item
                self.modules['xbmcplugin'].addDirectoryItem = submit
                self.modules['xbmcplugin'].addSortMethod = lambda *args: sorted_methods.append(args)
                self.run_route(route, **params)
                self.assertEqual(len(prepared), stop_after)
                self.assertEqual(len(submitted), stop_after)
                self.assertEqual(self.ends, [{'succeeded': False, 'cacheToDisc': False}])
                self.assertEqual((self.messages, self.commands, sorted_methods), ([], [], []))
                self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_accepted_directory_rows_finish_successfully(self):
        submitted = []
        def submit(handle, url, item, folder):
            submitted.append(url)
            return True
        self.modules['xbmcplugin'].addDirectoryItem = submit
        self.run_route('list', id='weekend')
        self.assertEqual(len(submitted), 4)
        self.assertEqual(self.ends, [{'succeeded': True, 'cacheToDisc': False}])
        self.assertEqual(self.messages, [])

    def test_storage_check_cancel_does_not_access_profile_or_probe(self):
        self.confirm = False
        self.modules['xbmcvfs'].translatePath = lambda value: self.fail('Profile translation forbidden')
        with patch.object(storage_probe, 'report', side_effect=AssertionError('Probe forbidden')), \
                patch.object(state, 'load', side_effect=AssertionError('Profile read forbidden')):
            self.run_route('storage_check')
        self.assertEqual((self.rows, self.ends, self.commands, self.messages), ([], [], [], []))
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_storage_check_is_explicit_synthetic_and_before_profile_loading(self):
        self.modules['xbmc'].Player = lambda: self.fail('Player forbidden')
        with patch.object(state, 'load', side_effect=AssertionError('Profile read forbidden')), \
                patch('socket.create_connection', side_effect=AssertionError('Network forbidden')):
            self.run_route('storage_check')
        self.assertIn('Overall: passed', self.messages[-1])
        self.assertNotIn(self.temp.name, self.messages[-1])
        self.assertEqual((self.rows, self.ends, self.commands), ([], [], []))
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_storage_check_only_in_root_and_rejects_extra_parameters(self):
        self.run_route()
        self.assertTrue(any('route=storage_check' in url for url, _, _ in self.rows))
        self.run_route('widgets')
        self.assertFalse(any('route=storage_check' in url for url, _, _ in self.rows))
        with self.assertRaises(ValueError):
            routes.parse('?route=storage_check&id=private')

    def test_readiness_without_profile_network_or_optional_kodi_information(self):
        with patch.object(state, 'load', side_effect=AssertionError('Profile read forbidden')), \
                patch('socket.create_connection', side_effect=AssertionError('Network forbidden')):
            self.run_route('readiness')
        self.assertEqual(self.rows, [])
        self.assertEqual(self.ends, [])
        self.assertEqual(self.commands, [])
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])
        report = self.messages[-1]
        self.assertIn('Kodi: unavailable', report)
        self.assertIn('HomeFX: unavailable', report)
        self.assertIn('Umbrella version: unavailable; handoff untested', report)
        self.assertNotIn(self.temp.name, report)

    def test_widget_setup_has_no_profile_account_network_or_player_access(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('Private or player access forbidden')
        class NoInfoAddon:
            def getAddonInfo(self, key):
                forbidden()
        self.modules['xbmcaddon'].Addon = NoInfoAddon
        self.modules['xbmcvfs'].translatePath = forbidden
        self.modules['xbmc'].Player = forbidden
        with patch.object(state, 'load', side_effect=forbidden), \
                patch('sqlite3.connect', side_effect=forbidden), \
                patch('socket.create_connection', side_effect=forbidden):
            self.run_route('widget_setup')
        self.assertEqual(len(self.messages), 2)
        self.assertIn('one list folder per row', self.messages[0])
        self.assertIn('Clickable widget headings depend on your skin', self.messages[1])
        self.assertIn('no media will play', self.messages[1])
        self.assertEqual((self.rows, self.ends, self.commands), ([], [], []))
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_widget_setup_only_in_root_and_rejects_extra_parameters(self):
        self.run_route()
        rows = [(url, folder) for url, item, folder in self.rows
                if item.label == 'Widget setup…']
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0][1])
        self.assertEqual(routes.parse(urlsplit(rows[0][0]).query), ('widget_setup', {}))
        self.run_route('widgets')
        self.assertNotIn('widget_setup', [routes.parse(urlsplit(url).query)[0]
                                         for url, _, _ in self.rows])
        for extra in ('id=private', 'q=secret', 'value=1', 'url=plugin%3A%2F%2Fother',
                      'route=home'):
            with self.assertRaises(ValueError):
                routes.parse('route=widget_setup&' + extra)

    def test_repository_readiness_uses_explicit_presence_and_version_only(self):
        reads = []
        class VersionAddon:
            def __init__(self, addon_id='plugin.video.homefx'):
                self.addon_id = addon_id
            def getAddonInfo(self, key):
                reads.append((self.addon_id, key))
                if key != 'version':
                    raise AssertionError('Only version may be read')
                return '0.2.0' if self.addon_id == 'repository.homefx' else '1.2.3'
        self.modules['xbmcaddon'].Addon = VersionAddon
        conditions = []
        def installed(condition):
            conditions.append(condition)
            return True
        self.modules['xbmc'].getCondVisibility = installed
        with patch.object(state, 'load', side_effect=AssertionError('Profile forbidden')):
            self.run_route('readiness')
        self.assertEqual(conditions, ['System.HasAddon(repository.homefx)'])
        self.assertIn(('repository.homefx', 'version'), reads)
        self.assertIn('HomeFX repository: 0.2.0', self.messages[-1])
        reads.clear()
        self.modules['xbmc'].getCondVisibility = lambda condition: False
        self.run_route('readiness')
        self.assertNotIn(('repository.homefx', 'version'), reads)
        self.assertIn('HomeFX repository: not installed', self.messages[-1])
        self.modules['xbmc'].getCondVisibility = lambda condition: 'unexpected private text'
        self.run_route('readiness')
        self.assertIn('HomeFX repository: unavailable', self.messages[-1])
        self.assertNotIn('unexpected private text', self.messages[-1])

    def test_playback_setup_is_information_only_before_any_profile_or_account_access(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('Account, profile and playback access forbidden')

        class NoInfoAddon:
            def getAddonInfo(self, key):
                forbidden()

        self.modules['xbmcaddon'].Addon = NoInfoAddon
        self.modules['xbmcvfs'].translatePath = forbidden
        self.modules['xbmc'].Player = forbidden
        with patch.object(state, 'load', side_effect=forbidden), \
                patch('socket.create_connection', side_effect=forbidden), \
                patch('sqlite3.connect', side_effect=forbidden):
            self.run_route('playback_setup')
        self.assertEqual(self.rows, [])
        self.assertEqual(self.ends, [])
        self.assertEqual(self.commands, [])
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])
        self.assertIsNone(self.last_default)
        self.assertEqual(self.choices, [])
        guidance = self.messages[-1]
        self.assertIn('metadata, not playable sources', guidance)
        self.assertIn('source you are authorized to access', guidance)
        self.assertIn('Umbrella playback handoff is unverified', guidance)
        self.assertIn('Real-Debrid prototype is inactive', guidance)
        self.assertIn('Never enter or share account tokens or client secrets', guidance)
        self.assertNotIn(self.temp.name, guidance)

    def test_root_playback_setup_action_stays_out_of_widget_sources(self):
        self.run_route()
        rows = [(url, folder) for url, item, folder in self.rows
                if item.label == 'Playback and Real-Debrid setup…']
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0][1])
        self.assertEqual(routes.parse(urlsplit(rows[0][0]).query), ('playback_setup', {}))
        self.run_route('widgets')
        self.assertNotIn('playback_setup', [routes.parse(urlsplit(url).query)[0]
                                           for url, _, _ in self.rows])

    def test_movie_click_and_information_distinguish_dates_from_sources(self):
        for route in ('play', 'info'):
            self.run_route(route, id='m3')
            self.assertIn('A release date does not establish a playable source', self.messages[-1])
            self.assertIn('separate authorized source', self.messages[-1])
            self.assertIn('Demo only: no playback', self.messages[-1])
        self.assertEqual(self.commands, [])

    def test_readiness_reads_only_explicit_numeric_runtime_versions(self):
        reads = []

        class VersionAddon:
            def __init__(self, addon_id='plugin.video.homefx'):
                self.addon_id = addon_id

            def getAddonInfo(self, key):
                reads.append((self.addon_id, key))
                if key != 'version':
                    raise AssertionError('Only version may be read')
                return '0.4.0' if self.addon_id == 'plugin.video.homefx' else '6.7.8'

        self.modules['xbmcaddon'].Addon = VersionAddon
        self.modules['xbmc'].getInfoLabel = lambda name: '21.2 (private build details)'
        with patch.object(state, 'load', side_effect=AssertionError('Profile read forbidden')):
            self.run_route('readiness')
        self.assertEqual(set(reads), {('plugin.video.homefx', 'version'),
                                      ('plugin.video.umbrella', 'version')})
        self.assertIn('Kodi: 21.2', self.messages[-1])
        self.assertIn('Umbrella version: 6.7.8; handoff untested', self.messages[-1])
        self.assertNotIn('private build details', self.messages[-1])

    def test_normal_navigation_does_not_require_optional_runtime_modules(self):
        with patch.dict(sys.modules, {'ssl': None, 'sqlite3': None}):
            self.run_route()
        self.assertTrue(self.rows)
        self.assertEqual(self.ends, [{'succeeded': True, 'cacheToDisc': False}])

    def test_root_offers_readiness_action(self):
        self.run_route()
        rows = [(url, folder) for url, item, folder in self.rows
                if item.label == 'Device readiness']
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0][1])
        self.assertEqual(routes.parse(urlsplit(rows[0][0]).query)[0], 'readiness')

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

    def test_widget_directory_has_only_selected_content_sources(self):
        self.selection = [3]
        self.run_route('select')
        self.commands.clear()
        self.messages.clear()
        self.run_route('widgets')
        self.assertTrue(all(folder for _, _, folder in self.rows))
        destinations = [routes.parse(urlsplit(url).query) for url, _, _ in self.rows]
        self.assertEqual(destinations, [('list', {'id': 'saved'}), ('continue', {}),
            ('next', {}), ('upcoming', {}), ('upcoming_movies', {})])
        self.assertEqual(self.messages, [])
        self.assertEqual(self.commands, [])
        self.assertIn('released_unwatched', dict(self.rows[0][1].menu)['Released unwatched titles (demo)'])
        self.run_route('list', id='saved')
        self.assertEqual(self.rows, [])
        self.assertIn('no matching demo titles', self.categories[-1])
        self.assertEqual(self.messages, [])
        self.assertEqual(self.ends, [{'succeeded': True, 'cacheToDisc': False}])

    def test_movie_filters_and_upcoming_saved_route_keep_content_rows_clean(self):
        self.run_route('list', id='weekend', filter='released_unwatched')
        self.assertEqual([li.tag.values['title'] for _, li, _ in self.rows],
                         ['The Lantern Harbour', 'A Map of Quiet Stars'])
        self.assertTrue(all(li.tag.values and not folder for _, li, folder in self.rows))
        self.run_route('list', id='weekend', filter='upcoming')
        self.assertEqual([li.tag.values['title'] for _, li, _ in self.rows], ["Tomorrow's Orchard"])
        self.run_route('collect', id='m3', value='1')
        self.run_route('upcoming_movies')
        self.assertEqual(len(self.rows), 1)
        self.assertIn('Upcoming', self.rows[0][1].label)
        self.assertEqual(self.content[-1], 'movies')

    def test_season_folders_counts_and_context_preserve_scope(self):
        self.run_route('seasons', id='s1')
        self.assertEqual(len(self.rows), 1)
        url, li, folder = self.rows[0]
        self.assertTrue(folder)
        self.assertIn('2/6 watched', li.label)
        self.assertIn('2 aired unwatched', li.label)
        self.assertIn('2 upcoming', li.label)
        self.assertEqual(routes.parse(urlsplit(url).query),
                         ('show', {'season': '1', 'filter': 'all', 'id': 's1'}))
        self.assertIn('season=1', dict(li.menu)['Aired unwatched episodes in this season (demo)'])
        self.run_route('show', id='s1', season='1', filter='aired_unwatched')
        self.assertEqual([li.tag.values['episode'] for _, li, _ in self.rows], [2, 4])
        menu = dict(self.rows[0][1].menu)
        self.assertIn('season=1', menu['Browse all episodes (demo)'])
        self.assertIn('route=seasons', menu['Browse seasons (demo)'])
        self.run_route('show', id='s1', season='2')
        self.assertEqual(self.rows, [])
        self.assertTrue(self.ends[-1]['succeeded'])
        self.assertEqual(self.messages, [])

    def test_invalid_routes_are_bounded_and_unambiguous(self):
        for query in ('route=list&route=home', 'route=list&id=weekend&id=saved',
                      'route=show&id=s1&season=-1', 'route=show&id=s1&season=1000',
                      'route=show&id=s1&season=01', 'route=list&id=saved&season=1',
                      'route=widgets&filter=all', 'route=list&id=saved&filter=aired_unwatched',
                      'route=show&id=s1&filter=released_unwatched',
                      'route=search&q=' + 'x' * 257, 'route=list&id=' + 'x' * 129,
                      'route=search&q=%00', 'route=home&unknown=x'):
            with self.subTest(query=query), self.assertRaises(ValueError):
                routes.parse(query)
        self.assertEqual(routes.parse('route=show&id=s1&season=0')[1]['season'], '0')
        self.run_route('seasons', id='m1')
        self.assertFalse(self.ends[-1]['succeeded'])

    def test_failed_profile_write_does_not_disclose_private_path(self):
        with patch.object(state, 'save', side_effect=OSError('/private/user/profile/token.sqlite')):
            self.run_route('watched', id='m1', value='1')
        self.assertFalse(self.ends[-1]['succeeded'])
        self.assertNotIn('/private', self.messages[-1])
        self.assertNotIn('token.sqlite', self.messages[-1])
        self.assertEqual(self.commands, [])

    def test_legacy_empty_id_widget_urls_remain_navigable(self):
        for route in ('home', 'continue', 'next', 'upcoming', 'search', 'select',
                      'reset', 'setup', 'readiness', 'widgets', 'upcoming_movies', 'playback_setup', 'widget_setup'):
            with self.subTest(route=route):
                self.assertEqual(routes.parse('route=' + route + '&id='), (route, {}))
        for route in ('continue', 'next', 'upcoming'):
            with self.subTest(route=route):
                self.run_route(route, id='')
                self.assertTrue(self.rows)
                self.assertEqual(self.ends, [{'succeeded': True, 'cacheToDisc': False}])
        for route in ('list', 'show', 'seasons', 'play', 'watched', 'info', 'sequence',
                      'similar', 'collect'):
            with self.subTest(route=route), self.assertRaises(ValueError):
                routes.parse('route=' + route + '&id=')
