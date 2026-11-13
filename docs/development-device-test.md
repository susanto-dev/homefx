# Bounded Development Trakt test on Kodi

**This is a separate experimental test add-on, not live mode for HomeFX Preview.**
HomeFX Preview 0.17.6 and repository 0.2.0 are published. PR #34 merged as
`e860684c06551de7fd203096f9e4f0816fe0a531`; its validation, security, publication
and deployed-byte verification passed. The owner installed the program add-on from
the HomeFX source and reported its private storage checks passing.

The latest TV reports show **Connection test: authorized** and **Refresh rotation:
passed**. These establish successful authorization and one refresh rotation in the
separate test scope. The refresh report explicitly says no list or history request
was made. The owner confirmed the add-on was reinstalled without restarting Kodi,
so restart persistence has not been tested. Cancellation/disconnect, failure recovery
and actual list/widget behavior are not established by these screenshots.

## Why a program add-on

The program add-on is a temporary, explicitly invoked authentication test. Its own
profile and app-identity scope keep experimental credentials separate from the
repository-installed video preview and its stable demo widgets. Installing or
opening it does not start login. It is not another Android application or server.

The intended everyday product remains the **video add-on**: connect there, choose
lists there, then assign widget rows separately in the existing skin. A future
reviewed video integration will require its own login and private storage checks;
it must not copy test tokens, settings or databases across profiles. The program
add-on is not a permanent requirement for using the eventual video experience.

## After successful authorization and refresh

Do not repeat a successful grant just to produce another screenshot. Keep the
matching test ZIP installed for now; no new package is required for these checks.

1. Fully close and restart Kodi. Open **HomeFX Development Test → Local connection
   status (no network)**. Report the fixed status only. Expect credentials stored;
   an explicit refresh/login-required state is a separate outcome, not a pass.
   If this was already done before refresh, report that sequence instead of repeating it.
2. When ready to end this test session, choose **Disconnect this test locally** and
   confirm. Reopen local status; expect **disconnected**. This removes local test
   credentials, not service-side authorization or backups.
3. On a later deliberate connection attempt, cancel at the code dialog **before**
   authorizing. Expect cancellation and local status disconnected. Never share the code.
   Do this after disconnect so a replacement attempt does not discard a session
   you intended to keep. Do not authorize again solely for this cancellation check.

Return only the fixed statuses and whether Kodi was fully restarted. Do not send
raw logs, tokens, device codes, profile paths, private lists/history or backups.
Denial/expiry, slow/offline behavior and interrupted-refresh recovery remain
separate [activation gates](account-setup.md#activation-gates); mark unexercised
cases **not run**. Do not corrupt a live token store or repeatedly refresh to test failures.

## Next milestone: one real list in the video add-on

After the remaining gates are reviewed, the smallest integration is an explicit,
read-only video account connection, one real personal or liked list, a stable widget
route, title/season browsing and selections surviving restart. Existing inactive
account/list assemblies are the starting point; another demo subsystem is unnecessary.
Selecting a list in HomeFX does not create a skin row. Keep a full-list folder route
where the skin heading is not clickable, and handle loading, empty, offline and
authorization-needed states without silently substituting demo content.

This milestone needs separate device acceptance for account isolation, focus/Back,
return position, cancellation, cold/warm loading and multiple rows. It does not
activate Production access, list/history writes, playback, Real-Debrid or scrobbling.
Continue Watching, Next aired and Upcoming remain distinct; dates are not source availability.

## Install directly from the HomeFX source

The hosted test ZIP/checksum and source-install path have been verified. The owner
installed it on the target TV. Other installations still need their own acceptance.

The installation path is:

1. Keep the existing File manager source `https://susanto-dev.github.io/homefx/`,
   named **HomeFX**. No new source, computer download or file transfer is needed.
2. Open **Add-ons → Install from zip file → HomeFX**. Review the Unknown sources
   warning if prompted; proceed only if you trust the project and have checked the
   source address. Do not bypass certificate or package-validation errors.
3. Select **`script.homefx.development-0.1.0-<SHA-256>.zip`** from the same source
   listing. The actual filename ends with its 64-character checksum; choose the
   script ZIP, not the `.sha256` sidecar, repository ZIP or video ZIP. The
   [download page](https://susanto-dev.github.io/homefx/) labels it as the
   **Development test** and shows the exact current filename.
4. Wait for the installation notification. Open **HomeFX Development Test** under
   **Program add-ons**, then run **Test this add-on's private storage** first.
   The owner confirmed this source-install/menu path on the target TV; skin labels
   may vary on other installations.
5. Keep HomeFX Preview, HomeFX Preview Repository and the current skin installed.
   The test does not replace their files, routes or profiles. Installation does not
   initiate login; each action requires its own consent.

A File manager source is a download listing. It is separate from Kodi's repository
index: this test add-on is deliberately absent from **Install from repository** and
has no repository-driven auto-update path. Installing it from the HomeFX source is
still a direct ZIP installation.

## What publication includes

After a reviewed main merge, the existing **Publish preview** workflow builds the
separate script ZIP using the **Development** environment and adds it to the same
Pages source. It does not contact Trakt, obtain credentials or start login. No
additional manual workflow is needed for this installation path. The 0.17.6
release added a new video archive because shared authentication bytes changed;
repository 0.2.0 and every previously recorded archive remain unchanged.

The script ZIP embeds the **public** Development client ID and registered redirect
from `TRAKT_CLIENT_ID` and `TRAKT_REDIRECT_URI`. Anyone can download these public
values from the hosted test ZIP; GitHub may also show them in build-step logs. Never
put a client secret, token, device code, private list/history or private configuration
in these variables. No secret is needed or accepted by the test schema. Production
is not selected. The configuration preflight remains syntax-only; ordinary PR tests
use fabricated values, and no real-account test belongs in CI.

Version 0.1.0 identifies the test harness. Its content-addressed filename and checksum
identify the exact built bytes, not a signature or proof of working account access.
The same inputs reproduce the same ZIP; changed code or public configuration has a
different filename. This is a **current experimental candidate**, outside the
retained release inventory: a later merge may remove an older test ZIP URL. A digest
filename must never serve different bytes. Keep a copy of the matching artifact if
needed for later scope-specific local disconnect. All recorded preview/repository
release URLs retain their existing preservation guarantees.

## Optional Actions download fallback

The **Build Development device test** workflow remains available for a maintainer
who wants an Actions artifact. It does not update the HomeFX source or deploy Pages.
On **main**, check its readiness confirmation only when the registered Development
public ID/redirect still match and the synthetic TV storage check has passed.
The workflow runs fabricated tests and requires the selected revision still to be
current main before building.

Its three-day artifact is named
`homefx-development-device-test-<source SHA>-<run ID>`. Download and extract the outer
artifact only when using this fallback; transfer the inner script ZIP to the TV,
then choose **Install from zip file**. Do not install the outer artifact wrapper.
Record the run link/source SHA and checksum. This fallback is not required when the
ZIP is available in the HomeFX source.

## Run one action at a time

Opening or cancelling the menu makes no network request and does not open a profile.
Each selection asks for confirmation before reading configuration or local storage.
The add-on closes after one action; reopen it for the next one. Do not enable Kodi
debug logging or capture/share a screen containing an authorization code for this test.

1. **Test this add-on's private storage**. Cancel once, then reopen and confirm.
   Read the complete report. Permissions, directory check, SQLite and cleanup must
   pass before proceeding. A failure stops this sequence; return fixed results only.
2. **Local connection status (no network)**. Confirm and record its fixed status.
   A first run should report disconnected. This action can create/check empty local
   test stores, but does not refresh or contact Trakt.
3. **Connect Development Trakt**. Read the consent and confirm only when ready to
   authorize. The storage check runs again before credentials or network setup.
   Use your own phone/computer to open the trusted address displayed on the TV:
   exactly `https://auth.trakt.tv/activate` or legacy `https://trakt.tv/activate`.
   Enter the code displayed privately on the TV. Never copy the code into chat, logs or
   an issue. The dialog supports cancellation and is bounded to ten minutes; network
   operations have their own limits, while OS DNS resolution can still delay return.
4. First exercise cancellation while the code prompt is open and **before**
   authorizing on Trakt. Expect a fixed cancelled outcome and no authorized state.
   Reopen and connect again when ready. An authorized result means credentials were
   stored locally; it does not establish list access, refresh or public activation.
5. Fully restart Kodi. Reopen the test and choose **Local connection status (no
   network)**. Expect credentials stored, or an explicit refresh/login-required
   state if appropriate. Do not infer persistence from an invocation that never closed.
6. **Test one refresh rotation**. Confirm once after a successful login and restart
   check. This consumes a stored refresh token and attempts one replacement grant;
   no list request follows. Expected success is **Refresh rotation: passed**. A busy,
   cancelled, interrupted or failed result is not a pass and may require login again.
   Do not repeatedly press refresh to work around a failure or deliberately corrupt
   storage/network state; failure injection remains in fabricated tests.
7. **Disconnect this test locally**. Confirm the scope-specific deletion prompt.
   Reopen local status and expect disconnected. Separately revoke the application's
   authorization in your Trakt account settings if you want service-side access
   removed. Local disconnect does not revoke it remotely or erase backups.

A replacement login removes this test scope's prior local credentials even if the
new login is cancelled. Denial, expiry, cancellation, offline/slow responses and
interrupted-refresh recovery remain separate acceptance outcomes. Record cases
that were not exercised as **not run**; do not manufacture a pass from the happy path.

## Retry after the 0.17.6 candidate is published

Historical repair context; see the completed outcome below.

The current activation address and legacy exact address are already supported.
The earlier failure was: the device-code request received status 403.
Official Trakt guidance requires an API key header containing the app's public
client ID, API version 2 and a User-Agent, as well as JSON Content-Type. Earlier
HomeFX OAuth requests omitted the first three headers. The 0.17.6 release supplies
HomeFX's own public identity and user agent, without a client secret or bearer
token for device-code issuance. OAuth remains on `https://auth.trakt.tv` with
unchanged TLS, redirect and retry protections.

The documentation associates 403 with an invalid API key or unapproved app.
The earlier TV rejection occurred before code display. After the header repair was
published, the owner reported authorization and refresh success. This is evidence
that the updated flow works on that device, not proof of the upstream reason for
the earlier 403 or acceptance of every failure path.

The repair is now published; the old retry sequence is superseded by
[the post-login checks](#after-successful-authorization-and-refresh). If another
connection fails, stop and return fixed Last stage, Category and Response status
only. Do not add a secret, bypass TLS or buy a plan as a troubleshooting shortcut.

## Storage and privacy limits

The test uses its own Kodi add-on profile, further separated by a digest of the public
client ID and redirect. This prevents a rebuilt test for a different app identity
from reusing the old app's tokens. No profile or credential migration into HomeFX
Preview occurs. The synthetic storage check before connect/refresh uses this same
scope, not the preview's earlier test location.

Tokens are unencrypted. Other code running as Kodi and profile backups may access
them. Do not share this profile, databases, full Kodi backups or unredacted logs.
Changing or invalidating the packaged configuration makes the old scope unavailable
to this test's status/disconnect actions; it does not erase that old data or revoke
its authorization. Keep the matching reviewed artifact for local disconnect, and
use Trakt account settings for remote revocation. Uninstalling is not proof of
forensic data erasure. Do not edit databases or guess profile paths to recover a test.

## Safe observations to return

Return only:

- The publication or manual-build run link/source SHA, test harness version and ZIP checksum.
- Fixed storage results, including cleanup and overall status.
- Fixed connect/cancel, restart-status, refresh and disconnect outcomes.
- On connection failure, fixed Last stage, Category and Response status fields only.
- Approximate wait times, responsiveness and any unexercised cases marked not run.

Do not return public app values unnecessarily, or any client secret, token, device
code, profile path, private list/history, account screenshot, full backup or raw log.
A generic failure is useful evidence; do not disable TLS verification or add a client
secret to bypass it.

After these results are reviewed, the next bounded milestone is the real read-only
list journey in HomeFX: one personal or liked list, separate skin-row assignment,
details and restart persistence. This test does not enable it automatically.
Continue Watching, Next aired and Upcoming remain separate; metadata and future
dates never prove a playable source.

See [account gates](account-setup.md#activation-gates),
[authentication contracts and primary sources](trakt-authentication.md), and
[storage boundaries](storage-boundaries.md). The current documented
[Trakt OAuth](https://developer.trakt.tv/docs/authentication-oauth) and
[registration](https://developer.trakt.tv/docs/create-an-app) requirements still
apply; owner confirmation is not proof of a successful provider grant or Production
approval. No app registration, changed-terms acceptance or paid service is performed
by this workflow.
