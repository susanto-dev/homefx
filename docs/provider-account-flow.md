# Shared account interaction contract

`AccountFlow` accepts the existing Trakt or Real-Debrid session protocol. Its caller
supplies the session, UI, cancellation/wait callbacks, monotonic clock and a local
disconnect callback. It constructs no transport or Kodi screen and is not activated
by any preview route.

Use `Library.disconnect` for Trakt so account-bound list choices and invocation
cache are cleared with local credentials. Use `debrid_session.Session.disconnect`
for Real-Debrid. Both accept an expected generation and reject stale confirmations.
Provider-aware UI wording must accurately describe the relevant local cleanup.
Local disconnection does not revoke authorization remotely or erase profile backups.

The controller confirms replacement, issues a device code, shows only its user code
and canonical verification URL, and polls when the session permits. It bounds total
interaction time and waits in intervals no longer than one second. Transport calls
need their own bounded cancellation/timeouts; the controller cannot interrupt them.
Callback errors produce fixed outcomes without including request bodies, credentials,
filesystem paths or user codes. Both providers' explicit `session_changed` errors
preserve that outcome. Invalid or unknown failures remain failures.

## Provider-specific meaning

A Real-Debrid success means the user-bound grant was installed locally. It does not
prove subscription entitlement, account-library correctness, a playable source or
successful playback. No account/download request follows authorization automatically.
No public application secret is supplied to this controller or bundled in HomeFX.

Real-Debrid's unverified pending-authorization responses are not guessed from a status
code. The session may receive an explicit, reviewed pending-response classifier; no
classifier is supplied by this controller. Unrecognized 400/403 responses fail once
rather than retrying indefinitely or asserting a distinct denial event. Local device
code expiry remains an `expired` result. A provider's future verified denial contract
would need explicit upstream support before exposing a distinct denial result.

Cancellation and replacement reject late installs. Cleanup is tied to the attempted
generation so it cannot erase a newer account. A prompt failure attempts UI cleanup;
a close failure cannot undo an already committed authorization. Code display is an
intentional private UI action, never diagnostics or persistence.

Tests use real temporary private stores and sessions with fabricated OAuth responses.
They cover polling, refusal, cancellation, replacement, stale disconnects and cleanup.
No live credentials, Real-Debrid traffic, Kodi UI or TV acceptance is involved.
