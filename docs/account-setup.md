# Preparing a Trakt development connection

The 0.17.1 Kodi preview still uses synthetic data. Its **Trakt connection setup**
menu only explains the current state; it does not collect credentials or contact
Trakt. Transport/session code is included for development and offline tests, but
no live connection route is enabled. Do not paste tokens into plugin URLs or source.

## Owner input for the read-only milestone

Live access remains blocked until the owner supplies the registered **public client
ID**, **exact registered redirect URI**, and Development/Production status, then
authorizes a bounded device test after the gates below. These public configuration
values do not prove registration validity by themselves. No real-account test belongs
in CI. Do not send a client secret, token, device code, private list/history export,
profile path, or application screenshot containing secret fields.

First return only HomeFX/Kodi versions and the fixed **Device readiness** / **Test
private storage** results from the [staged TV checklist](testing-on-tv.md). The owner
can select personal or liked lists privately on the device after activation; list
names or contents are not needed in chat or a public issue.

## Application registration

Read the current [Trakt registration guide](https://developer.trakt.tv/docs/create-an-app)
and [OAuth guide](https://developer.trakt.tv/docs/authentication-oauth), then register
a development application in your own account when ready. Record its **public client
ID** and the **redirect URI actually registered**. HomeFX does not need a client
secret, and there is no configuration field for one. Do not publish application
screenshots containing secret values. No application is registered by this project.

The current device-token contract permits a public client; the refresh contract
requires a matching redirect URI. A device-issued refresh must be verified with
your registration before live mode can be called supported. Do not assume an
invented URI or an omitted URI works. This does not require running a callback
server, always-on service or Android application.

Rechecked against the official guide on 2026-11-13: creating an application requires
a verified GitHub account. Development permits the owner and up to 16 invited users;
apps for personal or small-group use can stay in Development. The guide allows any
redirect URI for Development testing, but HomeFX still needs the actual configured
value rather than a guessed default.

Broader distribution requires separate Production access and a separate client ID,
including privacy and nonendorsement requirements. The guide's production HTTPS
redirect restriction is stated for PKCE applications; do not infer device-flow
production approval from a Development test. Recheck the current service terms before activation.
No paid plan or service is provisioned in this batch; basic proposed use is not
documented as requiring Premium. Changed terms or a paid option need separate review.

## Activation gates

1. Verify the registered identity and public-client contracts. Use an explicit
   development test flow before making a public account-connect menu available.
2. Test device-code authorization, denial, expiry and cancellation; confirm the
   supplied URL is the legitimate Trakt verification page. Never put a user code
   in logs or a public issue. Authorization requires the user's action on Trakt.
3. Verify successful single-use refresh rotation and interrupted-refresh recovery.
   Test only fabricated failures in automated CI; do not put real accounts there.
4. Check Kodi's Python/SQLite availability, private profile permissions and TLS trust
   on the actual Android/Google TV. Measure cancellation and slow/offline behavior.
5. Define account-switch/disconnect UI and service-side revocation guidance before
   enabling live mode. Local disconnect is not remote revocation or backup erasure. Library disconnect
   also clears all saved list choices in this local profile.
6. Verify selected personal/liked lists, read-only progress and UTC date handling.
   Watch-history/list writes, playback, subtitles and scrobbling remain separate work.

## Privacy and recovery

Tokens belong in the dedicated private Kodi profile store, never Kodi settings,
widget paths, repository files or exported diagnostics. The store is unencrypted:
other code running as Kodi and profile backups may expose it. Exclude the profile
from shared backups/logs. Do not send a full Kodi backup to troubleshoot a connection.

A refresh response can be lost after Trakt consumes the old token. HomeFX then
requires login again rather than retrying that token. A competing invocation can
report that refresh is busy. Disconnect/new login invalidates stale completion and
cached data. Clearing active local state does not revoke a token remotely; when
testing a real account, revoke application authorization in Trakt as appropriate.

For troubleshooting, record only the package checksum, Kodi/Android versions,
safe error category and steps. Never include authorization headers, tokens, device
codes, private list contents or watch history. See [security](security.md) and
[authentication contracts](trakt-authentication.md).

The new action contracts do not enable live writes. Before wiring them into UI,
verify confirmed/already-present/not-found/error outcomes with the registered app,
review how to reconcile an uncertain result, and check account-switch behavior.
Do not add automatic retries for mark-watched: duplicate plays can be recorded.
The local preview's remove/unwatched actions are demonstrations, not remote deletions.

## Assembly and dialog preparation

The inactive [service runtime factories](service-runtime.md) join private stores,
shared request limits and bounded transports. The [shared account controller](provider-account-flow.md)
and [injected dialog adapter](account-ui.md) support development tests without adding
a live Kodi route. Their existence does not satisfy the registration or device gates
above. Public client identity syntax is checked, not service registration validity.
No client secret should be added to settings or source to bypass a failed grant.
