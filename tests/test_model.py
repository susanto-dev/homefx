import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib import catalogue as m, routes, state
import tempfile
import json

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

    def test_saved_movie_list_includes_future_titles_and_preserves_widget_order(self):
        prefs = {"saved_movies": ["m4", "m3", "m2", "m1", "m1", "e2", "missing"]}
        rows = m.view("list", self.items, prefs, "saved", today=TODAY)
        self.assertEqual([x["id"] for x in rows], ["m1", "m2", "m3", "m4"])
        self.assertEqual(rows[2]["date"], "2026-12-12")
        self.assertEqual(rows[0]["progress"], 42)
        self.assertTrue(rows[-1]["watched"])
        self.assertEqual(m.view("list", self.items, {}, "saved", today=TODAY), [])

    def test_aired_unwatched_filter_keeps_resume_and_narrative_order(self):
        rows = m.view("show", self.items, {}, "s1", today=TODAY, episode_filter="aired_unwatched")
        self.assertEqual([x["id"] for x in rows], ["e2", "e4"])
        self.assertEqual(rows[0]["progress"], 35)
        self.items["e4"]["date"] = None
        self.assertEqual([x["id"] for x in m.view("show", self.items, {}, "s1", today=TODAY,
                         episode_filter="aired_unwatched")], ["e2"])
        self.items["e4"]["date"] = "unknown"
        self.assertEqual([x["id"] for x in m.view("show", self.items, {}, "s1", today=TODAY,
                         episode_filter="aired_unwatched")], ["e2"])
        self.assertEqual(len(m.view("show", self.items, {}, "s1", today=TODAY)), 6)
        with self.assertRaisesRegex(ValueError, "Unknown episode filter"):
            m.view("show", self.items, {}, "s1", episode_filter="anything")

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
        self.assertEqual(routes.parse("?route=show&id=s1&filter=aired_unwatched"),
                         ("show", {"id": "s1", "filter": "aired_unwatched"}))
        for query in ("route=show&filter=unknown", "route=list&filter=aired_unwatched",
                      "route=show&filter=all&filter=aired_unwatched"):
            with self.subTest(query=query), self.assertRaises(ValueError):
                routes.parse(query)

    def test_local_state_recovery_and_empty_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "demo.json"
            self.assertEqual(state.load(path)["selected"], list(m.LISTS))
            state.save(path, {"selected": [], "watched": {"m1": True}})
            self.assertEqual(state.load(path), {"selected": [], "watched": {"m1": True},
                                                "saved_movies": []})
            path.write_text("broken")
            self.assertEqual(state.load(path)["watched"], {})
            self.assertEqual(list(Path(temp).glob("demo-*")), [])

    def test_old_profile_migration_preserves_preferences_and_validates_collection(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "demo.json"
            path.write_text(json.dumps({"selected": ["series"], "watched": {"e2": True}}))
            original = state.load(path)
            self.assertEqual(original, {"selected": ["series"], "watched": {"e2": True},
                                        "saved_movies": []})
            original["saved_movies"] = ["m3", "m3", "e2", "s1", "missing", {}, "m1"]
            state.save(path, original)
            restored = state.load(path)
            self.assertEqual(restored["saved_movies"], ["m3", "m1"])
            self.assertEqual(restored["selected"], ["series"])
            self.assertEqual(restored["watched"], {"e2": True})
            self.assertEqual(list(Path(temp).glob("demo-*")), [])
            restored["saved_movies"] = "invalid"
            state.save(path, restored)
            self.assertEqual(state.load(path)["saved_movies"], [])
            self.assertEqual(state.load(path)["watched"], {"e2": True})

    def test_oversized_and_deep_profile_is_recovered_without_parsing_unbounded_data(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "demo.json"
            for content in (" " * (state.MAX_STATE_BYTES + 1), "[" * 3000 + "]" * 3000):
                path.write_text(content)
                self.assertEqual(state.load(path)["saved_movies"], [])
                self.assertEqual(state.load(path)["selected"], list(m.LISTS))
