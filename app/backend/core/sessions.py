"""Gestor de sesiones en memoria (uuid → ReportData).

En producción se recomienda reemplazar por Redis u otro store.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta

from services.loader import ReportData


class SessionStore:
    def __init__(self, ttl_minutes: int = 120):
        self._store: dict[str, tuple[ReportData, datetime]] = {}
        self._ttl = timedelta(minutes=ttl_minutes)
        self._lock = threading.Lock()

    def _purge(self) -> None:
        now = datetime.utcnow()
        expired = [k for k, (_, ts) in self._store.items() if now - ts > self._ttl]
        for k in expired:
            self._store.pop(k, None)

    def put(self, data: ReportData) -> str:
        sid = uuid.uuid4().hex
        with self._lock:
            self._purge()
            self._store[sid] = (data, datetime.utcnow())
        return sid

    def get(self, sid: str) -> ReportData | None:
        with self._lock:
            self._purge()
            entry = self._store.get(sid)
            return entry[0] if entry else None


sessions = SessionStore()
