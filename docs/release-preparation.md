# Preparing an immutable release proposal

`tools/prepare_release.py` prepares a complete prospective inventory and its ZIPs
in a new local staging directory. It does not edit tracked releases, publish files,
update GitHub settings or create a commit. No dependency or paid service is added.

After final runtime changes, update the add-on version and run:

```sh
python tools/prepare_release.py /tmp/homefx-release-proposal --base-ref REVIEW_BASE_SHA
```

The output must not exist, its parent must exist, and neither may use symlinks.
Use an external directory or a new subdirectory of `dist`; tracked source locations
are rejected. Use the actual reviewed base commit, not an invented ref or a shell
expression such as `HEAD^`. Source files and destination parents must stay unchanged
while preparing the proposal.

The helper first checks that the current inventory preserves every record at the
Git base. It builds the current video/repository packages with the existing bounded
validators and verifies every retained archive. A previously recorded version whose
bytes differ from the current build is rejected; bump the version instead of replacing
it. A missing new version is added under `archives/`. Existing identity, version,
relative path, hash and ZIP bytes are preserved exactly. No old version is pruned.

The full proposed inventory is then checked against the source inventory and fresh
package builds before the temporary stage is renamed into place. Failures remove
temporary staging and leave inputs and the requested output untouched. Inventory,
package-count and aggregate-byte limits are the same as the release validators.
This is local integrity evidence, not source approval, signatures or device testing.

Review the proposal and its difference from `releases/inventory.json`. Integrate only
new archive files and the reviewed inventory update. Do not replace the whole
`releases` directory: documentation and existing sidecars are not proposal contents.
Run the release-history check against the reviewed Git base after integration, then
run normal tests, packaging and repeatability checks. Protected main still receives
changes through a reviewed PR; the existing merge-triggered Pages workflow publishes
only after its gates pass.

The proposal always contains all inventoried ZIPs, even when a current package is
unchanged. An unchanged repository bootstrap can therefore be reused byte-for-byte
when only the video add-on changes. Re-running against the same source into another
fresh destination produces the same proposal bytes. Nothing in this process verifies
Kodi installation, update, rollback, live accounts or playback on the TV.
