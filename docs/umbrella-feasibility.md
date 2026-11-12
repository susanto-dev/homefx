# Umbrella playback handoff evidence

## 1. Decision and scope

Umbrella remains a candidate playback integration. Source inspection establishes
that playback routes exist; it does **not** establish a stable external API, a working
HomeFX handoff, or compatibility with the installed TV configuration. HomeFX does not
implement or invoke these routes. Keep live playback disabled until the experiment
below passes and the playback owner is selected. See [playback-plan.md](playback-plan.md)
for the separate direct Real-Debrid option.

## 2. Source snapshot and licence

Inspected on 2026-11-12: the [official source repository](https://github.com/umbrellaplug/umbrellaplug.github.io)
at commit `e4f24004462d22757d375ebbea0bad26e9d983cc`, specifically
`omega/plugin.video.umbrella`. Its
[manifest](https://github.com/umbrellaplug/umbrellaplug.github.io/blob/e4f24004462d22757d375ebbea0bad26e9d983cc/omega/plugin.video.umbrella/addon.xml)
identifies `plugin.video.umbrella` version **6.8.00**, declares the Python API dependency
`xbmc.python` 3.0.0, and identifies the project website. This snapshot is not evidence
of which package, version, dependencies or provenance the TV has installed. The API
dependency alone does not prove Kodi 21.2 compatibility.

The manifest declares GNU GPL version 3 and the add-on's
[LICENSE.txt](https://github.com/umbrellaplug/umbrellaplug.github.io/blob/e4f24004462d22757d375ebbea0bad26e9d983cc/omega/plugin.video.umbrella/LICENSE.txt)
contains GPLv3. GitHub's repository-level licence metadata was null; that does not
negate the add-on's licence file. This inspection does not audit every file, bundled
asset or dependency, nor establish additional permissions or an “or later” grant.
No upstream code, assets or licence text is imported here. GPL-covered source cannot
simply be copied into HomeFX and redistributed as MIT-only code. Any future reuse or
bundling needs an exact-file provenance, dependency and licence-obligation review.
An experiment with a separately installed add-on does not require copying its source;
it also does not settle every possible integration licensing question.

## 3. Observed routing contract

These are implementation observations at the pinned commit, not a documented promise
of an external integration interface:

| Observation | Implication for a possible experiment |
|---|---|
| The [entry point](https://github.com/umbrellaplug/umbrellaplug.github.io/blob/e4f24004462d22757d375ebbea0bad26e9d983cc/omega/plugin.video.umbrella/umbrella.py) passes Kodi's query argument into the router. | A route can be inspected independently of UI navigation, but invocation semantics still need device validation. |
| The [router](https://github.com/umbrellaplug/umbrellaplug.github.io/blob/e4f24004462d22757d375ebbea0bad26e9d983cc/omega/plugin.video.umbrella/resources/lib/modules/router.py#L1668) dispatches `play_Item` and `play_info` to source selection/playback logic. Its `play` branch is explicitly labelled support for older library stream files. | Prefer establishing the installed version's intended interface before choosing an action. Do not assume the legacy branch is the preferred public API. |
| The router reads `title`, `year`, `imdb`, `tmdb`, `tvdb`, `tvshowtitle`, `season` and `episode`; it also forwards `premiered`, `meta`, selection and rescrape options. | IDs are accepted as parameters. Their presence alone does not prove sufficient metadata, correct identity, availability or success. A Trakt ID is not a substitute for these ID namespaces. |
| [Source logic](https://github.com/umbrellaplug/umbrellaplug.github.io/blob/e4f24004462d22757d375ebbea0bad26e9d983cc/omega/plugin.video.umbrella/resources/lib/modules/sources.py#L84) distinguishes a movie from an episode by whether `tvshowtitle` is absent, uses season/episode numbers for episodes, and checks provider configuration. | Movie and episode requests need separate fixtures. Verify show-level IDs and episode numbering against installed behavior; never infer them from a filename. |

No supported minimal external parameter set was established. The inspected code also
has metadata fallback and playlist state handling, so an ID-only call is not proven
safe or complete. This document deliberately supplies no runnable guessed plugin URL.
Trakt supplies metadata and watch state; Real-Debrid resolves supported supplied
sources. Neither is a complete playable title catalogue.

## 4. Bounded TV experiment

Use content the user is authorized to access and record results locally:

1. Record Kodi/Android and installed Umbrella versions, package provenance and relevant
   settings. Compare the installed route implementation with this snapshot. Confirm
   the available interface and encoding rules before writing a temporary adapter.
2. Select one movie and one aired episode with independently checked title/year and
   IMDb/TMDb/TVDb identity, plus show title, season and episode for the latter. Establish
   playback from Umbrella itself as the baseline; that baseline is not a HomeFX pass.
3. Invoke the agreed interface once from a controlled HomeFX experiment. Record
   request, source-selection display, actual audiovisual start, stop/end/error and
   return navigation. Check correct content and episode, source cancellation, no sources,
   unavailable add-on, missing IDs and repeated clicks. No silent provider fallback.
4. Verify subtitles, audio selection, seek, resume prompts, stop/restart and return to
   the originating widget/folder on the TV. A successful route dispatch is insufficient.
5. With exactly one owner configured as below, test pause, stop, completion, watched
   correction and next-episode choice, including an already-watched next aired episode.
   Confirm no unaired episode starts and no duplicate playback or scrobbling occurs.
6. Save sanitized pass/fail evidence with versions and unresolved issues. Keep tokens,
   playback URLs, private lists and viewing history out of commits, issue reports and
   shared logs. A full Kodi backup is unnecessary; begin with redacted version/settings
   details and only request narrowly relevant diagnostics if a specific failure needs them.

## 5. Playback ownership and security

Before testing watch synchronization, assign one owner each for resume decisions,
next-episode orchestration and Trakt scrobbling. For the first handoff experiment,
prefer Umbrella owning playback behavior while HomeFX observes the outcome; explicitly
check its configuration rather than assuming its defaults. Disable competing writers
or autoplay controllers. HomeFX's manual watched correction must refresh authoritative
state without racing the playback owner's updates. If these responsibilities cannot
be isolated and verified, keep the handoff unselected.

Never pass account credentials or resolved media links in plugin query parameters.
Keep service authorization within its owning component; do not extract Umbrella's
private account configuration. Validate metadata types and IDs, bound request sizes,
and encode data rather than interpolate it into Kodi commands. No account or media
traffic was performed during this inspection. No paid service or new dependency was
added; service subscriptions remain separate from source-licence obligations.

## 6. Acceptance status

Verified: pinned public source, add-on manifest/version, included GPLv3 declaration
and text, entry point, candidate route branches and accepted parameter names.

Open: installed package provenance/version, supported external contract, minimum
metadata and numbering semantics, Android/Kodi compatibility, source availability,
actual playback, subtitles, resume, cancellation, navigation, watch synchronization
and next-episode ownership. These require the TV experiment. No device or live
integration result is claimed, and no playback path is enabled by this document.
