# TMDB artwork and bounded cache

TMDB is the chosen artwork candidate. **It is not activated yet.** The owner has
not registered the application or accepted its API terms. This batch supplies a
provider-specific client and cache with fabricated tests; neither Kodi entry point
constructs them. There is no new login, network traffic, artwork download, menu or
background process. Existing Development lists and Trakt descriptions/ratings stay
usable. Public Preview remains synthetic.

## What is cached, and why

The cache stores only a validated movie/show TMDB ID, language, poster/backdrop
**paths**, timestamps and short-lived request coordination fields. Trakt list names,
account IDs, tokens, descriptions, ratings, watch state, resume and selections do
not enter it. The containing private directory still matters: a set of public title
IDs can reveal viewing interests. It belongs to the video add-on's own profile;
no account or program-add-on storage is imported.

The list parser retains an optional valid TMDB ID supplied by Trakt. It never
substitutes a title-text match or assumes a missing ID can be guessed. Movie, show
and language keys are distinct. TMDB response IDs must match the requested ID;
only bounded relative JPG/PNG paths are retained, not arbitrary URLs or response
bodies. Actual image sizes/base configuration and display attribution are later
activation requirements.

| State | Policy | Network behavior |
|---|---|---|
| Fresh artwork paths | Seven days from successful fetch | Read locally; no new lookup |
| Missing artwork / 404 | One-day negative result | Do not repeatedly query a missing poster |
| Stale artwork paths | Seven to thirty days, explicitly marked stale | Can be read locally; explicit refresh can replace them |
| Hard expiry | At thirty days, including repeated failures | Remove on next cache operation; do not serve |
| Invalid result/network error | Keep original successful age | Stop the batch and share a cooldown; no automatic retry |
| Rate limited | Respect numeric or HTTP-date Retry-After, including waits longer than an hour | No early retry or sleep loop |
| Unauthorized (401/403) | Purge cached provider content and impose cooldown | Stop; credential/service access needs attention |
| Clock moves backward | Invalidate paths and active requests; preserve remaining cooldown conservatively | Do not extend cache life from an old timestamp |
| Explicit clear | Remove only this cache and invalidate outstanding results | No token deletion; no bypass of rate-limit cooldown |

These are conservative starting policies, not proof that a poster never changes
within seven days. There is no push notification from TMDB here: discovering a
change requires a subsequent successful request. Reads and failed refreshes do not
reset the original successful-fetch timestamp. Stale content must not be described
as newly verified. A future manual artwork refresh can clear the relevant cache and
fetch again, subject to the same request limits.

Expiry maintenance runs when the add-on uses the cache; nothing runs while Kodi is
closed. A real cache cannot be purged by an inactive process. Live use therefore
also needs an explicit provider-disable/purge path and clear retention guidance.

## Storage and concurrency

The cache has at most 1,000 rows and a 1 MiB SQLite database. The DELETE-mode rollback
journal is bounded separately to 1 MiB plus 64 KiB when inspected; SQLite cache memory
is set to 128 KiB, with memory mapping disabled. These are bounds on this path cache,
**not** a cap on all Kodi memory, image files or Kodi's texture database. The least
recently used entries are evicted; access does not extend freshness or hard expiry.
A 2,000-key read batch uses one transaction. An all-fresh refresh also uses one
transaction, not one write/commit per title. Unsafe paths, linked/nonregular files,
foreign databases and overlarge files fail closed with fixed errors.

Only one refresh claim is active per local cache. HTTP runs outside SQLite locks,
so another invocation can still read cached paths. A claim expires after fifteen
seconds for abrupt-process recovery. Completion after expiry, clear or replacement
cannot overwrite a newer result. Observed rate limits and authorization failures
still apply even if their content lease expired; a shorter late cooldown cannot
replace a longer observed wait. A crashed request may still be in progress until
its operating-system I/O returns; lease recovery is not cancellation of that I/O.
Different devices/profiles are not coordinated.

Explicit warm-up performs at most twenty network attempts per call, serially.
The client has a five-second request budget and three-second socket operations;
platform DNS can exceed Python socket deadlines. Cancellation is checked around
requests. This is not a five-second bound for an entire twenty-request warm-up.
No widget invokes this warm-up automatically in the current candidate.

## Seamless first-use design still to finish

A cache-only widget must not launch a hundred metadata requests just because it
opened. Once registration and credential delivery are resolved, prepare artwork in
a cancellable foreground list-selection/browsing flow, with visible progress and a
bounded work budget. Use existing paths immediately on subsequent widget reads;
unprepared or expired items retain the original placeholder. Decide the exact
staged first-load behavior on the TV before enabling automatic refresh. Do not add
an always-running service, unattended thread or periodic full-library scan merely
to fill the cache.

Kodi should request modest poster/backdrop sizes, not original images. **Image-byte
caching is not implemented by this path cache.** Before enabling remote artwork,
resolve image size/configuration, image retention and Kodi texture-cache behavior.
Do not claim the 1 MiB bound controls Kodi's own image cache, or delete other add-ons'
textures to enforce it. Account/view guards must still run before attaching cached
artwork to a selected-list result. A cache hit does not authorize a list read.

## Evidence and performance measurements

Run `python tools/benchmark_tmdb_cache.py` for an isolated fabricated 100-title
workload. It reports counts, database bytes and development-machine timings only;
all data is temporary. Five twenty-request warm-up calls produce exactly 100 fake
fetches, then zero fetches for a warm refresh. A reopen retains paths. The automated
suite covers freshness boundaries, negative caching, shared cooldowns, HTTP framing,
wrong identities, unsafe URLs, eviction, cancellation, clock rollback, concurrent
requests, clear during fetch and abrupt-process lease recovery.

One local run on 14 November 2026 measured 28,672 database bytes, 0.457 seconds for
fabricated filling, 0.0025 seconds for a 100-title warm read, 0.0021 seconds for a
no-op warm refresh and 0.0140 seconds for five such row reads. These exclude real network latency, JPEG/PNG transfer/decoding,
Kodi rendering and TV storage. They do not establish an improvement on Android TV.
No fixed wall-time assertion is added to CI.

After activation, measure first load, repeat load, full Kodi restart and multiple
skin rows separately. Record metadata request counts separately from image traffic,
loading time, focus/Back responsiveness, cancellation and cache size. Test missing
artwork, offline stale fallback, hard expiry and explicit refresh using synthetic
fixtures where possible; do not damage live tokens or change the TV clock.

## Owner setup and activation gates

1. Register a developer application through [TMDB account API settings](https://www.themoviedb.org/settings/api)
   and review/accept its current terms yourself. Use an accurate description of
   HomeFX as a non-commercial Kodi metadata/artwork project; do not claim affiliation.
2. Report registration/terms status only. Do not paste keys or read-access tokens in
   chat, screenshots, issues or commits. No TMDB value is needed in GitHub yet.
3. Review private device-side credential delivery before live wiring. An application
   read token is still a credential; putting it in a GitHub secret and then a public
   ZIP exposes it. No packaged shared token is an approved solution here.
4. Add the approved TMDB logo and required prominent non-endorsement notice in
   About/Credits before displaying TMDB artwork. Verify exact asset provenance and
   the current terms; do not modify the HomeFX logo to imply endorsement.
5. Complete image retention and cancellable first-load UI, then deliberately test
   one Development list on TV. No paid plan or public/Production activation is implied.

No more TMDB-only abstractions are needed before registration and credential/image
lifecycle decisions. Real-Debrid, playback, remote writes and scrobbling remain
outside this batch.

## Authoritative references checked on 14 November 2026

- [API terms](https://www.themoviedb.org/api-terms-of-use), section 1.C, prohibit
  caching API information longer than six months; section 1.D requires purging on
  licence termination. The path cache's thirty-day hard expiry is shorter, but
  runtime cleanup and image-cache behavior still require the activation work above.
- [API FAQ](https://developer.themoviedb.org/docs/faq): non-commercial use is free
  with attribution; commercial use requires a separate agreement. No new cost is
  incurred by this inactive implementation.
- [Application authentication](https://developer.themoviedb.org/docs/authentication-application):
  API read token in the Authorization Bearer header; it is not placed in URLs.
- [Image basics](https://developer.themoviedb.org/docs/image-basics): configuration
  supplies the base URL and supported sizes, combined with a metadata image path.
- [Rate limiting](https://developer.themoviedb.org/docs/rate-limiting): legacy limits
  were removed; the approximate current ceiling can change and 429 must be respected.

Only interface documentation was consulted. No third-party implementation, actual
film artwork, metadata dataset or logo is copied into this batch.
