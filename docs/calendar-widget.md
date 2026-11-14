# Personal Upcoming episodes widget

This Development Video candidate adds **Upcoming episodes (personal calendar)**
to Widget folders. It uses Trakt's authenticated personal show calendar, independent
of HomeFX's selected lists. Public Preview remains synthetic. No playback, remote
writes, provider activation or account registration is added.

## What the row means

Each open requests seven UTC calendar dates starting today: from today's UTC
midnight through the exclusive midnight seven dates later. Only episodes strictly
after the current UTC instant are shown, earliest first. This is not a rolling
168-hour window. The window advances on the next open; there is no background timer.
The directory category identifies the window. Midnight changes and provider edits
can change membership between opening the row and opening details.

Trakt describes its personal calendar as watched, collected or watchlisted items,
plus individual watchlisted episodes. It is **not a complete schedule for arbitrary
personal or liked lists**. Missing dates do not mean no future episodes exist.
The separate per-show Upcoming view remains available for a selected show's known
future dates. See [show progress](show-progress.md).

All calendar rows retain **unknown watched status**. Calendar membership does not
establish unwatched status, unfinished progress or playable availability. No history
join or resume percentage is invented. Rows show the show title, season/episode
numbers and episode title; unknown episode titles use a numbered fallback.

## Configure one existing-skin row

After merge and verified publication, update Development Video using the current
checksum-named ZIP at the [HomeFX source](https://susanto-dev.github.io/homefx/) and
fully restart Kodi, retaining your current login and saved lists.

Open **Widget folders → Upcoming episodes (personal calendar) → the personal calendar
folder**. In Arctic Zephyr Reloaded's widget source chooser, enter that terminal
folder and select **Use as widget**. HomeFX does not create the skin row itself.
See [the source-verified skin steps](widget-setup.md).

The source chooser checks account identity without loading calendar entries. The
terminal folder performs the read. Episode tiles open read-only details, rechecking
current feed membership; an item that has aired or disappeared no longer opens as
an upcoming item. **Open personal calendar** returns to the complete current feed.
No selected-list/season action uses calendar references.

## Loading and privacy boundaries

The existing calendar client/projection validates the complete bounded response,
with at most 1,000 rows; oversized, malformed or failed responses do not become a
truncated successful directory. Successful empty, offline, authorization-needed,
cancelled and failed outcomes remain distinct. Access denied is not an empty feed
and does not by itself establish a paid-plan requirement.

The calendar read uses one existing endpoint, plus account/refresh work when needed.
It does not enumerate selected lists, fetch watched history or make per-episode
detail requests. Additional opens/rows can repeat network work. No persistent
calendar/history cache, prefetch loop or performance improvement is introduced.
Opaque references are account/clear-epoch bound and separate from Continue Watching
and list references. Normal restart/refresh preserves them; disconnect or account
replacement invalidates them. No schema migration or credential transfer is needed.

## Short TV check

1. Open the calendar with the existing connection. Report content / empty / failed;
   privately check show/episode identity, future dates and unknown watched status.
2. Open details and press Back. Check focus, return position and responsiveness.
   No playback or watched-state change should occur.
3. Assign one row, fully restart Kodi, and confirm it reopens. Record approximate
   cold/warm seconds; add a second row only after the first works.

Do not repeat completed authentication/storage tests or deliberately alter account
files. Report fixed outcomes and timings only, not titles, history, tokens, codes,
profile paths, raw logs or full backups. Synthetic tests are not TV evidence.
