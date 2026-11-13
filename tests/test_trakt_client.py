"""Synthetic response tests. No account, credentials or network is used."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib.trakt_client import Client, Response, ApiError, retry_delay


class Transport:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        return next(self.responses)


def response(body, pages=None, page=None):
    headers = {}
    if pages is not None:
        headers["X-Pagination-Page-Count"] = str(pages)
    if page is not None:
        headers["X-Pagination-Page"] = str(page)
    return Response(200, headers, body)


def item(ident, name="Example list"):
    return {"ids": {"trakt": ident}, "name": name,
            "user": {"ids": {"slug": "synthetic-user"}}}


class ClientTests(unittest.TestCase):
    def test_detail_projection_binds_identity_and_nullable_dates(self):
        movie = {"ids": {"trakt": 9, "tmdb": 100}, "title": "Synthetic", "year": 2026,
                 "released": "2026-01-01", "overview": "not projected"}
        episode = {"ids": {"trakt": 30}, "title": None, "season": 0, "number": 1,
                   "first_aired": None}
        transport = Transport(response(movie), response(episode))
        client = Client(transport, "id", "token")
        self.assertEqual(client.movie_details(9), {"ids": {"trakt": 9}, "title": "Synthetic",
                                                  "year": 2026, "released": "2026-01-01"})
        self.assertEqual(client.episode_details(7, 0, 1), {"show_id": 7, "episode": episode})
        self.assertEqual([call[1] for call in transport.calls],
                         ["/movies/9?extended=full", "/shows/7/seasons/0/episodes/1?extended=full"])

    def test_details_reject_wrong_identity_coordinates_pagination_and_dates(self):
        movie = {"ids": {"trakt": 9}, "title": "Synthetic", "released": "2026-01-01"}
        episode = {"ids": {"trakt": 30}, "title": "Pilot", "season": 1, "number": 2}
        cases = [("movie_details", (8,), response(movie)),
                 ("movie_details", (9,), response(movie, pages=1)),
                 ("movie_details", (9,), response({**movie, "released": "2026-02-30"})),
                 ("episode_details", (7, 1, 1), response(episode)),
                 ("episode_details", (7, 1, 2), response(episode, pages=2)),
                 ("episode_details", (7, 1, 2), response({**episode, "first_aired": "2026-01-01"}))]
        for operation, args, reply in cases:
            with self.subTest(operation=operation, args=args), self.assertRaises(ApiError):
                getattr(Client(Transport(reply), "id", "token"), operation)(*args)

    def test_personal_calendar_projects_utc_window_without_grouped_or_watched_claims(self):
        row = {"first_aired": "2026-11-13T00:00:00Z",
               "show": {"ids": {"trakt": 7}, "title": "Synthetic Show", "year": 2026},
               "episode": {"ids": {"trakt": 30}, "title": None, "season": 1, "number": 1}}
        transport = Transport(response([row]))
        result = Client(transport, "id", "token").calendar_shows("2026-11-13", 7)
        self.assertEqual((result["start_date"], result["days"]), ("2026-11-13", 7))
        self.assertIsNone(result["entries"][0]["episode"]["first_aired"])
        self.assertNotIn("watched", result["entries"][0])
        self.assertEqual(transport.calls[0][1], "/calendars/my/shows/2026-11-13/7?extended=full")
        self.assertEqual(Client(Transport(response([])), "id", "token").calendar_shows(
            "2026-11-13")["entries"], [])

    def test_calendar_rejects_truncation_duplicates_conflicts_and_outside_window(self):
        from copy import deepcopy
        row = {"first_aired": "2026-11-13T00:00:00Z", "show": {"ids": {"trakt": 7}, "title": "Show"},
               "episode": {"ids": {"trakt": 30}, "title": "Pilot", "season": 1, "number": 1}}
        bad_rows = []
        for field, value in (("first_aired", "2026-11-14T00:00:00Z"),
                             ("episodes", []), ("episode_type", "full_season"), ("number", False)):
            item = deepcopy(row); item["episode"][field] = value; bad_rows.append([item])
        for stamp in ("2026-11-12T23:59:59Z", "2026-11-20T00:00:00Z", "2026-11-13T00:00:00",
                      "2026-11-13\n00:00:00Z"):
            bad_rows.append([{**row, "first_aired": stamp}])
        bad_rows.extend(([row, row], [{**row, "show": {"ids": {"trakt": 0}, "title": "Show"}}]))
        for body in bad_rows:
            with self.subTest(body=body), self.assertRaises(ApiError):
                Client(Transport(response(body)), "id", "token").calendar_shows("2026-11-13")
        for reply in (response([row], pages=1), response({}), response([row, row])):
            with self.assertRaises(ApiError):
                Client(Transport(reply), "id", "token", max_items=1).calendar_shows("2026-11-13")

    def test_calendar_inputs_reject_invalid_dates_and_bounds_before_request(self):
        transport = Transport()
        client = Client(transport, "id", "token")
        for start, days in (("2026-02-30", 7), ("2026-1-01", 7), ("2026-11-13", True),
                            ("9999-12-31", 1), ("2026-11-13", 32), ("2026-11-13", 0)):
            with self.assertRaises(ApiError):
                client.calendar_shows(start, days)
        self.assertEqual(transport.calls, [])

    def test_show_seasons_project_bounded_metadata_without_watch_claims(self):
        source = [{"number": 2, "ids": {"trakt": 22, "tmdb": 99},
                   "title": "Second", "episode_count": 12, "aired_episodes": 4,
                   "first_aired": "2026-01-01T00:00:00Z", "images": {"unused": True}},
                  {"number": 0, "ids": {"trakt": 20}}]
        request = Transport(response(source))
        result = Client(request, "id", "token").show_seasons(7)
        self.assertEqual(request.calls[0][1], "/shows/7/seasons?extended=full")
        self.assertEqual(result, {"show_id": 7, "seasons": [
            {"number": 2, "ids": {"trakt": 22}, "title": "Second",
             "episode_count": 12, "aired_episodes": 4, "first_aired": "2026-01-01T00:00:00Z"},
            {"number": 0, "ids": {"trakt": 20}, "title": None,
             "episode_count": None, "aired_episodes": None, "first_aired": None}]})
        result["seasons"][0]["ids"]["trakt"] = 999
        self.assertEqual(source[0]["ids"]["trakt"], 22)

    def test_show_seasons_rejects_bad_rows_duplicates_and_incomplete_responses(self):
        row = {"number": 1, "ids": {"trakt": 11}}
        for bad in (None, {}, {"number": True, "ids": {"trakt": 11}},
                    dict(row, number=-1), dict(row, ids={"trakt": True}),
                    dict(row, episode_count=-1), dict(row, aired_episodes=True),
                    dict(row, first_aired=[]), dict(row, title="bad\n")):
            with self.subTest(bad=bad), self.assertRaises(ApiError):
                Client(Transport(response([bad])), "id", "token").show_seasons(7)
        for rows in ([row, row], [row, dict(row, ids={"trakt": 12})],
                     [row, dict(row, number=2)]):
            with self.assertRaises(ApiError):
                Client(Transport(response(rows)), "id", "token").show_seasons(7)
        with self.assertRaises(ApiError):
            Client(Transport(response([row, dict(row, number=2, ids={"trakt": 12})])),
                   "id", "token", max_items=1).show_seasons(7)
        with self.assertRaisesRegex(ApiError, "invalid_pagination"):
            Client(Transport(response([row], pages=2)), "id", "token").show_seasons(7)
        self.assertEqual(Client(Transport(response([])), "id", "token").show_seasons(7),
                         {"show_id": 7, "seasons": []})

    def test_season_episode_collection_rejects_pagination_metadata(self):
        for headers in ({"X-Pagination-Page-Count": "2"}, {"x-pagination-page": "1"},
                        {"x-pagination-item-count": "100"}):
            with self.assertRaisesRegex(ApiError, "invalid_pagination"):
                Client(Transport(Response(200, headers, [])), "id", "token").season_episodes(7, 1)

    def test_series_input_validation_and_explicit_specials_scope(self):
        request = Transport(response({"seasons": []}), response({"seasons": []}))
        client = Client(request, "id", "token")
        for bad in (0, -1, True, "7", 2 ** 63):
            for operation in (lambda: client.show_seasons(bad),
                              lambda: client.show_progress(bad),
                              lambda: client.season_episodes(bad, 1)):
                with self.assertRaises(ApiError):
                    operation()
        for bad in (0, 1, None, "true", []):
            with self.assertRaises(ApiError):
                client.show_progress(7, bad)
        self.assertEqual(request.calls, [])
        self.assertEqual(client.show_progress(7), {"show_id": 7, "progress": {"seasons": []}})
        client.show_progress(7, True)
        self.assertEqual([call[1] for call in request.calls], [
            "/shows/7/progress/watched?hidden=false&specials=false",
            "/shows/7/progress/watched?hidden=false&specials=true"])

    def test_title_search_literal_encoding_and_basic_projection(self):
        from urllib.parse import urlsplit, parse_qs
        from resources.lib.trakt_client import metadata_rows
        body = [{"type": "show", "score": 7, "show": {
            "ids": {"trakt": 9}, "title": "Synthetic", "images": {"poster": "unused"}}}]
        request = Transport(response(body))
        result = Client(request, "id", "token").search_titles(" café + sequel ", "show")
        self.assertEqual(result, body)
        path = urlsplit(request.calls[0][1])
        self.assertEqual(path.path, "/search/show")
        self.assertEqual(parse_qs(path.query), {"query": ["café \\+ sequel"],
            "fields": ["title"], "page": ["1"], "limit": ["100"]})
        row = metadata_rows(result, "show", wrapped=True)[0]
        self.assertEqual(row, {"kind": "show", "trakt_id": 9, "title": "Synthetic",
            "year": None, "watched": None, "release_status": "unknown", "playable": False})

    def test_metadata_inputs_rejected_without_transport(self):
        request = Transport()
        client = Client(request, "id", "token")
        for query in (None, [], "", "   ", "x" * 129, "a\n", "a\x00", "a\x7f", "a\u0085", "a\ud800"):
            with self.subTest(query=repr(query)), self.assertRaises(ApiError):
                client.search_titles(query)
        for kind in ([], None, "episode", "movie,show"):
            with self.assertRaises(ApiError):
                client.search_titles("title", kind)
        for ident in (True, 0, -1, "1", [], 2 ** 63):
            with self.assertRaises(ApiError):
                client.related_movies(ident)
        self.assertEqual(request.calls, [])

    def test_related_order_and_pagination_fail_closed(self):
        first = {"ids": {"trakt": 20}, "title": "Z", "year": None}
        second = {"ids": {"trakt": 10}, "title": "A", "year": 2025}
        request = Transport(response([first], pages=2, page=1), response([second], pages=2, page=2))
        self.assertEqual(Client(request, "id", "token", page_size=1).related_movies(12), [first, second])
        self.assertEqual(request.calls[0][1], "/movies/12/related?page=1&limit=1")
        for responses in ((response([first]),), (response([first], pages=2, page=1), Response(500)),
                          (response([first], pages=2, page=1), response([first], pages=2, page=2))):
            with self.assertRaises(ApiError):
                Client(Transport(*responses), "id", "token", page_size=1).related_movies(12)
        with self.assertRaisesRegex(ApiError, "result_limit"):
            Client(Transport(response([first], pages=2, page=1)), "id", "token", page_size=1, max_pages=1).related_movies(12)

    def test_metadata_rejects_unusable_and_mistyped_rows(self):
        valid = {"ids": {"trakt": 1}, "title": "Synthetic"}
        for media in (None, {}, dict(valid, year=True), dict(valid, title=""),
                      dict(valid, year=10000), dict(valid, ids={"trakt": 0})):
            with self.assertRaises(ApiError):
                Client(Transport(response([{"type": "movie", "movie": media}])), "id", "token").search_titles("x")
        with self.assertRaises(ApiError):
            Client(Transport(response([{"type": "show", "show": valid}])), "id", "token").search_titles("x")

    def test_watched_movies_complete_snapshot_has_no_pagination_request(self):
        request = Transport(response([{"plays": 2, "movie": {"ids": {"trakt": 10}}},
                                      {"plays": 1, "movie": {"ids": {"trakt": 20}}}]))
        result = Client(request, "id", "token").watched_movies()
        self.assertEqual(result, (10, 20))
        self.assertEqual(request.calls[0][1], "/users/me/watched/movies")
        self.assertEqual(Client(Transport(response([])), "id", "token").watched_movies(), ())

    def test_watched_movies_rejects_partial_oversized_and_invalid_evidence(self):
        valid = {"plays": 1, "movie": {"ids": {"trakt": 10}}}
        invalid = [{}, {"plays": 0, "movie": {"ids": {"trakt": 10}}},
                   {"plays": True, "movie": {"ids": {"trakt": 10}}},
                   {"plays": 1, "movie": {"ids": {"trakt": True}}},
                   {"plays": 1, "movie": {"ids": {"trakt": -1}}},
                   {"plays": 1, "movie": {"ids": {"trakt": 2 ** 63}}},
                   {"plays": 1, "type": "episode", "movie": {"ids": {"trakt": 10}}},
                   {"plays": 1, "movie": []}]
        for body in ({}, [valid, valid], *([row] for row in invalid)):
            with self.subTest(body=body), self.assertRaises(ApiError):
                Client(Transport(response(body)), "id", "token").watched_movies()
        with self.assertRaisesRegex(ApiError, "result_limit"):
            Client(Transport(response([valid, valid])), "id", "token", max_items=1).watched_movies()
        for headers in ({"X-Pagination-Page": "1"}, {"x-pagination-page-count": "1"},
                        {"X-Pagination-Limit": "100"}):
            with self.subTest(headers=headers), self.assertRaisesRegex(ApiError, "invalid_pagination"):
                Client(Transport(Response(200, headers, [valid])), "id", "token").watched_movies()
        for status in (401, 403, 429, 500):
            request = Transport(Response(status))
            with self.subTest(status=status), self.assertRaises(ApiError):
                Client(request, "id", "token").watched_movies()
            self.assertEqual(len(request.calls), 1)

    def test_lists_deduplicate_and_preserve_ownership(self):
        request = Transport(response([item(12)]),
                            response([{"list": item(12)}, {"list": item(13)}]))
        lists = Client(request, "mock-client", "mock-token").lists()
        self.assertEqual([r.key for r in lists], ["trakt-list:12", "trakt-list:13"])
        self.assertEqual([(r.owner, r.writable) for r in lists],
                         [("me", True), ("synthetic-user", False)])
        self.assertEqual(request.calls[0][0], "GET")
        self.assertEqual(request.calls[0][1], "/users/me/lists?page=1&limit=100")
        self.assertEqual(request.calls[1][1], "/users/likes/lists?page=1&limit=100")
        self.assertEqual(request.calls[0][2]["Authorization"], "Bearer mock-token")

    def test_all_pages_are_collected_and_parameters_preserved(self):
        request = Transport(response([{"rank": 1}], 2, 1), response([{"rank": 2}], 2, 2))
        result = Client(request, "id", "token", page_size=1).list_items("me", 12)
        self.assertEqual(result, [{"rank": 1}, {"rank": 2}])
        self.assertEqual(request.calls[1][1], "/users/me/lists/12/items?extended=full&page=2&limit=1")

    def test_limits_and_malformed_pagination_never_return_partial_results(self):
        cases = [response([{}], 500), response([{}], "garbage"),
                 response([{}], 1, 2), response([{}]), response([{}], 0),
                 response([{}, {}], 1)]
        for reply in cases:
            with self.subTest(reply=reply):
                request = Transport(reply)
                with self.assertRaises(ApiError):
                    Client(request, "id", "token", page_size=1).paused()
                self.assertEqual(len(request.calls), 1)
        request = Transport(response([{}], 2, 1), response([{}], 2, 2))
        with self.assertRaisesRegex(ApiError, "result_limit"):
            Client(request, "id", "token", page_size=1, max_items=1).paused()

    def test_empty_and_invalid_list_data(self):
        request = Transport(response([], 0), response([]))
        self.assertEqual(Client(request, "id", "token").lists(), [])
        for body in ({}, ["invalid"], [{"ids": {"trakt": True}, "name": "invalid"}]):
            with self.assertRaises(ApiError):
                Client(Transport(response(body)), "id", "token").lists()

    def test_error_classes_and_no_implicit_retry(self):
        for status, kind in [(401, "reauthenticate"), (403, "unavailable"),
                             (404, "unavailable"), (420, "account_limit"),
                             (429, "rate_limit"), (500, "service")]:
            request = Transport(Response(status, {"Retry-After": "45"}, {"secret": "private-response"}))
            with self.assertRaises(ApiError) as caught:
                Client(request, "id", "private-token").paused()
            self.assertEqual(caught.exception.kind, kind)
            self.assertNotIn("private", str(caught.exception))
            self.assertEqual(len(request.calls), 1)
            if status == 429:
                self.assertEqual(caught.exception.retry_after, 45)

    def test_transport_errors_do_not_expose_response_or_credentials(self):
        def broken(*args):
            raise RuntimeError("mock-private-token")
        with self.assertRaises(ApiError) as caught:
            Client(broken, "id", "mock-private-token").settings()
        self.assertEqual(str(caught.exception), "Trakt request failed: transport")
        self.assertTrue(caught.exception.__suppress_context__)
        self.assertNotIn("sensitive", repr(Response(200, {}, {"token": "sensitive"})))
        self.assertNotIn("sensitive", repr(Client(broken, "id", "sensitive")))

    def test_retry_after_is_bounded_and_supports_http_date(self):
        now = datetime(2026, 11, 12, tzinfo=timezone.utc)
        self.assertEqual(retry_delay({"Retry-After": "Thu, 12 Nov 2026 00:00:30 GMT"}, now), 30)
        for raw, expected in [("garbage", 60), ("99999", 3600), ("-20", 1), (float("inf"), 60), (None, 60),
                              ("9" * 5000, 60), ([], 60)]:
            self.assertEqual(retry_delay({"Retry-After": raw}, now), expected)

    def test_missing_body_is_a_sanitized_response_error(self):
        class MissingBody:
            status = 200
            headers = {}
        for operation in (lambda c: c.settings(), lambda c: c.show_progress(1),
                          lambda c: c.season_episodes(1, 1), lambda c: c.paused()):
            with self.assertRaisesRegex(ApiError, "invalid_response"):
                operation(Client(Transport(MissingBody()), "id", "token"))

    def test_paths_and_headers_reject_injection_before_request(self):
        request = Transport()
        client = Client(request, "id", "token")
        for value in ["https://evil.invalid", "../x", "x/y", "x?y", "x%2Fy", "x\ny", True]:
            with self.assertRaises(ApiError):
                client.list_items(value, 1)
        with self.assertRaises(ApiError):
            Client(request, "id", "token\r\nInjected: header")
        self.assertEqual(request.calls, [])

    def test_progress_metadata_and_settings_are_bound_to_requested_show(self):
        request = Transport(response({"seasons": []}), response([]), response({"limits": {}}))
        client = Client(request, "id", "token")
        self.assertEqual(client.show_progress(42), {"show_id": 42, "progress": {"seasons": []}})
        self.assertEqual(client.season_episodes(42, 1), {"show_id": 42, "episodes": []})
        self.assertEqual(client.settings(), {"limits": {}})
        self.assertIn("/shows/42/progress/watched?", request.calls[0][1])
        self.assertEqual(request.calls[1][1], "/shows/42/seasons/1?extended=full")


if __name__ == "__main__":
    unittest.main()
