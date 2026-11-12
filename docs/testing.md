# Testing

Install `tools/build-requirements.txt` first. Run `python3 -m unittest discover -s tests -v` from the repository root.
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
repository stays outside the site directory. Run TV fresh-install/upgrade tests only
after the separate publication gates are met; no remote update passed in CI.

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
