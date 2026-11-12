# Trakt authentication feasibility

Reviewed 2026-11-12. Status: supported by current documented contracts; no live
login, token refresh, account access, or Android TV test has been performed.

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

Development app registration and the public client ID remain outstanding. Current
registration guidance allows the owner and up to 16 invited users in Development;
broad access requires separate Production access. Production registration calls
for privacy documentation and a Trakt nonendorsement notice. Premium is not stated
as mandatory for the proposed basic functionality. No account or paid service was
created during this investigation.

## Implemented mocked foundations

The 0.2.0 candidate implements caller-driven device polling, terminal/cancellation
states, token validation, and refresh orchestration with injected responses only.
The caller supplies the public client ID and registered redirect URI; neither is
preconfigured. There is no client-secret parameter. No live transport or Kodi
account screen exists, so these modules cannot independently contact a service.

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

## Gates before live account access

1. Register a development application and verify the documented public-client flow
   using its client ID and registered redirect URI. Never provide a client secret.
2. Implement and independently review a TLS-verifying transport with host binding,
   redirect rejection, byte/time bounds, cancellation and sanitized diagnostics.
   Injected callbacks are a test boundary, not proof of those network protections.
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
snapshot; a missing snapshot remains unknown. Live responses still need validation.
