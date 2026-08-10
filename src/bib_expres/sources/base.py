from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_CACHE_PATH = Path.home() / ".cache" / "bib_expres" / "http_cache.sqlite3"
DEFAULT_TIMEOUT = 15
DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60  # 1 semana


class ResponseCache:
    """Cache local de respuestas HTTP en sqlite -- vive fuera del repo, en la
    carpeta de cache del usuario. Evita repetir peticiones a las mismas fuentes
    al re-ejecutar sobre el mismo paper padre."""

    def __init__(self, path: Path = DEFAULT_CACHE_PATH, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, stored_at REAL)"
        )
        self._conn.commit()

    @staticmethod
    def _key(url: str, params: dict[str, Any] | None) -> str:
        raw = url + json.dumps(params or {}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, url: str, params: dict[str, Any] | None = None) -> dict | None:
        key = self._key(url, params)
        row = self._conn.execute(
            "SELECT value, stored_at FROM cache WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        value, stored_at = row
        if time.time() - stored_at > self._ttl:
            return None
        return json.loads(value)

    def set(self, url: str, params: dict[str, Any] | None, value: dict) -> None:
        key = self._key(url, params)
        self._conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, stored_at) VALUES (?, ?, ?)",
            (key, json.dumps(value), time.time()),
        )
        self._conn.commit()


class SourceClient:
    """Sesion HTTP compartida para todos los clientes de fuentes: reintentos con
    backoff, cache local, e identificacion de contacto (mailto o API key) inyectada
    una sola vez aqui en vez de repetida en cada cliente."""

    def __init__(
        self,
        base_url: str,
        contact_email: str | None = None,
        api_key: str | None = None,
        api_key_header: str | None = None,
        cache: ResponseCache | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.contact_email = contact_email
        self.timeout = timeout
        self.cache = cache if cache is not None else ResponseCache()

        self._session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            respect_retry_after_header=True,
        )
        self._session.mount("https://", HTTPAdapter(max_retries=retry))
        self._session.mount("http://", HTTPAdapter(max_retries=retry))
        if api_key and api_key_header:
            self._session.headers[api_key_header] = api_key

    def get(self, path: str, params: dict[str, Any] | None = None, use_cache: bool = True) -> dict:
        params = dict(params or {})
        if self.contact_email:
            params.setdefault("mailto", self.contact_email)

        url = f"{self.base_url}/{path.lstrip('/')}"

        if use_cache:
            cached = self.cache.get(url, params)
            if cached is not None:
                return cached

        response = self._session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        if use_cache:
            self.cache.set(url, params, data)

        return data
