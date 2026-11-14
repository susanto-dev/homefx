# Enriched continue-watching contract

`Library.enriched_continue_view(now=None)` is an explicit read operation, used by the
[Development account-wide widget candidate](continue-widget.md). Public Preview
does not activate it.
It supplements paused-playback metadata with authenticated title details and watched
snapshots. The existing `continue_view` remains unchanged and never implicitly adds
these requests. Neither method starts playback, obtains sources or writes history.

## Identity, evidence and ordering

Pause rows often omit release dates. Movie details are fetched by the movie Trakt ID;
episode details use the verified show Trakt ID plus season and episode number. The
returned episode Trakt ID must also equal the pause ID. Different identifier
namespaces and title strings are never interchangeable identity evidence.

The complete movie watched snapshot is fetched once when movies are present. Show
progress is fetched once for each distinct show. Specials are explicitly included
for that show only when a candidate pause is season zero. Known watched results
override stale pauses and are excluded. Missing episode progress remains
`watched=None` and `aired_unwatched=False`; it never becomes an unwatched assertion.

Only known aired metadata with unfinished progress enters the returned view. Future
and unknown release dates are excluded. A movie release date does not establish
regional or streaming availability. Results sort by latest paused UTC instant, then
stable identity. Duplicate pause IDs select the newest timestamp; a newer zero or
complete progress value supersedes an older unfinished one. Conflicting progress at
the same timestamp or conflicting episode coordinates fail the whole read.

An officially nullable episode title gets the display fallback `Episode SxxExx` with
`title_unknown=True`; it is not presented as a known provider title. Unknown duration
is not invented. Progress remains a percentage and is never converted into resume
seconds. Every returned row has `playable=False`.

## Bounds and failure behavior

At most 100 pause rows and 50 distinct unfinished candidates are accepted, without
silent truncation. Enrichment reads details once per candidate and watched progress
once per applicable account/show. This caps the operation at 101 logical data reads
(pauses, details and history), before underlying bounded pagination, optional saved
preference identity checks and credential refresh. No sleeps, background jobs or
retries are added. Empty or entirely zero/complete pause data causes no detail or
history read.

Input clock validation precedes account work. Invalid timestamps, future pause times,
malformed identities/progress, mismatched details, provider failures and account/data
revision changes reject the compound result and clear its invocation cache. A partial
successful list is never returned after such a failure. The existing bounded cache
stores only invocation-memory response copies; no persistent history/cache is added.

Tests use fabricated responses and temporary accounts only. They establish library
contracts, not a live Trakt response, entitlement, playable source, device resume
position, successful scrobble or TV acceptance. The Development widget guide explains the extra reads and unknown watched state;
actual endpoint and device acceptance remain unverified.
