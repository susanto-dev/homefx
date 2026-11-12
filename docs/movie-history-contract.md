# Movie watched-state contract

The inactive Trakt library joins a list's movie metadata with a complete watched-ID
response and paused progress. It supports All, Unwatched, Released unwatched and
Upcoming movie filters. This does not enable a live Kodi account route or establish
source availability.

## Primary evidence

Reviewed official Trakt contract snapshot:
`030a5e3cb6aacb11508f250865c0b907ab17b2ed`.

- [Personal watched routes](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/users/subroutes/watched.ts)
  define the typed GET `/users/:id/watched/movies` response without pagination.
  The separate minimal route has a pagination contract; HomeFX does not use it.
- [Watched movie response schema](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/users/schema/response/watchedMoviesResponseSchema.ts)
  supplies play count and nested movie IDs alongside timestamps and display metadata.
- [Sync routes](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/sync/index.ts)
  also describe a complete watched response; HomeFX uses the more explicitly typed
  personal route above rather than the generic sync response schema.

These are source contracts, not live-response or device acceptance evidence. No
upstream implementation is copied. The client requests `/users/me/watched/movies`
with the current bearer token and no page, limit or other query parameters.

## Completeness and failure handling

The client returns a tuple of positive Trakt movie IDs only after the entire response
passes validation. It rejects non-list data, invalid/nonpositive play evidence or
identities, duplicate IDs, unexpected pagination headers and oversized histories.
Unused timestamps and display fields are not retained or validated by this ID projection.
The default item bound is 2,000; the existing transport's response-byte bound also
applies. Exceeding either fails the view instead of silently truncating watched history.

A valid empty response is a complete empty watched set. A timeout, malformed response,
authorization failure or partial response is not an empty set. Such errors propagate
and clear invocation caches; the join never substitutes unknown or false on failure.
Pure normalization still supports unknown status when no snapshot is supplied by a
caller, and the conservative continue-watching view retains its earlier unknown-status
contract. The snapshot changes only list movie views.

List metadata, pauses and watched IDs are joined under one account generation and
local mutation revision. A change during a component request or normalization rejects
the joined result. Successful snapshots are held only in the bounded invocation cache;
refresh, account replacement, explicit history mutations and cache expiry force fresh
reads. This protects local consistency, not an atomic server-side snapshot: changes
made remotely during separate requests may only appear on a later refresh.

Tests use synthetic responses and temporary stores. They cover valid empty history,
failed/partial/oversized history, account or revision changes during the join, and
snapshot invalidation after token refresh and an explicit history write. No service
login, real watch history or TV navigation was exercised.
