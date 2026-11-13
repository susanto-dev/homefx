# Local storage boundaries

The 0.13 preview strengthens existing storage without enabling provider accounts
in Kodi. Tests use temporary files and fabricated credentials only.

Trakt token and preference stores reject symlink ancestors, non-regular or
multiply linked database files, and unsafe SQLite journal/WAL/shared-memory
sidecars. Database descriptor checks precede file-permission changes; connection paths are
checked again for later operations. Existing private stores are opened without
implicitly recreating a missing database. Preferences also enforce a bounded
store size. A valid legacy store can have its permissions tightened during setup;
unsafe paths are rejected before that step.

Only a newly created credential database is initialized. Existing empty,
incompatible or malformed databases produce fixed error categories instead of
resetting credentials or selections. Valid preference formats migrate to the
current schema, preserving account-bound selection order. Schema checks include
the account primary key, so later saves cannot silently create duplicate accounts.
Epochs, revisions and token generations must be bounded integers; exhaustion
fails before mutation. Invalid stored claims or clocks fail closed. Refresh
completion samples the clock after acquiring the write lock, so waiting for a
lock cannot extend a refresh claim's deadline.

The demo state retains its existing recovery behavior for missing or malformed
ordinary files. Reads are bounded and use nonblocking/no-follow flags where the
platform supplies them, with regular-file checks before reading. Saves reject
unsafe paths and use a flushed temporary file followed by atomic replacement.
A failed save attempts to remove its own temporary file and reports a fixed error.

These checks assume ancestor paths remain quiescent during an operation. They
are not a vault against another process running as Kodi, a guarantee of forensic
erasure, or a hard filesystem latency deadline. Android filesystem and SQLite
behavior still require device testing. No automatic private-store repair or
credential recovery workflow is enabled. Do not edit or upload account databases;
a future explicit recovery flow must preserve account isolation and handle
incomplete cleanup without claiming success.

Integration regressions open baseline stores through the actual service factories,
refresh synthetic credentials while retaining list choices, reject stale
operations, and exercise malformed data and sidecar substitutions after assembly.
They prove neither live authentication nor successful TV installation/playback.

## Provider credentials and request limits (0.14)

Real-Debrid credentials and shared request limits now open existing stores without
creating a replacement when a database disappears. Creation uses an exclusive
file-open decision; an existing file is never treated as a newly created store.
Baseline table shape and key constraints are checked before ordinary transactions
can change state. Valid baseline stores remain compatible without schema migration
or credential reset; ordinary lifecycle transitions still apply. Malformed stores
fail without automatic reset or repair. SQLite sidecars remain subject to
the same regular-file and link checks.

Real-Debrid refresh completion now samples time after acquiring the write lock.
A claim expiring while the operation waits requires authorization again; it cannot
be accepted using an earlier timestamp. Secret clearing, single-use refresh claims,
generation checks and provider isolation remain intact. Request limits already
sampled time after locking and continue to count failed issued attempts, combine
server cooldowns with the rolling quota, and avoid sleeping or retrying requests.

Synthetic integration tests exercise these failures through actual factories and
sessions. A rejected local store prevents provider traffic. These checks do not
change the quiescent-path assumption above or prove Android filesystem behavior.

## Concurrent preference journals (0.14.1 repair)

SQLite DELETE journals are transient: a normal commit can unlink an already opened
file, and the next transaction can recreate its pathname with a new inode. The
preference guard previously treated these normal transitions as database-path
replacement and rejected valid concurrent operations. Only sidecars now accept an
unlinked inode during path or descriptor inspection, or a safely reopened inode. The descriptor must still be
a bounded private regular file with no multiple hardlinks; nonblocking/no-follow
opening remains in place. Without no-follow support, inode changes remain rejected.
The mandatory database retains its strict inode and single-link checks. No retries,
sleep changes, corruption resets or storage/isolation checks are removed.

Deterministic regressions commit real SQLite writes during initial path inspection
and after journal open but before descriptor inspection. Additional cases test safe recreation,
unsafe replacement descriptors and mandatory-database unlink/replacement. These
reproduce the guard failure without relying on scheduler timing.

## Shared sidecar lifecycle (0.14.2)

Trakt tokens, Real-Debrid credentials and request limits also distinguish transient
SQLite sidecars from the mandatory database. A sidecar may have zero links in a
stat result when SQLite commits during path lookup. It must still be a regular
file, and multiple hardlinks remain rejected. The mandatory database still requires
exactly one link; deleted databases are not recreated by later operations. Existing
path, schema, refresh-generation and quota/isolation checks remain unchanged.

Real SQLite commit regressions cover reads and constructor reopen for all three
stores, including preserved committed generation/cooldown values. Negative cases
cover unlinked mandatory databases and symlink, hardlink, FIFO and directory
sidecars. This is a correction to the same journal-lifecycle class as 0.14.1, not
a general relaxation of database path checks or an account activation.

The service-factory preflight uses a single non-following stat inspection instead
of separate existence and stat calls. It applies the same sidecar-only zero-link
rule, including preference journals, before constructing components. Real-commit
factory tests preserve stored generations, epochs and cooldowns without provider
traffic; unlinked mandatory databases remain rejected before construction.

## Conditional list confirmation (0.15)

The preference save optionally compares the caller's expected ordered choices in
the same BEGIN IMMEDIATE transaction as its existing clear-epoch check and write.
A chooser opened before another local selection changed cannot overwrite that
selection after confirmation. This adds no schema migration; existing callers
without expected choices retain their behavior. Credential generations and verified
account UUIDs remain separate checks around the UI interaction.

## Widget identity (0.16)

Preference schema 3 stores a generated profile key alongside existing selections
and clear state. Valid old schemas migrate transactionally; missing/malformed
version-3 key state is never regenerated. HMAC references bind account, list and
clear epoch; item references also bind kind/title identity. Keys stay in private
storage and references do not authorize access. Fresh account/selection/epoch
checks reject stale resolves and presentation. No schema downgrade is supported;
older packages require a separate compatible profile. See [routing](widget-routing.md).

## Serialized demo mutations (0.17.2)

The authoritative demo data remains `demo.json`; its format and read-only load
behavior are unchanged. `state.update` applies only a confirmed selection, watched
flag, movie add/remove or explicit reset to the latest state under a shared SQLite
lock. The complete-replacement `save` API participates in the same serialization.
No UI dialog or network operation runs while the lock is held. A reset deliberately
replaces every field; overlapping edits to the same field follow lock acquisition
order, not the time a dialog opened.

The sibling `demo.json.lock.sqlite3` contains lock metadata only, not list selections,
watch data, credentials or tokens. Each SQLite lock acquisition uses a 0.25-second
busy timeout; first initialization can require two write-lock acquisitions. Filesystem
operations are not guaranteed wall-clock deadlines. Busy/error outcomes
produce the existing fixed save failure, without update-success notifications or
automatic retries. SQLite is loaded only for a mutation, so browsing and Device
readiness do not depend on opening this lock. Missing SQLite prevents local edits.

Lock paths, metadata and SQLite sidecars are checked. Metadata inspection uses
SQLite-managed connections: directly opening and closing the database file can
release another connection's POSIX locks. First-use checks inspect transient sidecars
before the persistent database so concurrent creation is not mistaken for an orphan; unsafe, unrelated or corrupt
lock files are not reset or silently adopted. This is separate from the retained
malformed ordinary demo JSON recovery behavior. Ordinary reads do not create a
lock file. Updated writers cooperate through the same lock, and atomic JSON
replacement keeps readers from observing a partial document. This is not a
multi-file atomic transaction or protection against an active filesystem attacker.
Restart Kodi after upgrading so earlier invocations cannot bypass the lock. Avoid
mixing updated writers with older versions or external editors.

Concurrency, initialized-lock process-exit release, failure and dialog tests use
synthetic data. Interrupted or corrupt initial lock setup can fail closed and is
not automatically repaired; the JSON remains authoritative. Real Android
SQLite/filesystem behavior, cancellation and restart persistence still require TV
acceptance. The Trakt/Real-Debrid private stores and activation gates are unchanged.
