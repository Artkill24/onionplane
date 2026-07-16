"""Runtime configuration, all overridable via environment variables."""
import os

# Tor control host/port. Host is 127.0.0.1 for a local tor daemon; in Docker
# it's the tor service name (e.g. "tor"), reached over the compose network.
CONTROL_HOST = os.getenv("TOR_CONTROL_HOST", "127.0.0.1")
CONTROL_PORT = int(os.getenv("TOR_CONTROL_PORT", "9051"))
# If you use HashedControlPassword instead of CookieAuthentication, set this.
CONTROL_PASSWORD = os.getenv("TOR_CONTROL_PASSWORD")  # None -> cookie auth

# Tor SOCKS proxy used by the uptime prober to reach .onion addresses.
SOCKS_PROXY = os.getenv("TOR_SOCKS_PROXY", "socks5://127.0.0.1:9050")

# Virtual port the onion service exposes to clients (what the prober hits).
VIRTUAL_PORT = int(os.getenv("ONION_VIRTUAL_PORT", "80"))

# Host that the onion service forwards traffic to. 127.0.0.1 when the backend
# runs on the same box as tor; in Docker it's the backend service name (the
# tor process must be able to reach it). PoC limitation: one target host for
# all services -- per-service targets are a roadmap item (needs a DB column).
DEFAULT_TARGET_HOST = os.getenv("DEFAULT_TARGET_HOST", "127.0.0.1")

# SQLite state file. Holds services, their private keys, and probe history.
DB_PATH = os.getenv("ONIONPLANE_DB", "onionplane.db")

# Background prober cadence and per-probe timeout (Tor is slow, be generous).
PROBE_INTERVAL_SECONDS = int(os.getenv("PROBE_INTERVAL_SECONDS", "120"))
PROBE_TIMEOUT_SECONDS = float(os.getenv("PROBE_TIMEOUT_SECONDS", "60"))
