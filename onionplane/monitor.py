"""Tor-aware uptime prober."""
import time
from dataclasses import dataclass
from typing import Optional

import httpx
from httpx_socks import AsyncProxyTransport

from . import config


@dataclass
class ProbeResult:
    ok: bool
    latency_ms: float
    status_code: Optional[int]
    error: Optional[str]


async def probe(onion_address: str) -> ProbeResult:
    port = config.VIRTUAL_PORT
    host = onion_address if port == 80 else f"{onion_address}:{port}"
    url = f"http://{host}/"

    transport = AsyncProxyTransport.from_url(config.SOCKS_PROXY, rdns=True)
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            transport=transport, timeout=config.PROBE_TIMEOUT_SECONDS
        ) as client:
            resp = await client.get(url)
        latency_ms = (time.perf_counter() - start) * 1000
        return ProbeResult(True, latency_ms, resp.status_code, None)
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000
        return ProbeResult(False, latency_ms, None, f"{type(exc).__name__}: {exc}")
