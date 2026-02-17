"""Version information for ET Phone Home."""

import os

__version__ = "0.1.13"

# Default update URL pointing to R2 releases bucket (via custom domain)
# Override with PHONEHOME_UPDATE_URL environment variable or client config.yml
_DEFAULT_UPDATE_URL = "https://phone-home.techki.ai/releases/latest/version.json"

UPDATE_URL = os.environ.get("PHONEHOME_UPDATE_URL", _DEFAULT_UPDATE_URL)
