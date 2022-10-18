import time
from os import getenv

MIMIR = str(getenv("MIMIR"))
TENANT = str(getenv("TENANT", ""))
PORT = int(getenv("PORT", 9000))
REFRESH_FREQUENCY = int(getenv("REFRESH_FREQUENCY", 30))
LOG_LEVEL = str(getenv("LOG_LEVEL", "warning"))
