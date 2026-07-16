"""OnionPlane -- a tiny self-hosted control plane for Tor onion services."""
import asyncio
import contextlib
import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import config, db, monitor
from .tor_manager import TorManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("onionplane")

tor = TorManager()


class ServiceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    local_port: int = Field(..., ge=1, le=65535)


async def _probe_all_once() -> None:
    for svc in db.list_services():
        result = await monitor.probe(svc["onion_address"])
        await asyncio.to_thread(
            db.record_probe, svc["id"], result.ok, result.latency_ms,
            result.status_code, result.error,
        )
        state = "UP" if result.ok else "DOWN"
        log.info("probe %s (%s) -> %s %.0fms", svc["name"], svc["onion_address"],
                 state, result.latency_ms)


async def _prober_loop() -> None:
    while True:
        try:
            await _probe_all_once()
        except Exception:
            log.exception("prober iteration failed")
        await asyncio.sleep(config.PROBE_INTERVAL_SECONDS)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(db.init_db)
    await asyncio.to_thread(tor.connect)
    log.info("connected to tor control port %s", config.CONTROL_PORT)

    for svc in await asyncio.to_thread(db.list_services_full):
        try:
            await asyncio.to_thread(tor.register_service, svc["private_key"], svc["local_port"])
            log.info("re-registered %s", svc["onion_address"])
        except Exception:
            log.exception("failed to re-register %s", svc["onion_address"])

    task = asyncio.create_task(_prober_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await asyncio.to_thread(tor.close)


app = FastAPI(title="OnionPlane", version="0.1.0", lifespan=lifespan)


@app.post("/services", status_code=201)
async def create_service(body: ServiceCreate):
    onion_address, private_key = await asyncio.to_thread(tor.create_service, body.local_port)
    svc = await asyncio.to_thread(
        db.add_service, body.name, body.local_port, onion_address, private_key
    )
    return svc


@app.get("/services")
async def list_services():
    services = await asyncio.to_thread(db.list_services)
    for svc in services:
        svc["health"] = await asyncio.to_thread(db.uptime_summary, svc["id"])
    return services


@app.get("/services/{service_id}")
async def get_service(service_id: int):
    svc = await asyncio.to_thread(db.get_service, service_id)
    if svc is None:
        raise HTTPException(404, "service not found")
    svc["health"] = await asyncio.to_thread(db.uptime_summary, service_id)
    svc["recent_probes"] = await asyncio.to_thread(db.get_probes, service_id, 50)
    return svc


@app.post("/services/{service_id}/probe")
async def probe_now(service_id: int):
    svc = await asyncio.to_thread(db.get_service, service_id)
    if svc is None:
        raise HTTPException(404, "service not found")
    result = await monitor.probe(svc["onion_address"])
    await asyncio.to_thread(
        db.record_probe, service_id, result.ok, result.latency_ms,
        result.status_code, result.error,
    )
    return result.__dict__


@app.delete("/services/{service_id}")
async def delete_service(service_id: int):
    svc = await asyncio.to_thread(db.get_service, service_id)
    if svc is None:
        raise HTTPException(404, "service not found")
    with contextlib.suppress(Exception):
        await asyncio.to_thread(tor.remove_service, svc["onion_address"])
    await asyncio.to_thread(db.delete_service, service_id)
    return {"deleted": service_id}


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
