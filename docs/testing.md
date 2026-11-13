# Testing

Install `tools/build-requirements.txt` first. Run from the repository root:

```sh
python3 tools/run_tests.py --summary dist/tests/summary.json
```

The standard-library runner discovers the same unittest suite as
`python3 -m unittest discover -s tests -v`, which remains supported. For a focused
run, add `--pattern 'test_trakt_tokens.py'`. The JSON report contains aggregate
counts only, never test names, failure messages, paths, account values or skip
reasons. Verbose console output remains available for diagnosing synthetic tests.
A passing suite with skipped tests is not a full pass of those skipped checks.
Empty discovery, errors, failures, unexpected successes and report-writing failures
return a nonzero exit code. Expected failures and skipped tests remain visible;
counts are not a code-coverage percentage or device acceptance result. Passed
counts come from successful test cases directly, not subtraction. Failed subtests
and fixture errors can produce multiple outcomes per test, so outcome totals need
not equal the number run.

Validation runs the complete suite on Python 3.8 and 3.12. Each job publishes the
aggregate JSON in its job summary and as a seven-day artifact, including after
test failure when a report exists. Publication uses the same runner before building
the preview. A missing report is explicitly reported as unavailable, never as a
pass. Existing failure gates, immutable Action pins and read-only PR permissions
remain in place; no new test dependency or hosted service is required.

Tests cover explicit synthetic expected orders/dates, episode identity, calendar
boundaries, watch-state overrides, search, related-title order, continuation choices,
URL encoding and malformed routes, local state recovery, reproducible ZIP bytes,
private-file exclusion, and rejection of deliberately broken manifests/files.
Profile token databases and journals are explicitly exercised as excluded files.

Expected values are independently specified. Keep the injected date fixed in logic
tests. Error and empty paths matter as much as happy paths. A package allowlist
prevents accidental inclusion of extra files but cannot detect a secret pasted into
an allowed source file; source review and future secret scanning remain necessary.

Kodi adapter tests use narrow stand-ins to verify route wiring, metadata and menu
construction. They do not establish actual Kodi API compatibility or rendering.
Cloud checks do not establish installation, home-widget behavior, navigation,
performance, playback, subtitles, resume, or scrobbling on Android/Google TV.
Record those separately with exact versions and the package hash.

Action audit tests require the optional security tool environment. They deliberately
reject floating tags, short/dynamic refs and nested unpinned Actions; mocked release
responses exercise annotated-tag resolution and update reporting. The security job
runs these tests explicitly. Plain standard-library runs skip this optional suite.

Trakt foundation tests inject fabricated responses and clocks. They cover polling
intervals and terminal states, cancellation, malformed credentials, durable refresh
ownership, atomic token replacement, interrupted refresh and disconnect races,
sanitized errors, pagination bounds and API failures, list identity/ownership, and
the separation of metadata, watched progress and paused playback. Future and unknown
air dates must not become aired-unwatched candidates. None of these tests establishes
that a real Trakt account or HTTP transport works.

Connectivity tests cover fixed-host request allowlists, TLS configuration, rejected
redirects, bounded response bodies and JSON nesting, cancellation/deadline handling,
connection lifetime, sanitized failures and account/session changes. Combined tests
pass fabricated HTTP bodies through transport, session and library into selected lists,
including refresh and cross-account cache invalidation. Cache tests include TTL,
copy isolation, bounded retention and failed/incomplete responses.

Repository tests check the actual packaged manifest/index relationship, deterministic
bytes, ZIP/index checksums, invalid IDs/versions/unsafe XML/archive members, private
file exclusion and refusal to replace differing candidate output. The candidate
repository stays outside the site directory; a separately verified preview channel is
embedded for publication. TV fresh-install/upgrade tests remain required; no remote
Kodi update passed in CI.

The 0.4.0 preview tests local saved-movie persistence/migration, future-release
membership, duplicate-safe additions, cancelled removals and all/aired-unwatched
folder filters. Account preference tests exercise verified UUID boundaries,
refresh/restart retention, private storage and account-switch races. Action tests
use fabricated history/list responses, never actual writes, and cover ambiguity,
no replay, rejected liked lists and stale-account outcomes. Cache revision tests
prevent an action from leaving an invocation's previous watch/list result in use.

Retention tests verify that older validated packages remain available while only
current versions enter the index; conflicts, numeric version ordering, malformed
inventories, unsafe paths and corrupt retained packages must fail. A local integration
check can reuse a published HomeFX ZIP after verifying its known reviewed checksum;
this is packaging evidence, not a Kodi upgrade or rollback test.

Readiness tests reject arbitrary private strings/raw exceptions and prove the report
route skips profile loading and network calls. Account-flow tests use synthetic codes,
fake clocks/UI and injected requests to exercise replacement confirmation, timed polling,
expiry/cancellation, stale confirmations and cleanup failure. No real user authorization
or Kodi dialog responsiveness is inferred from these tests.

Detached-repository verification tests deliberately alter index, inventory, sidecars,
ZIPs/assets and topology, then require rejection without repairing or changing inputs.
Valid retained-version candidates must still verify. After marking a draft ready,
check the newly triggered validation/security runs rather than reusing earlier green
checks from before promotion.

The 0.6 regression suite covers list/date boundaries, season counts and scope, safe
empty widget directories, duplicate or malformed route arguments, and fixed UI error
messages. Mocked Trakt view tests cover unknown watched status and account/revision
changes during joined reads. Repeatability tests deliberately change output bytes,
add unexpected files and corrupt candidates to prove the check rejects them.

Real-Debrid tests use fabricated device/credential/token responses, pending-response
classifiers, entitlement/download data and resolved links. They exercise cancellation,
expiry, pagination and uncertainty without contacting the service. Combined workflow
tests pass a mocked grant through the REST client to a fake player callback and prove
account change after resolution prevents dispatch. Single-attempt locks do not establish
cross-process playback ownership; callback acceptance is not a TV playback test.

The 0.8 suite adds actual temporary SQLite transactions for provider persistence and
competing refresh claims, injected HTTPS framing for the provider endpoints, and
session/account-change recovery tests. Complete movie-history tests distinguish an
authoritative empty snapshot from failures, pagination and malformed rows. Provider
network tests use in-memory connections or local socket pairs, never account traffic.


The 0.9 suite checks preview/bootstrap byte equality, immutable release inventories,
exact staged-versus-hosted bytes with injected HTTP responses, and fatal lint failures.
Search and related-movie tests preserve metadata-only semantics and unknown watched
state. Shared-limit tests use temporary SQLite files and concurrent reservations;
transport tests exercise local blocking and server cooldowns without service traffic.
Install all hash-locked tool inventories for the complete suite; run `tools/check_quality.py`
and `tools/release_history.py releases/inventory.json --base-ref <review-base>` as well.
The full official Kodi add-on checker remains pending for the reasons in
[tooling licences](tooling-licenses.md).

The 0.10 suite exercises complete-series joins across actual session, token-store,
client and library boundaries with fabricated provider responses. It checks known
count mismatch, unexpected pagination, request/row bounds, unknown watched status,
explicit specials, and refresh/account changes during a compound read. Playback
observation tests separate dispatch from AV start and never infer watched completion.
Widget setup tests verify fixed routes and local repository-version reporting before
profile access. These remain mocked or local checks, not TV or live-service evidence.


The 0.11 tests exercise enriched resume and calendar joins through actual client and
session code using fabricated HTTP responses. They cover missing release metadata,
watched precedence, identity conflicts, changed accounts/revisions, bounded requests,
UTC windows and personal-calendar filtering. Release-proposal tests prove existing
records stay immutable and invalid input cannot leave a promoted partial proposal.
No live account, device or playback acceptance is inferred.

The 0.12 suite exercises both account assemblies through actual private stores,
framed fabricated HTTPS responses, provider sessions, the account controller and
injected dialogs. It checks no construction-time network, invalid configuration
before storage, readonly Trakt writes, shared cooldowns, cancellation, replacement
races and provider-isolated disconnect. UI stand-ins establish API contracts only;
they do not prove Kodi dialog behavior or TV responsiveness.

The 0.13 storage regressions cover unsafe ancestors, hardlinks, special files,
SQLite sidecars, malformed schemas and records, integer exhaustion, and a refresh
claim expiring while waiting for a write lock. Assembly tests preserve baseline
credentials and list selections across refresh and reject unsafe later operations.
All account values are synthetic; platform-specific TV behavior is still untested.

The post-0.13 regression batch covers competing unfinished items, later-episode
resume priority, exact UTC air boundaries, watched precedence over paused metadata,
and retained routes for deselected lists. Account tests cover cancellation after
confirmation, malformed UI callbacks, issuance deadlines and atomic rate-limit
rollback. Playback contract tests use synthetic player callbacks and account
generations; they do not establish a real Kodi adapter connection. Runner tests
exercise failed/skipped/expected-failure outcomes and redacted aggregate reporting.

The dependency/manifest batch tests strict requirement declarations, malformed and
conflicting pins/hashes, and fixed offline inventory reporting. Source-manifest
mutations check that dependencies, extension points and metadata match the current
preview contract before packaging. Unchanged packages must still reproduce exactly
and preserve the published inventory. These are project-specific gates; the full
official Kodi checker remains pending.

The 0.14 storage regressions exercise refresh claims expiring during SQLite lock
waits, missing databases after assembly, incompatible table constraints and safe
creation classification. Service-level tests verify rejection before provider
requests and compatibility of valid stored credentials and shared limits. All
credentials, clocks and responses remain fabricated; real authorization and Kodi
playback are outside automated acceptance.

The 0.14.1 repair reproduces normal journal unlink with a real SQLite commit at
the open/descriptor boundary, and checks recreated sidecars against unsafe
symlink, hardlink, FIFO, permission and size replacements. Mandatory database
identity and missing-file rejection remain asserted. Existing concurrent account
retention tests remain unchanged; repeated runs supplement deterministic cases.
