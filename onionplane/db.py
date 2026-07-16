"""Minimal SQLite persistence.

Two tables:
  services  -- one row per onion service, including its ED25519 private key
             so the .onion address survives restarts (key = the address).
  probes    -- append-only uptime/latency samples produced by the prober.

All functions here are synchronous; the FastAPI layer calls them via
asyncio.to_thread so they never block the event loop.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS services (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    local_port    INTEGER NOT NULL,
    onion_address TEXT    NOT NULL UNIQUE,
    private_key   TEXT    NOT NULL,
    created_at    TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS probes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id  INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    ts          TEXT    NOT NULL,
    ok          INTEGER NOT NULL,
    latency_ms  REAL,
    status_code INTEGER,
    error       TEXT
);
CREATE INDEX IF NOT EXISTS idx_probes_service ON probes(service_id, ts);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as conn:
        conn.executescript(_SCHEMA)


def add_service(name: str, local_port: int, onion_address: str, private_key: str) -> dict:
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO services (name, local_port, onion_address, private_key, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, local_port, onion_address, private_key, _now()),
        )
        row = conn.execute(
            "SELECT * FROM services WHERE id = ?", (cur.lastrowid,)
        ).fetchone()
    return _service_public(dict(row))


def list_services() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM services ORDER BY id").fetchall()
    return [_service_public(dict(r)) for r in rows]


def list_services_full() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM services ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def get_service(service_id: int) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
    return _service_public(dict(row)) if row else None


def delete_service(service_id: int) -> Optional[dict]:
    svc = get_service(service_id)
    if svc is None:
        return None
    with _conn() as conn:
        conn.execute("DELETE FROM services WHERE id = ?", (service_id,))
    return svc


def record_probe(service_id: int, ok: bool, latency_ms: Optional[float],
                 status_code: Optional[int], error: Optional[str]) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO probes (service_id, ts, ok, latency_ms, status_code, error) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (service_id, _now(), 1 if ok else 0, latency_ms, status_code, error),
        )


def get_probes(service_id: int, limit: int = 100) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT ts, ok, latency_ms, status_code, error FROM probes "
            "WHERE service_id = ? ORDER BY id DESC LIMIT ?",
            (service_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def uptime_summary(service_id: int, window: int = 100) -> dict:
    probes = get_probes(service_id, limit=window)
    if not probes:
        return {"samples": 0, "uptime_pct": None, "median_latency_ms": None, "last_ok": None}
    ok = [p for p in probes if p["ok"]]
    latencies = sorted(p["latency_ms"] for p in ok if p["latency_ms"] is not None)
    median = latencies[len(latencies) // 2] if latencies else None
    return {
        "samples": len(probes),
        "uptime_pct": round(100 * len(ok) / len(probes), 1),
        "median_latency_ms": round(median, 1) if median is not None else None,
        "last_ok": bool(probes[0]["ok"]),
    }


def _service_public(row: dict) -> dict:
    row.pop("private_key", None)
    return row
