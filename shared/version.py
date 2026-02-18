"""Version information for Reach."""

from shared.compat import env

__version__ = "0.1.13"

# Default update URL pointing to R2 releases bucket (via custom domain)
# Override with REACH_UPDATE_URL (or legacy PHONEHOME_UPDATE_URL) env var or client config.yml
_DEFAULT_UPDATE_URL = "https://phone-home.techki.ai/releases/latest/version.json"

UPDATE_URL = env("REACH_UPDATE_URL", "PHONEHOME_UPDATE_URL", _DEFAULT_UPDATE_URL)
