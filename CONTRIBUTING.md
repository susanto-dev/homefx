# Contributing

Keep changes scoped to an agreed outcome. Inspect current source and working-tree
changes first. Preserve unrelated work. Use ordinary project documentation and
neutral commit/PR language; do not add assistant-specific instructions or branding.

Before review, explain the behavior changed, relevant checks and their results,
untested paths, compatibility effects, and the exact reviewed commit when available.
Self-review is not independent approval. Seek independent review for authentication,
watch-history writes, playback state, and publishing. Revisit affected conclusions
when source changes. Check route consumers, saved widgets, manifests and packages.

Run the checks in [development](docs/development.md). Tests must prove behavior,
not duplicate implementation. Update the authoritative documentation alongside a
behavior change; record significant choices in [decisions](docs/decisions.md).

Build, merge, push and publish are distinct operations. Work within the authorized
scope; pushes to main publish the preview through the Pages workflow after checks pass. Product choices belong
to the maintainer; resolve ordinary engineering choices within the agreed scope.

Never commit account data, tokens, private lists/history, Kodi profiles, or logs.
Use fabricated fixtures. Verify exact licences and provenance before adding any
third-party code or assets, and preserve required notices. Public availability is
not permission. See [security](SECURITY.md).
