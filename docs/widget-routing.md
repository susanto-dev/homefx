# Account-bound widget routing and rendering

Status: implemented for explicit development integration, inactive in the public
Kodi entry point. Existing demo routes and skin shortcuts keep their behavior.
No app registration, login, public live dispatch, playback or remote write is added.

## Stable private references

The private preference store's schema 3 adds one generated 32-byte profile key.
Migration from valid earlier schemas preserves selections and the clear epoch in
the same transaction. Malformed or missing schema-3 identity is rejected rather
than silently regenerated. The database retains its existing path, permissions,
size and transaction checks. The key is never bundled or exported.

List references are HMAC-SHA256 values bound to the profile key, verified account,
list identity and clear epoch. Item references also bind the parent list, media
kind and title identity. Widget URLs contain opaque references and bounded numeric
season/episode coordinates, not account names, list IDs, titles or tokens.
References are locators, not authorization credentials; possession never permits
access without the current verified account, selected-list membership and ordinary
service reads. Treat saved URLs and profile backups as private anyway.

References survive reopening and token refresh for the same verified account.
A different account or independently created profile cannot resolve them, even if
it selects the same global list. Deselection rejects an old route instead of
rebinding it by position; reselecting the same list can restore its reference if
the clear epoch is unchanged. Clear/disconnect invalidates old references. The
existing clear epoch is profile-wide, so an explicit account clear invalidates
other existing references too. No new per-list mapping or unbounded history is kept.

Every compound read returns a captured guard with its payload. It checks the exact
account generation/revision, clear epoch and selection snapshot again before
presentation. Cached Library selection state alone is not sufficient. The existing
8-account and 100-selection bounds still apply. Old runtimes cannot read schema 3;
retained packages do not establish safe downgrade of migrated private profiles.

## Injected Kodi rendering

The separate strict route parser accepts only the read-only source, list, season,
episode and metadata-detail routes with exact required parameters. It rejects
unknown/duplicate fields and malformed references before account work. The public
preview parser does not dispatch this namespace.

The injected renderer uses the existing Library, stages ListItems before bulk
submission, sanitizes service text for display, and builds commands solely from
validated internal routes. An optional trusted absolute local artwork root supplies
the existing original poster/icon/fanart; service image URLs are not used. It sets no playable flag and offers no history/list
mutation actions. Folder/widget routes disable Kodi disk caching. Widget refresh
opens no modal progress, authorization or detail dialog; explicit title/episode
actions display read-only metadata. Full-list access uses the same bound list URL
from a title context action or a separate skin menu shortcut. Selecting lists in
HomeFX does not configure or remove the skin's rows.

Loading, empty, partial/unsupported, unavailable, authorization-needed, connection
failure and cancellation remain distinct. Failed or cancelled reads never receive
a successful directory completion. Payload/exception text is not logged or used
as a diagnostic. Account and selection guards run before and after submission.

Kodi directory submission is **not transactional**: AddItems appends rows and
EndOfDirectory(False) does not itself clear them. This renderer does not claim an
atomic account switch or guaranteed clearing of rows already held by Kodi/a skin.
Before live dispatch, test and resolve stale-row/return-position behavior on the
actual target, including account changes at submission. See Kodi 21.2's official
[API declarations](https://github.com/xbmc/xbmc/blob/21.2-Omega/xbmc/interfaces/legacy/ModuleXbmcplugin.h)
and [directory implementation](https://github.com/xbmc/xbmc/blob/21.2-Omega/xbmc/filesystem/PluginDirectory.cpp).
No upstream implementation or artwork is copied.

## Activation remains separate

The next gate is a deliberate public dispatcher/account integration after the
registered public identity/redirect and authorized device tests are available.
The [account gates](account-setup.md), [widget setup](widget-setup.md) and [TV
checklist](testing-on-tv.md) remain authoritative. Cloud tests cannot establish
TLS, login/refresh, actual skin focus/Back, restart persistence or cold/warm timings.
Continue Watching, Next aired and Upcoming remain separate views; dates and the
personal calendar are not playable availability or complete selected-list schedules.

## Episode views and watch-progress metadata (0.17)

The episode route accepts an optional `filter=all` or `filter=aired_unwatched`.
Omitting it preserves the original URL and All-episodes narrative order. The other
route kinds reject this field, and malformed/unknown values fail before account
reads. Fixed context actions on season folders and episode rows preserve the bound
list/show reference and season. Episode detail actions do not carry filter state;
Open full list still opens the original mixed list.

The filtered view validates the complete season before excluding any rows. It then
includes only known-unwatched episodes with an aired date, orders unfinished items
first, and uses the existing date/order rules. Unknown watched evidence is not
unwatched even when a pause is present. If no rows qualify, the view remains empty;
when entered from a season folder, use Back and that folder's All episodes action
to restore the full view. A directly configured widget may have a different parent;
use its separate full-list shortcut to reach the series and season folder.
No settings/navigation row is inserted into widget content.

Season plots show total, watched, aired-unwatched, upcoming and unknown watched/date
counts. These overlap as independent dimensions and must not be added as exclusive
availability buckets. Unfinished progress is shown only as a bounded percentage;
no duration, resume seconds, playable flag or playback action is invented. Dates
and counts remain metadata. Actual skin display and navigation remain TV gates.
