# Preparing a Trakt development connection

The 0.9.0 Kodi preview still uses synthetic data. Its **Trakt connection setup**
menu only explains the current state; it does not collect credentials or contact
Trakt. Transport/session code is included for development and offline tests, but
no live connection route is enabled. Do not paste tokens into plugin URLs or source.

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

Development registration currently permits the owner and up to 16 invited users.
Broader distribution requires separate Production approval, including privacy and
nonendorsement requirements. Recheck the current service terms before activation.
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
