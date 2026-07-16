FROM debian:stable-slim

# tor for the daemon; netcat for the healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tor netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# SOCKS + control. NOT published to the host in compose -- internal network only.
EXPOSE 9050 9051

ENTRYPOINT ["/entrypoint.sh"]
