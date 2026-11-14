# Metadata enrichment and personal episode calendars

The calendar is used by the [Development widget candidate](calendar-widget.md).
Public Preview does not activate it. Tests use fabricated responses. Title identity, dates and partial progress are metadata;
they do not prove playable sources, watched state or access to a particular service.

## Primary source evidence

The official `trakt/trakt-api` contracts were inspected at revision
`030a5e3cb6aacb11508f250865c0b907ab17b2ed`:

- [Movie summary](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/movies/index.ts) supports `GET /movies/:id` with extended information.
- [Episode summary](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/shows/index.ts) supports `GET /shows/:id/seasons/:season/episodes/:episode`; an unknown first-air timestamp is null.
- [Calendar endpoints](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/calendars/index.ts) define the UTC date-window show calendar as an array response with extended metadata.
- [Calendar parameters](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/calendars/schema/request/calendarParamsSchema.ts) define `my` as watched, collected or watchlisted items, plus individual watchlisted episodes. This is **not** a calendar of arbitrary personal or liked lists.
- [Calendar rows](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/calendars/schema/response/calendarShowListResponseSchema.ts) contain an outer `first_aired`, a show and an episode. The [episode schema](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/_internal/response/episodeResponseSchema.ts) permits unknown titles and timestamps.

No upstream implementation was copied. These inspected contracts do not establish
live entitlement, API availability, TV acceptance or a paid-plan requirement. Recheck
current service terms and real responses before activation. The 31-day maximum below
is a conservative HomeFX request bound; the inspected parameter schema states an
integer day count but does not declare this maximum as a provider guarantee.

## Client and session reads

`movie_details(trakt_id)` requests `GET /movies/ID?extended=full` and projects
`ids.trakt`, `title`, nullable `year` and nullable `released`. The response Trakt ID
must equal the requested ID. A non-null release value must be a valid ISO date;
it remains a provider-supplied date, not a selected regional streaming release.

`episode_details(show_id, season, episode)` requests the corresponding episode path
with `extended=full`. Its result is `{"show_id": ID, "episode": {...}}`, containing
the episode's actual Trakt ID, nullable title, season, number and nullable first-air
timestamp. Coordinates must match the request. Callers joining a paused episode
must also compare its Trakt ID with this response; a request coordinate alone does
not prove that the paused identity matches the returned episode.

`calendar_shows(start_date, days=7)` requests exactly
`/calendars/my/shows/START/DAYS?extended=full`. `calendar_arguments` validates an
ISO `YYYY-MM-DD` date, integer day count 1–31 and a representable exclusive end date.
The result is `{"start_date": START, "days": DAYS, "entries": [...]}`. Each entry
projects outer `first_aired`, show identity/title/year and episode identity/title/
season/number/first-air metadata. Unknown episode titles or nested timestamps remain
null. A non-null nested first-air timestamp must agree with the outer instant.

The calendar is ungrouped. Grouped season cards, pagination headers, duplicate episode
IDs or coordinates, malformed dates and rows outside the UTC half-open window fail
the entire read. The client's configured item bound also applies. No pagination or
retry is invented for a complete-array endpoint. Summary endpoints likewise reject
pagination metadata. All new inputs are validated before credential refresh; existing
session generation checks still bracket network work. The transport permits only
these fixed-host paths with the exact extended query and no global-calendar fallback.

## Upcoming view

`trakt_calendar.upcoming(session, start_date, days=7, *, now=None, allowed_show_ids=None)`
normalizes the personal feed under one account generation and local data revision.
It accepts at most 1,000 rows and the same local 31-day window. Only valid instants
strictly later than `now` and inside the requested UTC window are returned. Watched
status stays `None`, and `playable` stays false. Unknown episode names use an explicit
`Episode SxxExx` label rather than inventing a programme title.

An optional allowed-show set filters the existing personal feed. It cannot make the
feed contain every show from a selected or liked list. The client rejects duplicate
rows; the separately injected normalized-view seam may collapse identical duplicates
while rejecting conflicting identity or timing. No persistent cache, account activation,
playback or service mutation is introduced.

## Evidence limits

Client/session/HTTP-framing fixtures exercise identity mismatch, malformed or nullable
metadata, UTC boundaries, calendar scope, incomplete responses, no-I/O input rejection
and account replacement. These are offline contract checks, not live integration tests.

## Current calendar contract recheck

On 14 November 2026, the official contract was rechecked at calendar revision
[`b2308e4a078e4f4779871580bc7895f0e8b6a98d`](https://github.com/trakt/trakt-api/tree/b2308e4a078e4f4779871580bc7895f0e8b6a98d/projects/api/src/contracts/calendars).
The GET show calendar still specifies a UTC date window and array response. The
[request schema](https://github.com/trakt/trakt-api/blob/b2308e4a078e4f4779871580bc7895f0e8b6a98d/projects/api/src/contracts/calendars/schema/request/calendarParamsSchema.ts)
still describes `my` as watched, collected or watchlisted items plus individual
watchlisted episodes. HomeFX omits the optional grouping parameter so entries remain
per episode. No upstream code/assets were copied and no service terms were accepted.
This source inspection is not a live entitlement or TV check. The Development
candidate uses a fixed seven-date window; public/Production activation remains gated.
