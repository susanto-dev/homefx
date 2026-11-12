import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib import catalogue as m, routes, state
import tempfile

TODAY = date(2026, 11, 12)


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.items = m.catalogue(TODAY)

    def test_movie_groups_and_release_dates(self):
        rows = m.view("list", self.items, {}, "weekend", today=TODAY)
        self.assertEqual([x["id"] for x in rows], ["m1", "m2", "m3", "m4"])
        self.assertEqual(self.items["m2"]["date"], "2026-11-04")
        self.assertEqual(self.items["m3"]["date"], "2026-12-12")

    def test_episode_order_and_next_unwatched(self):
        self.assertEqual([x["id"] for x in m.view("show", self.items, {}, "s1")],
                         ["e1", "e2", "e3", "e4", "e5", "e6"])
        self.assertEqual([x["id"] for x in m.view("next", self.items, {}, today=TODAY)], ["e2"])
        changed = m.apply_state(self.items, {"watched": {"e2": True}})
        self.assertEqual([x["id"] for x in m.view("next", changed, {}, today=TODAY)], ["e4"])
        self.assertEqual(changed["e2"]["progress"], 0)
        self.assertEqual(self.items["e2"]["progress"], 35)

    def test_continue_excludes_watched_and_upcoming(self):
        self.assertEqual([x["id"] for x in m.view("continue", self.items, {}, today=TODAY)],
                         ["e2", "m1"])
        self.items["m3"]["progress"] = 10
        self.assertNotIn("m3", [x["id"] for x in m.view("continue", self.items, {}, today=TODAY)])

    def test_calendar_boundaries(self):
        self.items["e5"]["date"] = "2026-11-19"
        self.items["e6"]["date"] = "2026-11-20"
        self.assertEqual([x["id"] for x in m.view("upcoming", self.items, {}, today=TODAY)], ["e5"])
        self.items["e5"]["date"] = TODAY.isoformat()
        self.assertEqual(m.view("upcoming", self.items, {}, today=TODAY), [])

    def test_next_episode_choice_and_unaired_boundary(self):
        immediate, unwatched = m.continuation(self.items, "e2", TODAY)
        self.assertEqual((immediate["id"], unwatched["id"]), ("e3", "e4"))
        self.assertEqual(m.continuation(self.items, "e4", TODAY), (None, None))
        self.items["e4"]["watched"] = True
        self.assertIsNone(m.continuation(self.items, "e2", TODAY)[1])

    def test_search_and_related_relevance(self):
        self.assertEqual([x["id"] for x in m.view("search", self.items, {}, query="LANTERN")], ["m1"])
        self.assertEqual([x["id"] for x in m.view("similar", self.items, {}, "m1")], ["m5", "m2"])
        self.assertEqual(m.view("search", self.items, {}, query="no such title"), [])

    def test_encoded_route_roundtrip_and_rejection(self):
        text = "Title & sequel / 雨? (2026), +"
        url = routes.url("search", q=text)
        self.assertEqual(routes.parse(url.split("?", 1)[1]), ("search", {"q": text}))
        with self.assertRaises(ValueError):
            routes.parse("?route=execute&q=anything")
        with self.assertRaises(ValueError):
            routes.parse("x" * 4097)

    def test_local_state_recovery_and_empty_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "demo.json"
            self.assertEqual(state.load(path)["selected"], list(m.LISTS))
            state.save(path, {"selected": [], "watched": {"m1": True}})
            self.assertEqual(state.load(path), {"selected": [], "watched": {"m1": True}})
            path.write_text("broken")
            self.assertEqual(state.load(path)["watched"], {})
            self.assertEqual(list(Path(temp).glob("demo-*")), [])
