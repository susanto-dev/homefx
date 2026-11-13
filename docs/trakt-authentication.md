# Trakt authentication feasibility

Rechecked 2026-11-13. Status: supported by current documented contracts; no live
login, token refresh or account access has succeeded. The target TV passed the
Development test storage check; the latest connection attempt received HTTP status
403 before a code appeared. Successful authorization remains unverified.

## Proposed path

Use device-code authentication directly from Kodi. The user authorizes on Trakt's
verification page using a phone or computer. HomeFX needs no separate server or
Android application and must not ship a client secret. OAuth traffic goes to
`https://auth.trakt.tv`; Standard data requests go to `https://api.trakt.tv`.

The current device-token schema accepts code and client_id; client_secret is
optional and deprecated. Refresh also allows omission of a client secret. However,
the refresh base schema requires redirect_uri matching the application settings.
The documentation does not explicitly exempt device-issued tokens. Register an
appropriate URI and verify secret-free refresh with a real device-issued token
before calling this integration complete. Do not invent a URI or assume omission
works. The device-code flow itself does not require a callback server.

The owner confirmed the registered Development public client ID and redirect match
the configured variables; service-side registration and grant acceptance remain unverified. Current
registration guidance requires a verified GitHub account, allows the owner and up
to 16 invited users in Development, and allows any redirect URI for Development
testing. The actual configured redirect must still be supplied and verified. Personal
or small-group applications may remain in Development; broad access requires a
separate Production application and client ID. Production registration calls
for privacy documentation and a Trakt nonendorsement notice. Premium is not stated
as mandatory for the proposed basic functionality. No account or paid service was
created during this investigation.

## Activation address compatibility and the observed failure

The official device-code documentation at
[revision 226f4fc5a5d90b6d3810b60f1ec6fe7e48e86e6c](https://github.com/trakt/trakt-api/blob/226f4fc5a5d90b6d3810b60f1ec6fe7e48e86e6c/projects/api/src/contracts/oauth/index.ts)
names `https://auth.trakt.tv/activate` as the hosted activation page. The earlier
HomeFX parser and dialog accepted only the legacy host/address. An actual parser
call with a fabricated successful response using the current address failed before
code display. This is a reproduced compatibility bug. The later TV report shows a separate
403 request rejection before an activation URL could be validated.

Published 0.17.5 shares an exact allowlist between response validation and the
code dialog: `https://auth.trakt.tv/activate` and `https://trakt.tv/activate`. It
preserves the accepted URL and rejects lookalikes, arbitrary paths, query strings,
fragments, user information and explicit ports. No redirect following, TLS bypass
or client secret is introduced. Only original validation code changes; no upstream
implementation is copied.

The separate Development test adds invocation-only fixed failure stages/categories
and a bounded response-status value. It does not display response bodies, exception
text or credentials. The local limiter can generate 429 only; the observed 403 came from the HTTP
response path. A generic request failure can still involve network, TLS or a local
request guard and does not identify a specific cause.

## Required request headers and the 403 follow-up

The current [required-header guidance](https://github.com/trakt/trakt-api/blob/226f4fc5a5d90b6d3810b60f1ec6fe7e48e86e6c/projects/developer/src/lib/guides/required-headers.md)
and [authentication guidance](https://github.com/trakt/trakt-api/blob/226f4fc5a5d90b6d3810b60f1ec6fe7e48e86e6c/projects/developer/src/lib/guides/authentication-oauth.md)
require JSON Content-Type, a User-Agent, `trakt-api-key` containing the app's public
client ID, and `trakt-api-version: 2`. Earlier HomeFX OAuth requests sent only
Content-Type and Accept. The 0.17.6 candidate adds the missing headers across device
issuance, token polling and refresh. Existing API requests also gain the fixed,
honest user agent `HomeFX (+https://github.com/susanto-dev/homefx)`.

The public ID in the OAuth header matches that request's `client_id` body field.
No client secret or bearer token is added to device-code issuance. The fixed OAuth
host remains `auth.trakt.tv`; Standard data requests remain on `api.trakt.tv`.
Existing request bounds, TLS verification, redirect rejection and no-retry behavior
are unchanged. Tests inspect fabricated HTTP bytes, not live account traffic.

The [status-code guide](https://github.com/trakt/trakt-api/blob/226f4fc5a5d90b6d3810b60f1ec6fe7e48e86e6c/projects/developer/src/lib/guides/status-codes.md)
associates 403 with an invalid API key or unapproved app. Missing headers are a
confirmed contract mismatch and plausible explanation, not proof of the TV cause.
If a single explicit retry still returns 403, the owner must inspect app status,
public identity and allowed-user access privately. An upstream gateway may also
reject requests. Do not infer that a paid plan, Production registration, alternate
endpoint or foreign application identity is required. Current
[registration guidance](https://github.com/trakt/trakt-api/blob/226f4fc5a5d90b6d3810b60f1ec6fe7e48e86e6c/projects/developer/src/lib/guides/create-an-app.md)
permits the owner and up to 16 invited users in Development; personal/small-group
use can remain there. Follow the [bounded retry](development-device-test.md#retry-after-the-0176-candidate-is-published).

## Implemented mocked foundations

The 0.4.0 candidate retains caller-driven device polling, terminal/cancellation
states, token validation, and refresh orchestration with injected responses only.
The caller supplies the public client ID and registered redirect URI; neither is
preconfigured. There is no client-secret parameter. A fixed-host HTTPS transport
is implemented but not wired to Kodi account actions; the new setup menu provides
information only. Tests never supply a real application identity or contact Trakt.

Token state uses a dedicated SQLite file below a supplied private profile directory.
Short transactions persist refresh ownership before sending a request and clear
the old token pair from the active row. Only the matching claimant can install the
new pair. Another invocation returns busy rather than retrying the old refresh
token. Failed, timed-out or abandoned refresh requires login again. Disconnect or
a new login invalidates an old in-flight completion. This conservative behavior can
require another login after a temporary network fault; it avoids replaying a
single-use refresh token. SQLite/permissions support on the actual TV is unverified.

Read API foundations cover personal/liked lists, list items, episode metadata,
show progress, paused playback and account settings. They enforce bounded results
and surface service/rate/account-limit errors without an automatic retry loop.
Liked lists are not assumed writable. View normalization is separate from API
requests and joins metadata, watched status and pause records by stable identity.
No Trakt write, scrobbling, persistent metadata cache or live list widget is enabled.
Optional saved selections now bind to verified stable user UUID. Explicit single-item
action contracts are tested with fabricated responses and remain unwired in Kodi.
Session/Library now coordinate these reads with expiry checks, account-generation
guards and a bounded invocation-memory cache. See [architecture](architecture.md)
for cache invalidation and [account setup](account-setup.md) for activation gates.

## Gates before live account access

1. Register a development application and verify the documented public-client flow
   using its client ID and registered redirect URI. Never provide a client secret.
2. Review and verify the implemented TLS transport with the registered application
   and on the device: host binding, redirect rejection, byte/time bounds, cancellation
   and sanitized diagnostics. Mocked connection/socketpair tests are not evidence
   of real network behavior. OS DNS resolution remains outside socket deadlines.
3. Add explicit connect/disconnect/account-switch UX and a revocation policy. Keep
   tokens out of widget routes, exported logs, backups and packaged artifacts.
4. Validate real device login and rotated-token refresh; check cancelled/expired
   attempts and interrupted refresh recovery. Then repeat on Android/Google TV,
   recording interpreter and SQLite availability without recording token values.
5. Choose actual lists/views and verify list ownership, response pagination and
   account limits against real API responses. Selected custom lists do not
   automatically define a personal calendar. Movie release region/type remains a
   product choice; unknown dates must not be treated as already released.
6. Connect live read views only after those gates; keep watch-history/list writes
   and playback under separate acceptance criteria.

No playback or scrobbling claims follow from successful Trakt login. Umbrella
handoff remains a separate test gate. Aired/released does not imply playable.

## Primary sources

The earlier contract review used official repository revision
`030a5e3cb6aacb11508f250865c0b907ab17b2ed` for the device-token, optional-secret,
refresh and base-field links below. The activation-address correction above uses
later revision `226f4fc5a5d90b6d3810b60f1ec6fe7e48e86e6c`, checked on 2026-11-13.
These are published requirements, not verification of the owner's registered
application, actual grants, rotated refreshes or device compatibility.

- [Authentication](https://developer.trakt.tv/docs/authentication-oauth)
- [API hosts](https://developer.trakt.tv/docs/api-url)
- [App registration](https://developer.trakt.tv/docs/create-an-app)
- [Personal calendars](https://developer.trakt.tv/docs/about-calendars)
- [Rate limits](https://developer.trakt.tv/docs/rate-limiting)
- [Account limits](https://developer.trakt.tv/docs/user-account-limits)
- [Device token schema](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/oauth/schema/request/deviceTokenRequestSchema.ts)
- [Optional client-secret schema](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/oauth/schema/request/clientSecretSchema.ts)
- [Refresh schema](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/oauth/schema/request/tokenRefreshSchema.ts)
- [Refresh base fields](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/oauth/schema/request/tokenBaseSchema.ts)

These sources establish the intended API contract, not observed integration
success. Recheck current contracts when implementing; no upstream source code is
copied into HomeFX.

Read API pagination contracts were checked against the same official snapshot:
[personal lists/items](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/users/subroutes/userLists.ts),
[liked lists](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/users/index.ts),
and [paused playback](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/sync/index.ts).
A full page without pagination headers fails conservatively instead of presenting
an incomplete result as complete. Movie watched IDs must be supplied from a complete
snapshot; a missing snapshot remains unknown. The 0.8 library obtains a bounded
complete snapshot for movie list joins; see [movie history](movie-history-contract.md).
Live responses still need validation.

## Explicit actions and identity

The [user settings contract](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/users/index.ts)
describes user.ids.uuid as globally unique and usable for local identification. It is
an opaque service string, not assumed to be an RFC UUID or replaced by username.
Saved list IDs are loaded only after this identity is verified for the current token
generation. Refresh preserves choices for that identity; different accounts remain
separate. Explicit library disconnect clears saved choices for the entire local profile.

The history action adds one movie/episode play with an explicit UTC timestamp.
Movie-list addition requires an owned-list reference; future release dates are not
an impediment to organizing metadata in a list. Neither action establishes playable
sources. Responses must confirm counts and item identity; HTTP success alone is not
accepted as confirmation. Uncertain writes are never replayed automatically. No remote
mark-unwatched/history-removal action is offered, because deleting history has broader
semantics than a local preview flag. See security.md for failure/retry handling.

Primary action contracts at the reviewed official snapshot:
[history endpoint and duplicate-play warning](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/sync/index.ts),
[history response schema](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/sync/schema/response/historyResponseSchema.ts),
[personal-list endpoint](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/users/subroutes/userLists.ts),
and [list-add response schema](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/_internal/response/listAddResponseSchema.ts).
These establish intended contracts, not observed service integration success.
