# Read-only list interaction preparation

Status: packaged but inactive. The public Kodi entry point and saved demo widget
routes are unchanged. No registered identity, login or real list is configured.
This closes a specific seam between existing account-bound Library reads and a
future gated UI; it does not establish a usable live widget yet.

`Library.browse_list(key)` projects mixed movie/show list metadata in service order.
Rows retain stable IDs and unknown watched state; date metadata never supplies a
playable source. Known unsupported season/episode/person entries are counted,
so even an unsupported-only result is not presented as a successful empty list.
Malformed or duplicate supported entries fail the whole view. The projection is
separate from Continue watching, Next aired and the personal upcoming calendar.

`Library.choose_lists(chooser)` supplies immutable references and the selected keys
for the verified account. Returning None cancels; returning an empty selection
explicitly clears choices. Confirmation pins account generation, data revision and
preference clear epoch. The ordered previous selection is also compared within the
save transaction, preventing a stale dialog from overwriting a concurrent choice.
No schema migration or remote list/history mutation is added. Existing per-account
restart persistence is reused. A refresh/account change requires reopening the
chooser even if list IDs happen to match.

`TraktListUI(dialog, progress_factory, monitor)` uses injected Kodi-shaped objects.
Construct it before service assembly and pass `ui.cancelled` to `build_trakt`, then
pass the resulting library to `choose`, `list`, `seasons` or `episodes`. This is a
future explicit integration sequence, not a public route or a registration bypass.
Construction opens no UI, storage or network connection. Folder reads show bounded
transport-driven loading with cancellation; widget reads open no dialogs. Cancellation
cannot forcibly interrupt operating-system DNS resolution; existing transport
bounds and device measurements remain necessary.

Results distinguish ready, empty, partial, saved, cancelled, authorization-needed,
connection-unavailable, changed, busy, limited and failed states. Errors expose
fixed messages only, with no private response/exception text or old result rows.
A captured generation/revision guard is checked after UI cleanup, so a reentrant
read under a replacement account cannot bless earlier results. Dialog cancellation
before confirmation does not save; cancellation after a completed local save does
not undo that save. Result payloads are private invocation data and must not be
logged, persisted or placed directly in public URLs.

## Remaining live boundary

The [account-bound route and renderer](widget-routing.md) now prepares opaque
persistent references, full-list access and injected read-only presentation. It is
not called by the public entry point. Gated dispatch, real account integration and
actual Kodi/skin acceptance remain necessary. Kodi submission is not a transaction;
failed completion does not prove that a skin discarded rows already submitted.
Selecting lists in HomeFX and assigning rows in the skin remain separate steps.

Registration/public identity and the exact registered redirect are owner inputs.
The [account gates](account-setup.md) and [staged TV checks](testing-on-tv.md) remain
mandatory before live login or routes. No private list names, history, credentials
or backups are needed in project discussions. Actual-device rendering, focus,
return position, cold/warm times, TLS, login and refresh remain untested.

## Integrated automated evidence

The whole-journey suite now joins the actual service factory and fixed-host transport
with account/list/widget interaction, using fabricated HTTP responses and private
temporary stores. New factory/UI instances test restart independently of invocation
cache reuse. This exposed a renderer cancellation bug repaired in 0.16.1; public
routes remain unchanged. See [testing](testing.md); actual registration and TV
gates remain open.
