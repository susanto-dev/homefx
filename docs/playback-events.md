# Playback observations

`PlaybackEvents` is an inactive in-memory observer for one explicitly correlated
playback attempt. It does not construct a Kodi player, stop playback, call a service,
store history, resume a title or start the next episode. The current entry point
never constructs it. `PlaybackAttempt.ACCEPTED` still means only that a dispatch
callback accepted the request; it must not be translated into `av_started`.

## Input contract

Construct with a positive integer attempt ID, the account's nonnegative credential
generation, cancellation/current-generation callbacks and an injected monotonic
clock. IDs are local correlation values, not tokens, URLs or title names. A future
adapter must allocate a new attempt ID per explicit dispatch and correlate every
callback to that attempt before forwarding it. Never label a delayed callback from
old media with the new attempt ID. The observer cannot infer media identity from a
Kodi callback, and sequence numbers do not authenticate their source.

Call `observe(attempt_id, generation, sequence, event, position=None, duration=None)`
with a strictly increasing positive sequence (at most `2**63 - 1`). The adapter must
serialize callback order. Duplicate/older sequences or different attempt/generation
values are rejected as stale. Invalid events do not advance the accepted sequence.
Reentrant/concurrent observations return `busy` without applying an event. The adapter
must not silently reorder callbacks when deciding how to handle that result.

| Event | Accepted from | Result |
|---|---|---|
| `av_started` | waiting | playing; no invented position |
| `sample` | playing or paused | validated position/duration observation |
| `paused` | playing | paused |
| `resumed` | paused | playing |
| `ended` | playing or paused | ended; preserves last observed sample |
| `stopped`, `error` | waiting, playing or paused | terminal observation |

A sample's position is finite seconds between zero and seven days. Duration is
`None` when unknown, otherwise finite positive seconds within that same bound;
position cannot exceed a known duration. Lower positions are legitimate seeks.
Each sample replaces both values, so an unknown duration never keeps an earlier
percentage denominator. Non-sample events cannot carry position/duration payloads.

## Guarded results

`snapshot()` returns a frozen detached `Observation(state, position, duration,
progress, watched)`. Progress is a percentage only after an AV-start event and a
valid sample with known duration. It remains unknown without that evidence.
`watched` is always `None`, including after a 100% sample or `ended`: an event alone
is not a watch-history policy or proof of successful completion. An ended event does
not synthesize a final sample. Last samples after stop/error/end are observations,
not instructions to persist or replay them.

The configurable startup timeout is 1–300 seconds (default 30), checked only while
waiting for AV start. It does not expire a long film after 30 seconds. Guards run on
valid incoming events and snapshots; there is no background timer. Cancellation,
changed account generation, invalid/backward clock readings or failing callbacks
invalidate the observer and clear its samples. Terminal states cannot start another
playback. A previously returned detached snapshot cannot be revoked; a caller must
recheck account/attempt identity atomically before any future external action.

Callbacks must be bounded trusted code. The in-memory lock serializes this observer,
not external account state or other processes, and cannot interrupt a blocking
callback. A busy snapshot raises a fixed error. Cancellation/expiry invalidates
observations; it does **not** establish that the actual player has stopped.
Representations and fixed errors omit attempt IDs and callback error text. Snapshots
contain no URLs, titles or credentials, but progress is still private usage data and
must not be exported to public logs.

## Acceptance still required

Tests feed fabricated events, clocks and account changes. They cover missing AV
start, duplicate/late events, seeks, unknown duration, pause/resume transitions,
terminal states, cancellation, startup expiry and callback failures. They are not
Kodi callback, playback, subtitle, resume or scrobbling tests.

A future adapter still needs real Kodi callback correlation and TV validation.
Resume persistence, completion thresholds, scrobbling ownership and automatic next
playback remain separate decisions. No observer result initiates those operations.
