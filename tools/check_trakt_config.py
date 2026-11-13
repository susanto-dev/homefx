"""Check public Trakt configuration syntax offline, without activation or output files."""
import os
from pathlib import Path
import sys


ADDON = Path(__file__).resolve().parents[1] / "addons" / "plugin.video.homefx"
if str(ADDON) not in sys.path:
    sys.path.insert(0, str(ADDON))
from resources.lib import service_runtime, trakt_auth


class ConfigurationError(ValueError):
    """Fixed categories only; configuration values must never enter diagnostics."""


def check(environment):
    """Validate selected environment and the same public syntax accepted by runtime.

    This does not construct a service, read profiles, contact Trakt, verify app
    registration or publish configuration. No client secret is accepted or needed.
    """
    if environment.get("HOMEFX_TRAKT_ENVIRONMENT") not in ("Development", "Production"):
        raise ConfigurationError("invalid_environment")
    client_id = environment.get("TRAKT_CLIENT_ID")
    if type(client_id) is not str or not trakt_auth._text(client_id, 256):
        raise ConfigurationError("invalid_public_client_id")
    if not service_runtime._redirect(environment.get("TRAKT_REDIRECT_URI")):
        raise ConfigurationError("invalid_redirect_uri")


def main(environment=None):
    try:
        check(os.environ if environment is None else environment)
    except ConfigurationError as error:
        print("Public Trakt configuration check failed: " + str(error) + ".")
        return 1
    print("Public Trakt configuration syntax passed. Registration, device acceptance "
          "and live activation are not verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
