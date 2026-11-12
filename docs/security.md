# Security design

Current preview: no outbound requests or accounts. Only synthetic watched overrides
and demo list selection are saved in the Kodi profile. Reset clears these overrides.
The package includes only an explicit file list. Do not package any user profile.

Future service integration must use supported public-client authentication without
shipping a client secret. Keep user tokens out of plugin URLs, logs and diagnostics.
Serialize token refresh and atomically replace rotated tokens. Kodi profile storage
is not a vault against other code running inside Kodi. Specify disconnect, revocation,
cache retention and account-switch behavior before connecting real accounts.

Validate remote responses, bound requests and caches, retain TLS verification, handle
rate limits and cancellations, and avoid duplicate watch-history writes. Read-only
metadata access and Trakt write actions have separate acceptance criteria.

Before release: review dependencies and exact licences, scan source/history for
secrets, inspect packaged bytes, and record scanner coverage and failures. Original
artwork may be shipped; third-party skins/art/code require a separate provenance and
compatibility review. Design for content users are authorized to access.
