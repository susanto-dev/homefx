# Explicit service assembly

The `service_runtime` module assembles existing components for later account
integration. The public Preview entry point does not import it or supply live configuration.
The deliberate Development video candidate calls it after explicit actions with
its own profile and public Development configuration; startup does not authorize. Import performs
no storage or network I/O. Device registration, permissions/TLS checks and live
acceptance remain required before activation.

`build_trakt(profile, client_id, redirect_uri, *, clock, monotonic, cancelled,
connection_factory)` returns a redacted bundle with `session`, `library` and
`disconnect(expected_generation=None)`. It joins private token storage, account-bound
list preferences, bounded invocation-memory caching, shared request limits, verified
fixed-host HTTPS transport and the session/library. History/list mutation callbacks
are deliberately absent: the assembled session reports `writes_disabled` rather
than sending a mutation. The bundle's disconnect uses the library to clear saved
list choices and invocation cache as well as local credentials.

`build_debrid(profile, public_client_id, *, clock, monotonic, cancelled,
connection_factory, pending_response=None)` returns a redacted bundle with `session`
and generation-aware `disconnect`. It joins the separate private provider store,
mandatory shared request budget, fixed-host transport and session. No pending-error
classifier is guessed; an optional classifier must be separately verified trusted
code. Its default remains fail-closed.

Both factories use wall time and monotonic time by default, a false cancellation
probe, and standard-library `HTTPSConnection`. Alternate callbacks are trusted test
seams, never user settings or service data. The factories expose no arbitrary host,
proxy, transport-size or timeout options. They retain the existing bounded transport
defaults and certificate verification. They accept no bundled client-secret option.
User-bound provider credentials still belong solely in the existing private store.

## Validation and effects

All identity, redirect syntax, callback and initial clock/cancellation checks run
before creating profile files. The profile must be absolute and must not be a root,
contain `..`, or resolve through symlink ancestors. Existing relevant SQLite files
and journals must be regular, singly linked files; private-store directories cannot
be symlinks or non-directories. Filesystem parents must remain quiescent during
assembly. This is not a security boundary against other code running as Kodi.

Redirect validation checks an absolute URI's syntax and rejects embedded userinfo or
fragments, raw whitespace/control characters, backslashes and malformed percent escapes. It allows URN/custom schemes as well as HTTP(S) syntax. It does not prove
that Trakt registered or accepts that URI, and never opens it. Supply the actual
registered redirect; no default URI, callback server or always-on service is invented.

Construction explicitly opens private SQLite stores and may validate/recover their
local records through the existing store constructors. It does not issue requests,
authorize, refresh or resolve media. Failure after validation can leave empty private
stores; unrelated files are not removed. Setup errors use fixed categories and do
not expose paths, public identity values or raw exceptions. A disconnected status
is not proof that a service account or connection works.

The shared limiter is mandatory in these assemblies. Real-Debrid's local-profile
250-attempt/rolling-minute budget spans OAuth and REST; Trakt uses shared server
429 cooldowns without a guessed numeric quota. Provider budgets remain separate.
Different devices/profiles are not coordinated, and account disconnect does not
reset the provider budget. Store access itself uses the existing bounded SQLite
transactions; Android behavior remains unverified.

## Interaction and evidence

The bundle can supply `session` and `disconnect` to the injected account interaction
controller. Constructing that controller still does not start authorization. No
factory performs confirmation or token display itself; an explicit future UI action
must own the authorization flow, cancellation and cleanup.

Tests construct actual temporary stores and use fabricated HTTPS framing. They
verify no connection during construction, validation before writes, unsafe-profile
rejection, private file permissions, provider isolation, mandatory shared limits,
429 cooldowns, read-only Trakt actions and generation-aware local cleanup. These
are integration contracts, not live provider, Kodi dialog or TV acceptance results.


A future caller should pass the same UI cancellation probe to the factory and account
controller, for example `cancelled=ui.cancelled`, so transport checks observe dialog
cancellation too. The default probe never requests cancellation. Socket deadlines
remain necessary: neither UI polling nor this assembly can forcibly interrupt an
arbitrary blocking callback or operating-system DNS lookup.

The [joined video dispatcher](video-integration.md) supplies the same active UI
cancellation callback to this factory and the interaction. It remains uncalled by
the public Kodi entry point; factory reuse is not public live activation.
