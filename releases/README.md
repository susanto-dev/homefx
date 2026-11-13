# Reviewed release archives

`inventory.json` pins archive identity, version, relative path and SHA-256. Keep every
record and its original bytes once merged. Add current package records after final
runtime changes; the history guard compares fresh builds and the review base.

The initial retained video 0.8.0 archive was rebuilt from merged source commit
`ce924ffde917dc68fabababecdea048016d57214` before the 0.9 changes. Its SHA-256 is
`3b4503f0203eb15bddb488f66918a4b48e63dbc8f18bdf73ef8fff31e3d37617`.
It is a reviewed predecessor, not a claim of successful TV installation or playback.
The initial current archives are video 0.9.0 and repository 0.2.0, generated from
this change's final runtime source with the reviewed deterministic builder.

All packages contain the existing original-code MIT notice. No upstream add-on,
skin or artwork has been incorporated. No profile, credentials or live account data
belongs in this directory. See [release policy](../docs/releases.md) for bounds,
publication, device acceptance and recovery; retaining a ZIP does not trigger a downgrade.

Video 0.10.0 adds its reviewed current archive while retaining all three initial
records unchanged. Repository 0.2.0 is reused byte-for-byte; a new repository package
is unnecessary when only the indexed video add-on changes.


Video 0.11.0 was prepared through the verified local proposal helper. Its integration
preserves the four existing records and their ZIP bytes; only the new video archive
and prospective inventory are added. Repository 0.2.0 remains unchanged.

Video 0.12.0 was staged with the same verified proposal workflow, preserving all five
prior records and bytes. Its optional storage self-check uses synthetic temporary
files only; no profile or account configuration is packaged.

Video 0.13.0 uses the same verified proposal workflow and preserves all six prior
records and archive bytes. Repository 0.2.0 remains unchanged. Storage regression
fixtures are synthetic and are not included in the video package.

Video 0.14.0 extends credential and request-limit storage guards. Its release
proposal preserves all seven previous records and ZIP bytes; repository 0.2.0
remains unchanged. No account data or test fixtures are included.

Video 0.14.1 repairs concurrent preference sidecar inspection. It preserves all
eight prior records and archive bytes, including 0.14.0 whose post-merge publication
failed before deployment. Only 0.14.1 is the repaired current video update target.
