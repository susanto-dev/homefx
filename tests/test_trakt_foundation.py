"""Offline contract test across auth, private state, read API and view layers."""
from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "addons/plugin.video.homefx"))
from resources.lib.trakt_auth import DeviceLogin, refresh_tokens
from resources.lib.trakt_tokens import TokenStore
from resources.lib.trakt_client import Client, Response
from resources.lib.trakt_views import episodes, widget_order


@unittest.skipUnless(os.name == "posix", "Private token store requires POSIX permissions")
class FoundationTests(unittest.TestCase):
    def test_login_rotation_read_and_episode_view_without_network(self):
        clock = [0.0]
        oauth_paths = []

        def oauth(method, path, body):
            self.assertEqual(method, "POST")
            self.assertNotIn("client_secret", body)
            oauth_paths.append(path)
            if path == "/oauth/device/code":
                return Response(200, body={"device_code": "synthetic-device-code",
                                          "user_code": "DEMO-CODE",
                                          "verification_url": "https://trakt.tv/activate",
                                          "expires_in": 600, "interval": 5})
            if path == "/oauth/token":
                self.assertEqual(body["refresh_token"], "synthetic-refresh-one")
                self.assertEqual(body["redirect_uri"], "https://example.invalid/callback")
                suffix = "two"
            else:
                self.assertEqual(path, "/oauth/device/token")
                suffix = "one"
            return Response(200, body={"access_token": "synthetic-access-" + suffix,
                                      "refresh_token": "synthetic-refresh-" + suffix,
                                      "token_type": "bearer", "created_at": 1000,
                                      "expires_in": 3600})

        login = DeviceLogin(oauth, "synthetic-client", clock=lambda: clock[0])
        login.begin()
        self.assertEqual(login.poll(), "pending")
        clock[0] = 5.0
        self.assertEqual(login.poll(), "authorized")
        with tempfile.TemporaryDirectory() as profile:
            store = TokenStore(profile)
            store.install(login.tokens)
            generation = store.snapshot().generation
            rotated = refresh_tokens(store, oauth, "synthetic-client",
                                     "https://example.invalid/callback", generation)
            self.assertEqual(store.snapshot().tokens, rotated)
            self.assertIsNone(refresh_tokens(store, oauth, "synthetic-client",
                                            "https://example.invalid/callback", generation))
            data_paths = []

            def api(method, path, headers, body=None):
                self.assertEqual(method, "GET")
                self.assertEqual(headers["Authorization"], "Bearer synthetic-access-two")
                self.assertIsNone(body)
                data_paths.append(path)
                if "/seasons/" in path:
                    return Response(200, body=[
                        {"ids": {"trakt": 101}, "title": "Demo first", "season": 1,
                         "number": 1, "first_aired": "2026-11-01T00:00:00Z"},
                        {"ids": {"trakt": 102}, "title": "Demo next", "season": 1,
                         "number": 2, "first_aired": "2026-11-03T00:00:00Z"},
                        {"ids": {"trakt": 103}, "title": "Demo future", "season": 1,
                         "number": 3, "first_aired": "2026-11-20T00:00:00Z"}])
                if "/progress/" in path:
                    return Response(200, body={"seasons": [{"number": 1, "episodes": [
                        {"number": 1, "completed": True},
                        {"number": 2, "completed": False}]}]})
                self.assertTrue(path.startswith("/sync/playback?"))
                return Response(200, body=[{
                    "type": "episode", "show": {"ids": {"trakt": 10}},
                    "episode": {"ids": {"trakt": 102}}, "progress": 30,
                    "paused_at": "2026-11-11T12:00:00Z"}])

            client = Client(api, "synthetic-client", store.snapshot().tokens.access_token)
            rows = episodes(client.season_episodes(10, 1), client.show_progress(10),
                            client.paused(), now=datetime(2026, 11, 12, tzinfo=timezone.utc))
            self.assertEqual([r["trakt_id"] for r in rows], [101, 102, 103])
            self.assertEqual([r["trakt_id"] for r in widget_order(rows)], [102, 103, 101])
            self.assertEqual([r["trakt_id"] for r in rows if r["aired_unwatched"]], [102])
            self.assertEqual(rows[1]["progress"], 30)
            self.assertEqual(rows[2]["release_status"], "upcoming")
            self.assertTrue(all("playable" not in row for row in rows))
            store.disconnect()
            self.assertIsNone(store.snapshot().tokens)
            self.assertEqual(len(data_paths), 3)
        self.assertEqual(oauth_paths, ["/oauth/device/code", "/oauth/device/token", "/oauth/token"])
