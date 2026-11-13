# Real-Debrid and playback

Real-Debrid is part of HomeFX's plan. The 0.9 preview retains inactive provider storage/transport/session foundations and a
setup information screen; it does not sign in, resolve a real source or start Kodi's
player. Existing widgets and the installed skin remain the browsing surface.

## Responsibilities and first live path

| Component | Responsibility | Current evidence |
|---|---|---|
| Trakt | Title identities, personal lists and watch state | Mocked; live routes disabled |
| Source input/provider | Locate a specific source the user is authorized to access | Provider and discovery workflow undecided |
| Real-Debrid | Account authorization and resolution of supplied supported links | Original injected contracts tested with fabricated responses |
| Playback coordinator | Keep metadata separate from source, check cancellation/account state and call a player adapter once | Inactive mocked contract |
| Kodi player | Actual audiovisual playback, subtitles and seek/resume | Device validation pending |
| Umbrella adapter option | Possible alternate playback handoff | Pinned source routes/licence inspected; no supported external contract or device pass |

A title ID, air date, paused record or list entry is not evidence of a playable
source. An account download list is not a title catalogue. Do not match a filename
to a title and silently assume identity. Do not silently fall back between providers.

Retain the Umbrella experiment as a candidate first live path. The
[feasibility investigation](umbrella-feasibility.md) records the exact upstream source
revision, GPLv3 declaration and observed candidate routes. No source/assets were copied.
Verify the installed version/provenance and its supported interface before implementing
an adapter; then test a movie and episode, cancellation, subtitles, resume and return navigation.
If that handoff is unsuitable, the direct Real-Debrid path starts with an explicitly
supplied authorized host link. Source discovery and automatic title-to-source matching
need a separate reviewed design. Neither route has been selected as proven.

## Verified service contract and open questions

The [official API documentation](https://api.real-debrid.com/) describes a distinct
open-source device flow: obtain a code with `new_credentials=yes`, poll for user-bound
client credentials, then exchange for tokens. Refresh uses the device grant with the
refresh token as `code`. These runtime secrets are private account material, never
shared application secrets bundled in the add-on. Registration is still required.

The documentation does not identify the precise not-yet-authorized credentials-poll
response. The prototype fails closed unless tests inject an explicit pending-response
classifier. A real registration/device experiment must establish that behavior before
supplying any production classifier. The authorization module itself stores nothing. The separate 0.8 provider store is
exercised only by tests; the current Kodi adapter does not create it.

The API documents a 250-request/minute ceiling and 429 responses. Local bounds are
not a cross-invocation quota manager. The inactive transport enforces TLS, a fixed API host, byte/time limits, form
encoding, cancellation checks and redacted failures. Device verification is pending;
OS DNS resolution is outside Python socket deadlines.
Mutating resolution requests are not automatically retried after uncertain outcomes.

## Security, terms and costs

Follow the [service terms](https://real-debrid.com/terms): use only authorized content,
keep the account and generated links private, and respect service limits. No live
account tests run in cloud CI or this development environment. Tests fabricate data.

Some operations require Premium. An existing subscription is a service cost, separate
from HomeFX's source licence; no subscription, Remote Traffic or paid option is bought
or enabled here. Verify current pricing in the service's own account/checkout UI before
purchase. No third-party source/assets, new dependency or licence fee was added.

The 0.8 store keeps user-bound client secrets and access/refresh tokens in a separate
protected provider directory when explicitly constructed. Validate its permissions
and recovery on the TV before activation. Do not mix them into Trakt records, Kodi settings,
plugin URLs, logs, source control or backups shared for support. Resolved URLs may
contain bearer-like secrets; keep them in memory and redact representations/errors.
URL syntax checks do not establish DNS safety, redirect policy, content identity or
permission. Network and player adapters must enforce the remaining boundaries.

## Activation sequence and acceptance

1. Review registrations and public client IDs. Never send a client secret or token in
   chat or a PR. Verify device polling, expiry, denial and refresh using the TV.
2. Validate the implemented provider-specific storage, transport and session stack on
   the TV. Automated tests cover interrupted responses, disconnect/account replacement
   and competing refresh attempts; they do not prove Android behavior.
3. Choose the first live path after the Umbrella experiment and direct-resolution
   evidence. Confirm the source's rights and title identity explicitly.
4. Wire one Kodi player adapter behind an explicit live-mode gate. A callback accepting
   a URL is not evidence that media played. Verify actual audiovisual start, cancellation,
   failure, subtitles, resume and seek on Android/Google TV.
5. Assign exactly one component ownership of resume and Trakt scrobbling. Test start,
   pause, stop, completion, manual watched correction and the next aired episode policy.
   Existing next-episode preview remains synthetic and does not auto-start media.
6. Enable only the verified route. Live account support, real source availability and
   repository update hosting are separate from publishing a manual synthetic ZIP.

Kodi distinguishes a playback request from available audiovisual playback; see its
[official player callback documentation](https://xbmc.github.io/docs.kodi.tv/master/kodi-dev-kit/group__python___player_c_b.html).
That reference is current development documentation, not a device test of Kodi 21.2.


The inactive [playback event observer](playback-events.md) distinguishes a dispatched
request from AV start, pause/resume and terminal callbacks. It supplies observations
only: completion thresholds, scrobbling ownership and the real Kodi adapter remain
open. An ended event is not a successful watched-state update.
