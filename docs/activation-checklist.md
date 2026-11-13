# From the preview to a real Trakt widget

**Public preview live connection and account-bound routes remain inactive.** This handoff groups
existing requirements; it does not authorize login, replace the
[account activation gates](account-setup.md#activation-gates), or turn cloud tests
into TV evidence. No real account belongs in CI.

## 1. Try the published demo on TV

Follow the [installation guide](install.md) on Kodi 21.2 with the existing skin.
Published HomeFX Preview is 0.17.6 with repository 0.2.0; PR #34 post-merge
validation and publication passed.
The TV previously confirmed Kodi 21.2 / Python 3.11.7. The owner supplied a passing
0.17.4 synthetic storage report: private permissions, directory check, SQLite
commit/rollback, cleanup and overall passed; failure stage was none. This clears
the observed synthetic-probe blocker, not all account-store or network acceptance.

- Fully restart Kodi after installation/update. Open **Device readiness** and record
  the displayed versions and fixed capability results, including unavailable results.
- Open **Test private storage**. Cancel once, then run it if you choose. Record
  **Private file permissions**, **SQLite commit/rollback**, **Temporary cleanup**
  and **Overall** exactly as shown, plus **Failure stage** on 0.17.3. Scroll to read
  the whole report. Report cancellation as not run; report failed
  cleanup explicitly. Do not delete unfamiliar files to make a result pass.
- Select two demo lists in HomeFX, then assign their rows separately in the skin.
  Check focus, Back, return position, title/season browsing and full-list access.
  Cancel selection once and restart Kodi: prior choices and saved routes should remain.
- Use the [timing record](testing-on-tv.md#current-device-candidate-and-timing-record)
  for one row and multiple rows. Record first-open and immediate-reopen times and
  responsiveness; these synthetic results do not measure live network/cache behavior.

**Return only:** versions, fixed result/error categories, cleanup status,
success/failure/not-run observations and timings. Navigation/timing and actual
video-profile account-store persistence remain unverified; the separate program
restart check subsequently passed. A storage/readiness pass does not
prove TLS, Trakt authorization, refresh or playback works.

## 2. Verify registration before planning login

The owner has confirmed that the **Development** client ID and registered redirect
exactly match the GitHub configuration. This is owner confirmation, not a provider
login test. Reconfirm locally if either value or application changes. Variable
placement is documented in [configuration environments](account-setup.md#github-configuration-environments).
No values, screenshots or secrets need to be pasted into this checklist or an issue.

The Development preflight checks presence/syntax only. It does not verify registration,
public-client device/refresh support, provider entitlement or Production approval.
Review the current [registration requirements](account-setup.md#application-registration)
and public-client/redirect contracts before the next step. Do not use a client secret
to work around a failed grant, dispatch Production checks automatically, register a
new application or accept changed service terms as part of this handoff.

## 3. Explicitly authorize a bounded Development device test

Use the [separately installed Development device test](development-device-test.md)
from the verified source installation path. PR #32 publication and the owner’s
installation succeeded; its own storage check passed. Install its script ZIP directly from **Install from zip file → HomeFX**;
a manual artifact workflow or file transfer is not required. Building or installing
it initiates no login. Each on-TV action requires consent. It tests only its own profile and does not wire
public live routes or real-list widgets into HomeFX Preview.

The test must establish actual Android TLS trust and bounded slow/offline/cancellation
behavior, device authorization/denial/expiry/cancellation, single-use refresh rotation
and interrupted-refresh recovery. Fabricated failure tests remain in CI; they do not
prove these live outcomes. Check account-switch/disconnect handling and service-side
revocation guidance too: local disconnect is not remote revocation or backup erasure.
See [account gates](account-setup.md#activation-gates) and
[privacy and recovery](account-setup.md#privacy-and-recovery).

## 4. Accept one real read-only widget journey

Only after the gates permit it, choose a personal or liked list privately on the TV,
assign a skin row separately, browse title/season details and restart Kodi. Verify
saved selections, account isolation, loading/empty/offline/authorization-needed
states, cancellation and stale-row behavior using the
[bounded TV journey](testing-on-tv.md#start-here-bounded-read-only-journey).
Repeat timing measurements with live requests before deciding on cache or speed changes.
Do not export list contents to demonstrate success.

Continue Watching, Next aired and Upcoming remain distinct views. A personal calendar
does not cover every upcoming episode in arbitrary selected lists, and an upcoming
date never guarantees playable availability. Remote list/history writes, playback,
Real-Debrid and scrobbling require separate work and remain outside this milestone.

## Keep private information private

Never share tokens, client secrets, device codes, profile paths, private lists/history,
unredacted logs or full Kodi backups. No screenshot is required. Return only the safe
categories and observations above; retain private application/account details locally.
See [security](security.md) and the [complete backlog](backlog.md) for the wider scope.

## Completed synthetic storage checkpoint

The 0.17.4 TV result passed private permissions, directory check, SQLite transaction
and cleanup checks, with failure stage none. The separate test add-on must test its
own storage scope before live connect/refresh; the preview pass is not transferred
as blanket permission for a different path or for live account access. The owner
subsequently passed that separate test's own storage check and correctly saw local
status disconnected. Connecting then failed before any code appeared, so the
remaining account tests were not run. That diagnostic report identified a
403 response rejection before code display; the local limiter only generates 429.

## Current checkpoint: authorization and refresh passed

After PR #34 publication, the owner supplied **Connection test: authorized** and
**Refresh rotation: passed** reports from the separate Development program add-on.
The refresh test made no list or history request. The owner subsequently confirmed restart persistence, disconnect, code-dialog
cancellation and responsive offline failure. Restoring networking allowed a new
code without reinstalling. These clear the observed lifecycle blockers, not real
list/widget acceptance; live denial/expiry and interrupted refresh are not claimed.

The owner completed the short [post-login checklist](development-device-test.md#after-successful-authorization-and-refresh)
for restart status, local disconnect and cancellation. Do not repeat those passes. No new test ZIP
or repeat authorization is needed just to record these outcomes. Leave unexercised
gates as not run. The next implementation target is the existing video add-on's
read-only list journey, subject to the remaining gates, without importing test tokens.

Failure evidence is divided explicitly between automated synthetic cases and TV
observations in [account setup](account-setup.md#evidence-required-without-destructive-account-tests).
A controlled process-interruption test uses synthetic stores; no destructive live
refresh experiment is requested. The remaining integration work is the video entry
and immutable configuration delivery, then one deliberately enabled read-only TV journey.
