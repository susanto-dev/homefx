# Title search and related movie contract

This inactive service layer supports literal movie or series title searches and
related movies. No live routes, context menus, login changes, artwork downloads,
source resolution, or player calls are enabled by it. Mock responses validate the
implementation; no account, TV, or live API integration has been tested.

## Primary evidence

Contracts were inspected at the immutable official `trakt/trakt-api` revision
`030a5e3cb6aacb11508f250865c0b907ab17b2ed`:

- [Search contract](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/search/index.ts): `GET /search/:type`, pagination, relevance order, literal operator escaping, and the documented `fields=title` option for movies and shows. `fields` is documented in the endpoint description although the adjacent query schema only explicitly declares `query`.
- [Related movies contract](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/movies/index.ts): `GET /movies/:id/related`, pagination, and an array of movie metadata. The optional `personalized=true` ranking is described as VIP. HomeFX does not request it.
- [Movie search wrapper](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/search/schema/response/searchMovieResponseSchema.ts) and [show search wrapper](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/search/schema/response/searchShowResponseSchema.ts): type, score, and nullable movie/show objects. Unusable null metadata fails closed rather than silently dropping titles.
- [Movie metadata](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/_internal/response/movieResponseSchema.ts) and [show metadata](https://github.com/trakt/trakt-api/blob/030a5e3cb6aacb11508f250865c0b907ab17b2ed/projects/api/src/contracts/_internal/response/showResponseSchema.ts): title, optional year, IDs; dates require extended metadata and images have their own extension.

These are contract references, not copied implementation or bundled assets.
Original HomeFX code and synthetic fixtures implement a deliberately smaller
contract. API access and rights to service data or artwork remain subject to the
service's terms; the project's licence does not grant those rights. The ordinary
search/related descriptions do not identify a paid requirement, but no account
entitlement or future pricing is asserted. No new paid dependency is introduced.

## Runtime API and bounds

`Client.search_titles(query, kind="movie")` accepts only `movie` or `show`.
`search_arguments` rejects non-string, empty, whitespace-only, and over-128-character
queries before requests, including before session refresh. All Unicode categories
beginning with `C` are rejected (controls, format characters, surrogates, private-use,
and unassigned characters). Leading and trailing whitespace is stripped; interior
spacing and Unicode letters are preserved. There is no lowercasing or fuzzy match
expansion. Unsupported kinds fail before requests.

Each search operator character in `+ - & | ! ( ) { } [ ] ^ " ~ * ? : /` and literal
backslash is escaped with a preceding backslash. `urlencode` then encodes the query;
escaped decoded text is at most 256 characters. The route is `/search/movie` or
`/search/show` with exactly `query`, `fields=title`, `page`, and `limit` parameters.
This is a literal title query, not a caller-controlled URL or search expression.

`Client.related_movies(trakt_id)` accepts a positive integer below `2**63`, rejects
booleans/string IDs, and calls `/movies/{id}/related` with only `page` and `limit`.
Neither method requests `extended`, `images`, or personalized ranking. Both use the
existing authenticated GET transport and bounded pagination (default 100 per page,
20 pages, 2,000 items). A full page without pagination-count evidence, invalid page
headers, duplicate identities, a later page failure, or exceeded bounds fails the
whole result; partial recommendations are not returned.

Basic title/identity/year shape is validated before client results return. Titles
must be nonblank, at most 1,024 characters, and contain no category-C characters.
Years may be missing/null; if present they must be integer 1–9999. Scores do not
change server ordering. Extra metadata fields are ignored by the normalized view.

`Session.READS` includes both operations. `Library.search_titles(query, kind)` and
`Library.related_movies(id)` normalize to rows containing `kind`, `trakt_id`,
`title`, `year`, `watched=None`, `release_status="unknown"`, and `playable=False`.
The latter means no attached playback action; it is not evidence that a title has
no authorized playable source. Neither a year nor a show's premiere proves that
episodes are available. Release country/date and watch history are not guessed.
No watched snapshot is fetched for these metadata-only views.

Library reads use the existing account-generation and mutation-revision checks,
including a final check after normalization. Cache copies are invocation-memory
only, account isolated, bounded, and invalidated on guarded read failures. Search
terms and results are not written to preferences, logs, URLs in error messages,
or a search-history endpoint. Results preserve API order rather than the home
widget's progress/date sorting.

## Remaining acceptance

The transport allowlist must accept only the specified routes and parameters,
strictly decode search query UTF-8, and retain existing TLS/redirect/response bounds.
Before UI activation, validate literal search behavior and real account API limits,
then test TV navigation, keyboard entry, stale results, and context-menu behavior.
Similar movie suggestions remain metadata from Trakt's related endpoint, not a
promise of recommendation quality, playback availability, regional release,
watch status, or permission to reuse artwork.

## Selected-list descriptions and ratings

The Development Video selected-list request already uses `extended=full`. Its
normalized movie/show rows now retain an optional synopsis (up to 4,096 characters)
and a finite 0–10 Trakt rating with a positive integer vote count. Missing or invalid
optional fields are omitted without making a valid title unavailable. No additional
per-title request is made. Search/related routes and episode metadata are unchanged.

The existing folder/widget adapter supplies the synopsis and named `trakt` rating
to Kodi, and labels the score and vote count in the plot and movie detail dialog.
Service text cannot inject Kodi formatting. Watch state, dates, account isolation,
opaque routes and non-playable behavior are unchanged. Actual score presentation
is skin-dependent and has not been tested on TV. No IMDb or critic score is inferred
from a Trakt community rating. Artwork remains the local placeholder.

## Next metadata provider decision

Provider documentation inspected on 14 November 2026:

- [TMDB API FAQ](https://developer.themoviedb.org/docs/faq): non-commercial use is
  free with attribution; commercial use needs a licence discussion. Registration
  requires the owner to accept service terms. Its required approved logo and
  non-endorsement notice belong in an About/Credits surface before activation.
  Recommend this provider for posters/backdrops, matched by IDs rather than title
  guesses, after reviewing credential distribution and image/cache requirements.
- [IMDb non-commercial datasets](https://developer.imdb.com/non-commercial-datasets/):
  personal/non-commercial subsets include title IDs and ratings, but the listed
  datasets do not supply poster images or plot summaries. Their terms do not grant
  unrestricted redistribution. Do not scrape IMDb pages or bundle their images.
- [Rotten Tomatoes licensing](https://www.rottentomatoes.com/help_desk/licensing):
  application/API/data-feed use requires submitting the proposed use for review;
  attribution and links back are required. No approval or free licence is assumed.
- The official Trakt response contract above exposes `overview`, `rating` and
  `votes` under `full`, with images as a separate extension. An image field alone
  is not proof of entitlement or permission to reuse its upstream artwork.

No new provider credentials, network endpoints, third-party artwork or paid service
are introduced in this batch. Original source licensing does not relicense service
metadata. The owner must register/accept any new provider terms; credentials must
not be pasted into chat or committed. A build secret embedded in a public ZIP would
still be public, so it is not a credential-distribution solution.

## TMDB artwork cache candidate

TMDB is now the owner's chosen artwork direction. The [bounded artwork cache](tmdb-artwork.md)
retains paths only and is not yet wired into Kodi. List normalization retains an
optional validated TMDB ID without additional reads or altering Trakt identity.
Registration/terms, credential delivery, attribution and image-retention decisions
remain activation gates. Existing synopsis and Trakt-rating display is unchanged.
