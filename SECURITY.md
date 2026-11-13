# Security

Do not put credentials, tokens, private history, or full Kodi backups into public
issues. For a suspected vulnerability, use GitHub private vulnerability reporting
if it is available. If unavailable, ask the maintainer for a private contact route
without disclosing exploit details or account data publicly.

No private reporting channel has been configured or verified by this project yet.
Version 0.12.0 remains a synthetic-data preview. Authentication and data-client
foundations are exercised only with injected test responses; the HTTPS transport is not
connected to Kodi routes and no account-login action is enabled. See [security design](docs/security.md).

The experimental repository package 0.2.0 prepares installation and updates through
Pages after merge. Publication is separate from successful TV installation or service
activation. Release history, package hashes and independent repository checks guard
artifact consistency; hashes alone do not establish publisher trust. Development
requirements use reviewed version/hash locks and external workflow Actions retain
immutable commit pins. See [tooling coverage](docs/tooling-licenses.md) for the Ruff
gate and the official Kodi checker's remaining limitations.
