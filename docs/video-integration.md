# Joining the read-only video journey

The published 0.17.7 release adds a single injectable `TraktVideo` dispatcher in the video
add-on's shared runtime. The public `default.py` does not call it and no public
configuration is added to the video ZIP. This is implementation preparation, not
an activated live preview or another installed add-on.

## Reuse and ownership

Authentication, session, token storage, transport, account interaction, list selection
and directory rendering already live under `plugin.video.homefx/resources/lib`.
The separate program builder packages these same source files. The dispatcher joins
them for the video caller rather than introducing a second login implementation.

The caller supplies a trusted lazy `build_trakt` factory bound to the video add-on's
own private profile and reviewed public client configuration. It must never discover
or copy another add-on's credentials. Configuration and profile selection are caller
responsibilities, not arbitrary query parameters. Import/construction opens no store
and makes no request. No client-secret argument or account configuration URL is added.

## Invocation contract

`dispatch` supports explicit `connect`, `disconnect`, `choose` and `browse` actions.
Management actions request consent before constructing the runtime; declined consent
and cancellation before runtime construction leave storage unopened. Cancellation
after login begins can change local credential state, including removing a prior
session during a replacement login. AccountFlow owns code display and cleanup.
Disconnect uses the complete bundle's callback, clearing local saved list choices as
well as credentials without claiming remote revocation or backup erasure.

Browse accepts the existing strict opaque widget queries. Reads never initiate login
or silently fall back to demo data. The same active UI cancellation callback reaches
the runtime and the interaction. Widget invocations open no consent/progress/error
dialogs; directory completion is unsuccessful for failed or cancelled loads. Human
browsing uses the existing loading dialog and metadata-only details. There is no
playable flag, source resolution, remote mutation or Real-Debrid path.

List choices are saved locally; creating the skin's row is a separate action. Existing
source/list folders remain available when a heading is not clickable. Continue
Watching, Next aired and Upcoming retain their separate meanings; a future air date
never guarantees a source, and the personal calendar is not a schedule of every
show in arbitrary selected lists.

## Delivery and activation status

1. The next candidate packages the public Development identity/redirect into a
   separately identified Development video ZIP, using the existing GitHub variables. Do not change
   an existing archive's bytes, silently import script configuration or use Production
   merely because owner Development login worked. No credentials belong in builds.
2. The candidate wires the reviewed entry point explicitly while preserving existing
   Preview/demo/widget URLs and using its own storage/login. Keep remote writes and playback disabled.
3. On an intentional device candidate, accept one real personal or liked list,
   separate skin-row setup, title/season details and restart retention. Check empty,
   offline and authorization-needed states and account isolation. Measure cold/warm
   loading and multiple rows before making performance claims.

The owner has already passed the separate program's authorization, refresh, restart,
disconnect, cancellation and responsive offline-error checks. They need not repeat
those as a prerequisite for unrelated implementation. Synthetic denial/expiry and
process-interruption regressions are separate evidence, not invented live results.
See [account requirements](account-setup.md#evidence-required-without-destructive-account-tests)
and [testing evidence](testing.md#refresh-process-interruption).

## Development delivery candidate

The next candidate uses a distinct video ID with its own profile and widget URLs,
reusing this dispatcher. It is built from reviewed source with public Development
configuration and delivered as a checksum-named ZIP on the existing Pages source.
It leaves the public Preview entry point inactive and requires deliberate installation,
fresh on-device login and list-read consent. See [delivery and TV checklist](development-video.md).
