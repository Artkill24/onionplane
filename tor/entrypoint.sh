#!/bin/sh
set -e

: "${TOR_CONTROL_PASSWORD:?TOR_CONTROL_PASSWORD must be set}"

# Own a fresh data dir as the current user (root), avoiding the debian-tor
# ownership check that makes recent tor refuse /var/lib/tor.
DATA_DIR=/tmp/tor-data
mkdir -p "$DATA_DIR"
chmod 700 "$DATA_DIR"

HASH=$(tor --hash-password "$TOR_CONTROL_PASSWORD" | grep '^16:')

cat > /etc/torrc <<EOF
SocksPort 0.0.0.0:9050
ControlPort 0.0.0.0:9051
CookieAuthentication 0
HashedControlPassword $HASH
DataDirectory $DATA_DIR
EOF

exec tor -f /etc/torrc
