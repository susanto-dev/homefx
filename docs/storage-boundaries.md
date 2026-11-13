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
