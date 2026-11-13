# Bounded Development Trakt test on Kodi

**This is a separate experimental test add-on, not live mode for HomeFX Preview.**
HomeFX Preview 0.17.4 and repository 0.2.0 remain unchanged. The test adds no list
widgets, account-data reads, history/list writes, playback, Real-Debrid or scrobbling.
It is a Kodi program add-on, not a new Android app or server.

The owner has confirmed that the registered Development client ID and redirect
match the GitHub variables, and supplied a passing synthetic storage report on
0.17.4: permissions, directory check, SQLite commit/rollback and cleanup passed;
failure stage was none. These observations do not establish real TLS, token-store
persistence, login, refresh rotation or account entitlement. Those remain device
tests, not cloud results.

## Install directly from the HomeFX source

The source-install change is a candidate until its PR is merged and the normal
Pages publication and hosted-byte checks pass. The existing manual build succeeded,
but the Development ZIP has not yet been verified in the hosted source or installed
on the TV. Do not treat its absence before publication as a Kodi failure.

After that publication is verified:

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
   Skin labels may vary; this source-install/menu path remains unverified on TV.
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
additional manual workflow is needed for this installation path. The public video
ZIP, repository ZIP and all recorded release archives remain unchanged.

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
   Use your own phone/computer to open exactly `https://trakt.tv/activate` and enter
   the code displayed privately on the TV. Never copy the code into chat, logs or
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
