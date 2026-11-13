"""Personal calendar projection and account boundaries; fabricated responses only."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib import trakt_calendar as calendar
from resources.lib.trakt_auth import AuthError
from resources.lib.trakt_client import ApiError

NOW = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)


def entry(ident=101, show=10, number=1, stamp="2026-11-14T00:00:00Z"):
    return {"first_aired": stamp,
            "show": {"ids": {"trakt": show}, "title": "Invented series", "year": 2026},
            "episode": {"ids": {"trakt": ident}, "title": "Invented episode",
                        "season": 1, "number": number, "first_aired": stamp}}


class Session:
    def __init__(self, entries=()):
        self.entries = list(entries)
        self.generation = 1
        self.data_revision = 0
        self.calls = []
        self.hook = None
        self.payload_hook = None

    def cache_key(self):
        self.calls.append("activate")
        return self.generation

    def assert_current(self, generation):
        if generation != self.generation:
            raise AuthError("session_changed")

    def read(self, operation, start, days):
        self.calls.append((operation, start, days))
        if self.hook:
            self.hook()
        payload = {"start_date": start, "days": days, "entries": deepcopy(self.entries)}
        if self.payload_hook:
            self.payload_hook(payload)
        return payload


class CalendarTests(unittest.TestCase):
    def test_upcoming_order_utc_boundaries_and_metadata_only(self):
        source = Session([entry(103, number=3, stamp="2026-11-20T01:00:00+02:00"),
                          entry(102, number=2, stamp="2026-11-13T12:00:00Z"),
                          entry(101, stamp="2026-11-14T01:00:00+02:00")])
        rows = calendar.upcoming(source, "2026-11-13", now=NOW)
        self.assertEqual([row["trakt_id"] for row in rows], [101, 103])
        self.assertEqual(rows[0]["release_at"].isoformat(), "2026-11-13T23:00:00+00:00")
        self.assertTrue(all(row["watched"] is None and row["playable"] is False
                            and row["aired_unwatched"] is False for row in rows))
        self.assertEqual(len(source.calls), 2)

    def test_filter_is_only_personal_calendar_intersection_and_detached(self):
        source = Session([entry(), entry(201, show=20)])
        rows = calendar.upcoming(source, "2026-11-13", now=NOW, allowed_show_ids={20, 30})
        self.assertEqual([row["show_id"] for row in rows], [20])
        rows[0]["title"] = "changed"
        self.assertEqual(source.entries[1]["episode"]["title"], "Invented episode")
        empty = Session([entry()])
        self.assertEqual(calendar.upcoming(empty, "2026-11-13", now=NOW, allowed_show_ids=[]), [])
        self.assertEqual(empty.calls, [])

    def test_bad_inputs_do_not_activate_or_read(self):
        cases = [dict(start_date="2026-2-01"), dict(start_date="9999-12-31", days=31),
                 dict(days=True), dict(days=0), dict(days=32), dict(now=0), dict(now=False),
                 dict(now=datetime(2026, 11, 13)), dict(allowed_show_ids=[True]),
                 dict(allowed_show_ids="10"), dict(allowed_show_ids=list(range(1, 102)))]
        for changes in cases:
            source = Session([entry()])
            args = dict(start_date="2026-11-13", days=7, now=NOW)
            args.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ApiError):
                calendar.upcoming(source, **args)
            self.assertEqual(source.calls, [])

    def test_account_or_revision_change_during_read_fails(self):
        for field in ("generation", "data_revision"):
            source = Session([entry()])
            source.hook = lambda: setattr(source, field, getattr(source, field) + 1)
            with self.subTest(field=field), self.assertRaises((ApiError, AuthError)):
                calendar.upcoming(source, "2026-11-13", now=NOW)
            self.assertEqual(len(source.calls), 2)

    def test_revision_change_during_projection_fails(self):
        source = Session([entry()])
        original = calendar._project

        def project(*args):
            result = original(*args)
            source.data_revision += 1
            return result

        with patch.object(calendar, "_project", side_effect=project):
            with self.assertRaisesRegex(ApiError, "data_changed"):
                calendar.upcoming(source, "2026-11-13", now=NOW)

    def test_duplicate_identity_or_coordinate_conflicts_are_rejected(self):
        source = Session([entry(), entry()])
        self.assertEqual(len(calendar.upcoming(source, "2026-11-13", now=NOW)), 1)
        for conflict in [entry(show=20), entry(number=2), entry(102),
                         entry(stamp="2026-11-15T00:00:00Z")]:
            with self.subTest(conflict=conflict), self.assertRaisesRegex(ApiError, "conflicting_calendar_episode"):
                calendar.upcoming(Session([entry(), conflict]), "2026-11-13", now=NOW)

    def test_unknown_title_is_numeric_but_unknown_date_never_becomes_upcoming(self):
        row = entry()
        row["episode"]["title"] = None
        row["episode"]["first_aired"] = None
        rows = calendar.upcoming(Session([row]), "2026-11-13", now=NOW)
        self.assertEqual(rows[0]["title"], "Episode S01E01")
        for stamp in (None, "", "not-a-date", "2026-11-14T00:00:00", "2026-11-14"):
            invalid = entry(stamp=stamp)
            with self.subTest(stamp=stamp), self.assertRaises(ApiError):
                calendar.upcoming(Session([invalid]), "2026-11-13", now=NOW)

    def test_window_and_nested_date_mismatches_fail(self):
        for stamp in ("2026-11-12T23:59:59Z", "2026-11-20T00:00:00Z"):
            with self.subTest(stamp=stamp), self.assertRaisesRegex(ApiError, "calendar_window_mismatch"):
                calendar.upcoming(Session([entry(stamp=stamp)]), "2026-11-13", now=NOW)
        row = entry()
        row["episode"]["first_aired"] = "2026-11-15T00:00:00Z"
        with self.assertRaisesRegex(ApiError, "conflicting_calendar_episode"):
            calendar.upcoming(Session([row]), "2026-11-13", now=NOW)
        source = Session([entry()])
        source.payload_hook = lambda payload: payload.update(days=True)
        with self.assertRaisesRegex(ApiError, "calendar_window_mismatch"):
            calendar.upcoming(source, "2026-11-13", now=NOW)

    def test_bounds_malformed_rows_and_empty_response(self):
        self.assertEqual(calendar.upcoming(Session(), "2026-11-13", now=NOW), [])
        with self.assertRaisesRegex(ApiError, "invalid_calendar_metadata"):
            calendar.upcoming(Session([entry()] * 1001), "2026-11-13", now=NOW)
        for change in [lambda row: row.update(show=None),
                       lambda row: row["episode"].update(number=0),
                       lambda row: row["episode"]["ids"].update(trakt=True),
                       lambda row: row["show"].update(title="\nprivate"),
                       lambda row: row["show"].update(title="\u202ehidden"),
                       lambda row: row["episode"].update(title=" ")]:
            row = entry()
            change(row)
            with self.subTest(change=change), self.assertRaises(ApiError):
                calendar.upcoming(Session([row]), "2026-11-13", now=NOW)


if __name__ == "__main__":
    unittest.main()
