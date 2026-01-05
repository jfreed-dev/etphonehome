"""Version information for ET Phone Home."""

import os

__version__ = "0.1.5"

# Update server URL - set PHONEHOME_UPDATE_URL environment variable
# or configure in client config.yml
UPDATE_URL = os.environ.get("PHONEHOME_UPDATE_URL", "")
