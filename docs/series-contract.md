# Series metadata and watched-progress contract

This service layer remains inactive. It uses injected requests and fabricated tests;
no Kodi route, account login, playback adapter or live API connection is enabled.
Season metadata identifies episodes to browse. Neither episode counts nor air dates
establish a playable source or an account's watched state.

## Primary evidence

The official `trakt/trakt-api` contracts were inspected at revision
`030a5e3cb6aacb11508f250865c0b907ab17b2ed`:

- [Show endpoints](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/shows/index.ts) describe `GET /shows/:id/seasons` as all season metadata, with extended information. `extended=episodes` fetches a much larger result and is deliberately not requested. The watched-progress description explicitly documents `specials=true` to include season zero, and that future or undated episodes do not contribute to progress.
- [Season response](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/shows/schema/response/seasonResponseSchema.ts) defines the season number and IDs, plus extended optional or nullable counts, title, and first-air information.
- [Season IDs](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/_internal/response/seasonIdsResponseSchema.ts) distinguish the Trakt ID from other provider namespaces.

These links are evidence, not incorporated implementation. Original tests use invented
IDs and metadata. Service access, terms and actual responses still require validation
before live activation. No new paid dependency or account entitlement is assumed.

## Read contracts

`Client.show_seasons(show_id)` requests exactly `/shows/ID/seasons?extended=full`.
The result is `{"show_id": ID, "seasons": [...]}`. Every projected row has:

- `number`: integer 0–10000 (zero means specials).
- `ids`: only the positive 63-bit `trakt` ID; other namespaces are not substituted.
- `episode_count` and `aired_episodes`: integers 0–10000, or `None` if absent/null.
- `title` and `first_aired`: bounded text or `None`. Air-date interpretation belongs
  to the view's timestamp parser; a string by itself is not proof of an aired episode.

The list is bounded by the client's item limit and at most 1000 seasons. Duplicate
season numbers or Trakt IDs fail the entire read. Malformed fields fail closed;
unknown fields are not projected. Response order is preserved for the caller to sort.
An empty list is a valid empty metadata response. Pagination headers are rejected:
this endpoint's inspected contract is a complete array, and a page cannot be presented
as a complete series. Counts may be missing or stale and are not watch-history evidence.

`Client.show_progress(show_id, include_specials=False)` keeps regular-season scope
by default. An explicit boolean `True` requests `specials=true`; false requests
`specials=false`. Both keep `hidden=false`. Missing hidden-season or episode progress
must remain unknown rather than being invented as unwatched. The special flag is not
an automatic next-episode policy or a choice of playback/scrobbling owner.

`Session.read` exposes these bounded operations and validates IDs, season numbers
and the specials flag before it may refresh credentials. Account-generation checks
still bracket network work. Existing per-season reads remain available through
`season_episodes(show_id, season)`, with strict numeric input validation before refresh
and rejection of pagination headers on its documented complete-array response.

## Validation limits

Mocked client, session and HTTP-framing tests cover nullable metadata, duplicate and
malformed rows, incomplete responses, no-I/O validation, account replacement during a
read, exact route/query encoding and the explicit specials scope. No live account,
provider quota, TV navigation, Kodi compatibility or actual playback result is implied.

## Joined series views

`Library.series_view(show_id, now=None, episode_filter="all", include_specials=False)`
reads selected seasons under one account generation and local data revision. It reads
watched progress and paused playback once per join, using the same specials scope.
At most 50 selected seasons and 5,000 episode rows are accepted. Known season counts
are reconciled with returned rows; a mismatch fails as `incomplete_series` rather than
returning partial output or retrying. Missing counts supply no independent proof of
catalogue completeness. Metadata can change between requests, so a valid live series
may require a later explicit refresh when counts disagree.

The `all` filter preserves season/episode order. `aired_unwatched` requires explicit
unwatched evidence and a known past air date, then applies unfinished-first/date order.
Unknown watched status, future releases and undated episodes never enter that filter.
Duplicate episode identities, mismatched seasons, failures and account changes reject
the compound view and clear its invocation cache.

`Library.series_seasons` derives watched, unwatched, unknown, upcoming and aired-unwatched
counts from those episode rows. Empty seasons contribute no episode summary. The pure
`trakt_views.continuation` helper returns immediate aired and next known-unwatched
candidates in narrative order. It makes no player call and leaves an immediate
candidate's unknown watched state unknown. Specials require explicit inclusion;
these candidates do not decide automatic playback or scrobbling ownership.

## Inactive widget consumer (0.17)

`Library.widget_episodes(ref, item_ref, season, episode_filter="all")` adds a local
filter to the existing account-bound read. It validates the filter before account
work, requests the complete season, rejects wrong-season rows, then applies the
existing `trakt_views.episode_filter`. All preserves narrative order; aired-unwatched
uses unfinished-first ordering and excludes unknown watched/date and future rows.
The captured account/selection guard remains attached to the result. Episode detail
resolution continues to use the full unfiltered season. No new endpoint is called.
