# Backlog

| Batch | Scope | State / exit condition |
|---|---|---|
| 1 | Mocked widgets, context menus, guidance, tests, local ZIP | Includes saved movie collection and aired-unwatched episode filter; TV acceptance pending |
| 2 | Trakt authentication feasibility | Mocked lifecycle, protected token rotation, transport and session coordination implemented; registration/live login/refresh still pending ([evidence](trakt-authentication.md)) |
| 3 | Personal lists and watch progress | Read API, normalized views and invocation-memory library cache mocked; account-bound selections and explicit watched/list-add contracts mocked; live UI/write validation and persistent metadata caching pending |
| 4 | Playback strategy and Umbrella experiment | Handoff unverified; compare its installed interface with direct resolution before choosing the first live path |
| 4a | Real-Debrid | Inactive OAuth/API contracts and playback coordination mocked in 0.7; registration, protected storage, bounded transport and device validation pending |
| 4b | Source discovery and playback ownership | Select a lawful source input/provider; metadata alone is insufficient. Decide one resume/scrobbling owner and validate next-episode behavior |
| 5 | Repository installation and updates | Local generation plus checksum-pinned version retention implemented; fresh install/upgrade and channel publication pending |
| 6 | Optional native playback / skin changes | Only if a demonstrated need justifies scope and licensing review |

Real recommendations need a reviewed metadata provider and terms. Upcoming movie
release dates require a defined release type/region; they do not prove playability.
No batch depends on a separate always-on server or standalone Android application.

## Combined batch: Real-Debrid and playback foundation (0.7.0)

Four parallel slices make the previously architectural Real-Debrid dependency explicit:

1. An inactive, injected open-source device authorization contract, using user-bound
   credentials obtained after consent rather than shipping a shared client secret.
2. Mocked account, bounded download-list and explicit link-resolution API contracts.
3. An inactive playback attempt coordinator separating title identity, supplied source,
   resolution and player acceptance, with cancellation and account-generation checks.
4. A Kodi playback/setup information screen that opens without reading account profiles.

No real account, source resolution or playback is enabled. Detailed sequence, costs,
security boundaries and external gates are in [the playback plan](playback-plan.md).
Source discovery remains unresolved: Trakt metadata and a debrid account do not identify
an authorized source for every title. Umbrella is an experiment, not a verified handoff.

Next device work: install the preview, record Device readiness, verify existing widgets,
and read setup guidance. Then verify registrations, storage/TLS and one authorized
movie/episode source on the TV before enabling a live route. Watch-history completeness,
real recommendations, scrobbling and repository installation/updates remain separate gates.
