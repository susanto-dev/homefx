# Kodi metadata identity and TMDb Helper

HomeFX Development Video keeps Trakt as its metadata source and the existing skin.
This candidate supplies typed Kodi media identities from data already read for the
selected list. It does not fetch artwork or turn on a metadata service.

## What changes

Movie/show cards expose Trakt IDs and an optional valid TMDB ID through Kodi's
`InfoTagVideo.setUniqueIDs`. Season and episode cards expose their parent show's
Trakt/TMDB IDs under the separate `tvshow.trakt` and `tvshow.tmdb` namespaces, plus
its display title. An episode's own Trakt ID remains distinct from its parent.
No show ID is mislabelled as an episode's TMDB ID. Missing or invalid optional IDs
stay absent; HomeFX does not guess from a title or perform an extra lookup.

Existing account/list membership and final rendering guards still apply. The
parent comes from the selected show's metadata, not another account or a global
cache. Saved opaque URLs, selection storage, ordering and watched state are
unchanged. Public Preview/Production live routes remain inactive.

## Installed Helper and verified interface

The owner identified **TMDb Helper 5.4.16**, add-on ID
`plugin.video.themoviedb.helper`, from Kodi's add-on repository. The exact
[official 5.4.16 archive](https://mirrors.kodi.tv/addons/nexus/plugin.video.themoviedb.helper/plugin.video.themoviedb.helper-5.4.16.zip)
was inspected on 14 November 2026. SHA-256:
`fdd9d9e4b77d1e1db6b1c6f42c72b562039233f5a8322f53d5d950d9a46e6e1a`.
Its manifest declares GPL-3.0-or-later and includes the GPLv3 licence text.
No Helper source, artwork or bundled credentials are copied into HomeFX.
The archive is a reference, not a dependency or a HomeFX download.

In that archive, `resources/tmdbhelper/lib/monitor/itemdetails.py` reads
`UniqueId(tmdb)` for movies/shows and `UniqueId(tvshow.tmdb)` for seasons/episodes.
HomeFX now supplies those standard Kodi labels when the existing Trakt response
contains a valid mapping. This avoids requiring HomeFX to request its own artwork
or borrow Helper credentials merely to expose identity.

The [Helper service-monitor documentation](https://github.com/jurialmunkey/plugin.video.themoviedb.helper/wiki/Service-Monitor)
describes focused-item metadata and skin-provided widget-container selection.
The wiki evolves; its newer options are not proof of support in 5.4.16. Source
inspection verifies which IDs that version reads, not that the installed skin
consumes its resulting artwork or that a service request succeeds.

## What this does not do

HomeFX does not import Helper modules, inspect its profile/settings/tokens/cache,
install or upgrade Helper, alter skin settings, set global service properties,
run Helper scripts, initiate playback or add background work. Helper remains
optional; ordinary HomeFX browsing works without it. No HomeFX TMDB credentials,
new licence purchase or paid plan are required by this change.

If the user already enabled a skin/Helper metadata service, that separate service
can consume the new IDs and make its own requests. Its network, cache, provider
terms and performance remain under its own configuration; this change does not
promise zero total Kodi network traffic. IDs exposed to Kodi are metadata, not
account credentials, but selected titles can still reflect private interests.
No account/list IDs, watch history or tokens are added to URLs or logs.

Focused artwork is not a whole-row artwork API. HomeFX cards retain their original
placeholder art. No successful automatic poster replacement, correct skin wiring,
cache benefit or speed improvement is claimed. Direct TMDB integration remains
[deferred](tmdb-artwork.md); Real-Debrid and playback remain inactive.

## Smallest TV check after publication verification

1. Update **HomeFX Development Video** using the current checksum-named ZIP in the
   HomeFX source, then fully restart Kodi. Keep the existing login and saved lists.
   Do not repeat completed authentication/storage checks solely for this update.
2. Open one saved list and a show's season/episode folders. Verify normal titles,
   watched state, focus, Back and return position still work.
3. In an existing skin widget, focus one movie and one show. If the skin's Helper
   service was already configured, observe whether its information/artwork panel
   identifies the correct item. No automatic skin configuration is part of HomeFX;
   unchanged placeholders alone do not mean the list failed.
4. Compare cold/repeat focus and navigation times, optionally with two rows. Report
   only correct/incorrect/no visible change and approximate timings. Do not share
   private titles/list names, history, tokens, profile paths or full backups.

Actual Helper/skin interaction is unverified on the target Kodi 21.2 / Arctic
Zephyr Reloaded 3.0.3 setup. A useful next decision depends on that observation;
HomeFX must not add a custom skin or a bulk Helper lookup loop on assumption.
