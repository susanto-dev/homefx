# Inactive device-login dialog adapter

`AccountUI(provider, dialog, progress_factory, monitor)` adapts injected Kodi-shaped
objects to `AccountFlow`. Providers are `trakt` and `realdebrid`. Construction opens
no UI, reads no profile and contacts no service. The preview entry point does not
construct this adapter or expose live account actions.

The adapter provides `confirm_replace()`, `show_code(code, url)`, `close()` and
`confirm_disconnect()`, plus `cancelled()` and `wait(seconds)` callbacks for the
controller. Supply the assembled bundle's disconnect callback: Trakt disconnect
must clear its saved list choices; provider disconnect must affect only provider
credentials. UI confirmation alone never deletes data or revokes authorization.

## Display and cleanup

Device codes go only to the explicit progress-dialog display call. They are not
stored as adapter string fields, returned, persisted or logged. The trusted injected
UI necessarily receives the code; it must not log display text or callback exceptions.
This is not protection against arbitrary code running in the same process.

The UI accepts only the canonical `https://trakt.tv/activate` and
`https://real-debrid.com/device` URLs for the selected provider. It does not open a
browser. Codes must contain 1–128 printable non-space ASCII characters, excluding
square brackets to prevent Kodi text-markup interpretation. This UI boundary is
intentionally narrower than the Trakt transport's allowed verification-host contract;
a changed provider URL or code format fails closed until separately reviewed.

A progress object is created lazily. Creation/update failures attempt cleanup and
produce fixed errors. Close drops the adapter's reference before calling cleanup,
so repeated close never repeats a failed external close. Raw callbacks, codes and
URLs do not become error messages. A failed adapter is not reused; construct a new
one for a new explicit interaction. No successful credential storage is undone by
UI cleanup; that outcome remains the account controller's responsibility.

Replacement confirmation warns that a new login replaces local credentials even
if subsequently cancelled. Disconnect wording distinguishes local deletion from
remote service authorization and backup erasure. Trakt wording includes removal of
saved HomeFX list choices; Real-Debrid wording leaves Trakt selections unchanged.

## Cancellation and wait bounds

`wait(seconds)` accepts finite durations from zero through 60 seconds. It checks
system abort and progress-dialog cancellation, then uses at most 600 monitor waits
of at most 0.1 seconds each. The account controller normally requests no more than
one second. A fake or broken monitor that returns immediately cannot create an
unbounded polling loop; the controller separately rejects a scheduler whose
monotonic clock does not advance. These bounds do not interrupt a blocking service
request or misbehaving injected callback. Network timeouts remain the transport's
responsibility, and actual Android UI responsiveness requires device tests.

## Primary Kodi interface evidence

The injected signatures follow Kodi 21.2 source documentation:

- [Dialog and DialogProgress](https://github.com/xbmc/xbmc/blob/21.2-Omega/xbmc/interfaces/legacy/Dialog.h): `Dialog.yesno(heading, message)`, `DialogProgress.create(heading, message)`, `update(percent)`, `iscanceled()` and `close()`.
- [Monitor](https://github.com/xbmc/xbmc/blob/21.2-Omega/xbmc/interfaces/legacy/Monitor.h): `abortRequested()` and `waitForAbort(timeout)`.

No upstream implementation is copied. Tests use fake objects to establish call
contracts, bounded waits and failure cleanup. They do not prove dialog rendering,
remote-control navigation, login, account entitlement or TV acceptance. Registration,
public-client contract verification and existing activation gates remain required.
