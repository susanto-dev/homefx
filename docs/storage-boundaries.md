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
unlinked open descriptor or a safely reopened inode. The descriptor must still be
a bounded private regular file with no multiple hardlinks; nonblocking/no-follow
opening remains in place. Without no-follow support, inode changes remain rejected.
The mandatory database retains its strict inode and single-link checks. No retries,
sleep changes, corruption resets or storage/isolation checks are removed.

A deterministic regression commits a real SQLite write after the journal is opened
but before the descriptor is inspected. Additional cases test safe recreation,
unsafe replacement descriptors and mandatory-database unlink/replacement. These
reproduce the guard failure without relying on scheduler timing.
