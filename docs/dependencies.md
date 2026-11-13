# Dependency inventory

HomeFX's Python runtime uses the Python standard library and modules supplied by Kodi. It has no third-party Python runtime packages. Kodi module and add-on requirements are declared in each add-on's `addon.xml`; they are part of the Kodi host contract, not PyPI packages, and are not represented by Python requirements files.

## Python requirements files

The root `requirements.txt` is intentionally empty apart from comments. It records the runtime inventory boundary and is the input to the runtime audit. Do not add development tools there. If a third-party Python runtime dependency is introduced, pin and hash it, update this inventory and its checks, and account for Kodi compatibility and package inclusion explicitly.

The development-only inventories are:

- `tools/build-requirements.txt`: `defusedxml`, used by packaging and XML checks.
- `tools/quality-requirements.txt`: `ruff`.
- `tools/security-requirements.txt`: Bandit, pip-audit, and their pinned transitive dependencies.

All entries are exactly version-pinned and include PyPI SHA-256 hashes. Install them with pip's hash-checking mode as shown in the file comments and workflows. These packages support repository checks and are not shipped as Kodi runtime dependencies. The offline `tools/check_dependencies.py` checks these four files for numeric version pins, SHA-256 hashes, normalized package names, and consistent hashes when the same name and version appear more than once. The empty runtime inventory is allowed; each tooling inventory must contain at least one declaration. CI runs this guard before installing dependencies. An optional deterministic JSON report contains normalized package, version, and hash membership. The guard does not install or resolve packages and does not establish package provenance.

Run the offline check before installing tools:

```sh
python3 tools/check_dependencies.py
# Optional report: choose a fresh output path; existing files are not replaced.
python3 tools/check_dependencies.py --output dist/dependencies/inventory.json
```

This is a deliberately restricted declaration format: numeric release versions,
SHA-256 hashes, whole-line comments and explicit backslash continuations. Includes,
URL/VCS/local requirements, environment markers, extras and prerelease-version
syntax are rejected rather than partially interpreted. Equivalent version spellings
are not inferred; shared package versions and hash sets must match exactly. Duplicate
normalized package names within one inventory are rejected. This is not a general
pip requirements parser or proof of transitive completeness.

## GitHub dependency graph

GitHub's dependency graph reads supported dependency manifests and lockfiles, including `requirements.txt`, and GitHub Actions workflow files under `.github/workflows/`. A file named `dependencygraph.yaml` is not a prerequisite. `dependabot.yml` configures Dependabot version-update jobs; it is not the dependency graph's inventory file.

On 2026-11-13, the repository's read-only GitHub SBOM export confirmed the Python tooling inventory, including transitive packages, and five GitHub Actions referenced by workflow SHA. All 32 normalized Python package names and versions from the four local inventories matched that snapshot. It is a useful view of dependencies GitHub recognizes from the repository, not a complete bill of materials for everything used to build or run HomeFX.

## Alerts and updates are separate

The dependency graph supplies inventory data. Dependabot alerts use that graph to report known vulnerable dependencies when alerts are enabled. Dependabot security updates can open pull requests to fix vulnerable dependencies. Dependabot version updates can open pull requests on a schedule configured in `dependabot.yml`. These features have separate controls and purposes; a version-update configuration is not required just to describe dependencies in the graph. This document does not request a settings change or enable automatic pull requests.

GitHub's supported-ecosystem reference notes that GitHub Actions alerts are generated for actions using semantic versions, not SHA versions. HomeFX pins Actions to commit SHAs for workflow integrity, so the graph's presence of those Actions should not be read as proof that Dependabot alerts cover them.

## Coverage limits

The graph and exported SBOM do not establish a complete inventory of the operating system, Python interpreter, Kodi version or bundled modules, Kodi add-on dependencies, files installed by external Actions, or every dependency inside third-party Actions. Workflow manifests identify the referenced Actions, but do not describe all of their runtime contents. The Python requirements files describe declared Python tooling, while platform packages and dependencies supplied by Kodi are outside that inventory. Continue to review package artifacts and the target Kodi environment separately.

## GitHub references

- [About the dependency graph](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependency-graph)
- [Dependency graph supported package ecosystems](https://docs.github.com/en/code-security/reference/supply-chain-security/dependency-graph-supported-package-ecosystems) — lists `requirements.txt` for pip and describes supported manifest and lockfile inputs.
- [Dependabot alerts](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependabot-alerts)
- [Dependabot security updates](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependabot-security-updates)
- [Dependabot version updates](https://docs.github.com/en/code-security/concepts/supply-chain-security/dependabot-version-updates)
