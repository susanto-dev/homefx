# Backlog

| Batch | Scope | State / exit condition |
|---|---|---|
| 1 | Mocked widgets, context menus, guidance, tests, local ZIP | Includes saved movie collection and aired-unwatched episode filter; TV acceptance pending |
| 2 | Trakt authentication feasibility | Mocked lifecycle, protected token rotation, transport and session coordination implemented; registration/live login/refresh still pending ([evidence](trakt-authentication.md)) |
| 3 | Personal lists and watch progress | Read API, normalized views and invocation-memory library cache mocked; account-bound selections and explicit watched/list-add contracts mocked; live UI/write validation and persistent metadata caching pending |
| 4 | Umbrella playback experiment | Pending: installed version, movie/episode identity, cancellation, subtitles, resume, one scrobbling owner, next-episode choice |
| 5 | Repository installation and updates | Local generation plus checksum-pinned version retention implemented; fresh install/upgrade and channel publication pending |
| 6 | Optional native playback / skin changes | Only if a demonstrated need justifies scope and licensing review |

Real recommendations need a reviewed metadata provider and terms. Upcoming movie
release dates require a defined release type/region; they do not prove playability.
No batch depends on a separate always-on server or standalone Android application.

## Combined batch: Activation readiness (0.5.0)

Three parallel sub-batches prepare the next real-device validation step:

1. A visible Device readiness report shows bounded local version/capability fields,
   without opening account profiles, exporting diagnostics or contacting services.
2. An injected account-flow controller tests confirmation, device polling intervals,
   cancellation, bounded waits and disconnect failure semantics. It is not wired to
   the Kodi connection menu; registration/live/device gates remain unmet.
3. A standalone read-only repository verifier checks detached candidate topology,
   index/package/inventory checksums and references before artifact upload. It does
   not publish, install, execute retained code or certify provenance.

Validation and Security scans already ran on PR creation/update/reopening. Their
explicit event lists now include ready_for_review, so promotion reruns checks.
These workflows report checks/artifacts only and do not post PR comments.

Next external gates: run the readiness screen and TV checklist; register a Trakt
application and provide its public client ID/registered redirect URI (never its
secret); verify actual login/refresh before enabling account routes. Real data views,
action outcomes and playback still require service/device testing. Repository
activation remains separate, after retained-version review and install/upgrade tests.
