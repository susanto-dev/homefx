# Account-wide Continue Watching widget

This Development Video candidate adds one mixed movie/episode row for the current
Trakt account. It is independent of selected lists: titles outside those lists can
appear. Public Preview remains synthetic. No player, source resolution, remote
write or scrobbling is activated.

## Select the row

After merge and verified publication, update Development Video from the current
checksum-named ZIP at the [HomeFX source](https://susanto-dev.github.io/homefx/) and
fully restart Kodi. Keep your existing login and list selections.

Open **Widget folders → Continue watching (account-wide; reads history)**, then
open the account's terminal Continue watching folder. In your existing skin's
widget source chooser, enter that same terminal folder and select **Use as widget**.
Selecting a folder in HomeFX does not create a skin row; see [widget setup](widget-setup.md).
The initial chooser verifies the current account but does not read paused/history
collections until the terminal folder is opened.

Titles open read-only details. **Open Continue watching** returns to the whole feed;
these account-wide items do not offer selected-list or season shortcuts using the
wrong reference. An old item that is no longer eligible does not open cached detail.
This is separate from [per-show Continue/Next/Upcoming](show-progress.md).

## Meaning, privacy and request costs

The feed uses [existing bounded enrichment](continue-contract.md): dated aired
unfinished pauses, joined to title details and watched snapshots. Known watched
entries override stale pauses. Unknown episode watched status stays unknown rather
than being labelled unwatched. A pause percentage is not a seek position in seconds,
and no row claims to be playable. Future and unknown-date titles are excluded.
The newest pause comes first, with stable identity tie-breaking.

This is not a complete watch history, global Next aired feed or personal calendar.
An empty successful result means no eligible pauses were found. Offline, failed,
authorization-needed and cancelled reads remain separate states. Incomplete reads
fail instead of returning a successful partial feed.

Up to 100 pause rows and 50 distinct unfinished candidates are accepted. Enrichment
can require up to 101 logical reads before underlying pagination/account/refresh
work. Additional rows or opens can repeat requests. Only invocation-memory caching
is used; no background work or persistent viewing-history cache is added. Measure
cold/warm loading before adding several rows; no speed improvement is claimed.

Opaque folder/item references are bound to the verified account and private clear
epoch. They survive normal restart/refresh for the same account, not disconnect or
account replacement. They are locators, not authorization. No credential transfer,
new account registration or list selection is required solely for this feature.

## Smallest TV check

1. Open the feed using your existing connection. Privately check movie/episode
   identity, unfinished status and ordering; report content / empty / failed only.
2. Open details and press Back. Check focus and responsiveness; nothing should play.
3. Assign one row, fully restart Kodi and check that it still opens. Record approximate
   cold/warm seconds, then two-row timing only if the first row works.

Do not repeat completed authentication tests, edit token files or disconnect merely
for this check. Keep titles/history, tokens, codes, paths, full backups and raw logs
private. Cloud tests and source inspection are not TV evidence.
