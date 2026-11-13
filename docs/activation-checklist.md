# From the preview to a real Trakt widget

**Live connection and account-bound routes remain inactive.** This handoff groups
existing requirements; it does not authorize login, replace the
[account activation gates](account-setup.md#activation-gates), or turn cloud tests
into TV evidence. No real account belongs in CI.

## 1. Try the published demo on TV

Follow the [installation guide](install.md) on Kodi 21.2 with the existing skin.
The published candidate is HomeFX Preview 0.17.2 and repository 0.2.0.

- Fully restart Kodi after installation/update. Open **Device readiness** and record
  the displayed versions and fixed capability results, including unavailable results.
- Open **Test private storage**. Cancel once, then run it if you choose. Record
  **Private file permissions**, **SQLite commit/rollback**, **Temporary cleanup**
  and **Overall** exactly as shown. Report cancellation as not run; report failed
  cleanup explicitly. Do not delete unfamiliar files to make a result pass.
- Select two demo lists in HomeFX, then assign their rows separately in the skin.
  Check focus, Back, return position, title/season browsing and full-list access.
  Cancel selection once and restart Kodi: prior choices and saved routes should remain.
- Use the [timing record](testing-on-tv.md#current-device-candidate-and-timing-record)
  for one row and multiple rows. Record first-open and immediate-reopen times and
  responsiveness; these synthetic results do not measure live network/cache behavior.

**Return only:** versions, fixed result/error categories, cleanup status,
success/failure/not-run observations and timings. These checks remain **not run on
TV** until actual observations are supplied. A storage/readiness pass does not prove
TLS, Trakt authorization, refresh or playback works.

## 2. Verify registration before planning login

The owner already reports creating the Trakt application and configuring public
values. Confirm, within the owner-managed Trakt registration and GitHub settings,
that the **Development** client ID identifies that registered application and the
shared redirect URI exactly matches its registration. The repository variable
names are documented in [configuration environments](account-setup.md#github-configuration-environments).
No values, screenshots or secrets need to be pasted into this checklist or an issue.

The Development preflight checks presence/syntax only. It does not verify registration,
public-client device/refresh support, provider entitlement or Production approval.
Review the current [registration requirements](account-setup.md#application-registration)
and public-client/redirect contracts before the next step. Do not use a client secret
to work around a failed grant, dispatch Production checks automatically, register a
new application or accept changed service terms as part of this handoff.

## 3. Explicitly authorize a bounded Development device test

This is a **later gated test**, not an instruction to start login in the current
preview. After reviewing steps 1–2, agree on the small Development test scope before
any live flow is enabled. Keep public live routes inactive until the account gates
are satisfied and the implementation has passed review.

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
