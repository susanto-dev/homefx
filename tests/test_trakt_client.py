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
