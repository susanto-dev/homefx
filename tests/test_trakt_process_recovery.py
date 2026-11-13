"""Abrupt refresh-process exits use temporary stores and fabricated grants only."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "addons/plugin.video.homefx"
sys.path.insert(0, str(ADDON))
from resources.lib.trakt_auth import TokenSet, refresh_tokens
from resources.lib.trakt_tokens import TokenStore


# Exit without exception handling, context-manager cleanup or atexit handlers.
# The callback boundaries stand in for an unknown provider outcome and a received
# replacement grant. Neither mode creates a network connection.
CHILD = r'''
import os
import socket
import sys
from types import SimpleNamespace

sys.path.insert(0, sys.argv[1])
from resources.lib.trakt_auth import refresh_tokens
from resources.lib.trakt_tokens import TokenStore

def forbidden_network(*args, **kwargs):
    raise AssertionError("network forbidden")
socket.create_connection = forbidden_network

class InterruptedStore(TokenStore):
    def complete_refresh(self, claim, tokens):
        assert sys.argv[3] == "before_commit"
        assert tokens.access_token == "synthetic-replacement-access"
        assert tokens.refresh_token == "synthetic-replacement-refresh"
        os._exit(23)

def request(method, path, body):
    assert method == "POST" and path == "/oauth/token"
    assert body["refresh_token"] == "synthetic-original-refresh"
    if sys.argv[3] == "during_request":
        os._exit(23)
    return SimpleNamespace(status=200, body={
        "access_token": "synthetic-replacement-access",
        "refresh_token": "synthetic-replacement-refresh",
        "token_type": "bearer", "created_at": 1000, "expires_in": 3600})

store = InterruptedStore(sys.argv[2], clock=lambda: 1000, claim_ttl=10)
refresh_tokens(store, request, "synthetic-client", "urn:homefx:synthetic", 1)
raise AssertionError("interruption was not reached")
'''


class ProcessRecoveryTests(unittest.TestCase):
    def test_abrupt_refresh_exit_never_replays_and_recovers_with_new_login(self):
        for boundary in ("during_request", "before_commit"):
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as profile:
                now = [1000]
                store = TokenStore(profile, clock=lambda: now[0], claim_ttl=10)
                store.install(TokenSet("synthetic-original-access",
                                       "synthetic-original-refresh", 2000))
                child = subprocess.run(
                    [sys.executable, "-c", CHILD, str(ADDON), profile, boundary],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, check=False)
                self.assertEqual(child.returncode, 23)
                self.assertEqual(child.stdout, b"")
                self.assertEqual(child.stderr, b"")

                calls = []

                def must_not_request(*args):
                    calls.append(True)
                    raise AssertionError("abandoned refresh must not be replayed")

                # A new process/invocation can observe the durable claim, but
                # cannot reclaim its old token even before the claim expires.
                reopened = TokenStore(profile, clock=lambda: now[0], claim_ttl=10)
                for when, expected_state in ((1000, "refreshing"),
                                             (1009, "refreshing"), (1010, "reauth")):
                    now[0] = when
                    snapshot = reopened.snapshot()
                    self.assertEqual(snapshot.state, expected_state)
                    self.assertIsNone(snapshot.tokens)
                    self.assertIsNone(refresh_tokens(reopened, must_not_request,
                        "synthetic-client", "urn:homefx:synthetic", snapshot.generation))
                self.assertEqual(calls, [])

                # Explicit login replaces the failed scope through the same
                # generation-checked store operations used by Session. A crash
                # must neither revive old tokens nor permanently poison storage.
                generation = reopened.snapshot().generation
                self.assertTrue(reopened.disconnect(expected_generation=generation))
                replacement = TokenSet("synthetic-new-login-access",
                                       "synthetic-new-login-refresh", 5000)
                self.assertTrue(reopened.install(replacement,
                                                expected_generation=generation + 1))
                final = TokenStore(profile, clock=lambda: now[0]).snapshot()
                self.assertEqual(final.state, "ready")
                self.assertEqual(final.tokens, replacement)
                self.assertEqual(final.generation, generation + 2)
                self.assertIsNone(refresh_tokens(reopened, must_not_request,
                    "synthetic-client", "urn:homefx:synthetic", generation))
                self.assertEqual(calls, [])
