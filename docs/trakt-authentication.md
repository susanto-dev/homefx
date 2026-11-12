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

## Next implementation slice

1. Build device-login lifecycle against synthetic HTTP responses: pending,
   authorization, cancellation, expiration, denied/used/invalid codes and 429.
   Honor returned interval and expiry; never poll indefinitely.
2. Separate OAuth/data hosts, verify TLS and redact tokens/device codes from all
   logs and error messages. Keep public client identity separate from user tokens.
3. Define profile storage and a cross-invocation refresh lock. Replace access and
   refresh tokens atomically; refresh tokens are single-use. Treat ambiguous
   refresh failure conservatively and provide reauthentication. Profile backups
   can expose credentials; Kodi profile storage is not a secure vault.
4. Verify mocks for personal and liked list selection, pagination, ownership,
   restricted/private lists and account limits. Liked lists are not necessarily
   writable. Read account allowances; avoid retry loops on limit errors.
5. Keep episode metadata separate from watched progress and paused playback.
   Personal calendars are based on watched/watchlisted shows, not automatically
   the selected custom lists. Define that view explicitly before implementation.
6. Require real development-app device login and rotated-token refresh before
   enabling live account mode; then validate on the Android TV. Keep the existing
   preview synthetic until those gates are complete.

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
