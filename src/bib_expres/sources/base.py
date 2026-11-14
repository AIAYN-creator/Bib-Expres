from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_CACHE_PATH = Path.home() / ".cache" / "bib_expres" / "http_cache.sqlite3"
DEFAULT_TIMEOUT = 15
DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60  # 1 semana
# Si una API pide esperar (HTTP 429 + Retry-After) poco, se espera y se reintenta;
# si pide esperar mas de esto (p.ej. cuota diaria agotada: OpenAlex llega a pedir
# ~10 h), se avisa al usuario en vez de dejar la app colgada en silencio.
MAX_RETRY_AFTER_SECONDS = 30
RATE_LIMIT_RETRIES = 2
DEFAULT_RATE_LIMIT_WAIT = 5
MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MB -- las respuestas de estas APIs son metadata, nunca deberian acercarse a esto


class ResponseCache:
    """Cache local de respuestas HTTP en sqlite -- vive fuera del repo, en la
    carpeta de cache del usuario. Evita repetir peticiones a las mismas fuentes
    al re-ejecutar sobre el mismo paper padre."""

    def __init__(self, path: Path = DEFAULT_CACHE_PATH, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()

    @property
    def _conn(self) -> sqlite3.Connection:
        """Conexion sqlite3 por hilo -- una misma ResponseCache se comparte entre
        llamadas de la GUI que pywebview despacha cada una en su propio hilo
        (ver webview/util.py), y sqlite3 no permite reutilizar una conexion
        creada en otro hilo. Se crea perezosamente la primera vez que este hilo
        la toca, y se reutiliza en llamadas siguientes del mismo hilo."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._path)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, stored_at REAL)"
            )
            conn.commit()
            self._local.conn = conn
        return conn

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
        if time.time() - stored_at >= self._ttl:
            return None
        return json.loads(value)

    def set(self, url: str, params: dict[str, Any] | None, value: dict) -> None:
        key = self._key(url, params)
        self._conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, stored_at) VALUES (?, ?, ?)",
            (key, json.dumps(value), time.time()),
        )
        self._conn.commit()


class RateLimitedError(Exception):
    """La fuente ha limitado las peticiones y pide esperar demasiado como para
    hacerlo en silencio. No hereda de requests.RequestException a proposito: los
    fallos de red de un paper se ignoran para seguir con el resto, pero este no
    debe ignorarse -- afecta a toda la busqueda y el usuario tiene que saberlo."""

    def __init__(self, source: str, retry_after: float | None) -> None:
        self.source = source
        self.retry_after = retry_after
        super().__init__(
            f"{source} ha limitado las peticiones (demasiadas en poco tiempo, o la cuota "
            f"diaria agotada) y pide esperar {_humanize_wait(retry_after)}. Vuelve a "
            "intentarlo más tarde: lo ya consultado queda en la caché local, así que "
            "repetir la misma búsqueda gastará menos peticiones."
        )


def _humanize_wait(seconds: float | None) -> str:
    if seconds is None:
        return "un rato"
    if seconds >= 3600:
        hours = round(seconds / 3600)
        return f"unas {hours} hora{'s' if hours != 1 else ''}"
    if seconds >= 60:
        minutes = round(seconds / 60)
        return f"unos {minutes} minuto{'s' if minutes != 1 else ''}"
    return f"{round(seconds)} segundos"


def _parse_retry_after(value: str | None) -> float | None:
    """Retry-After admite segundos o una fecha HTTP."""
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max((when - datetime.now(timezone.utc)).total_seconds(), 0.0)


def _read_limited(response: requests.Response, url: str) -> bytes:
    """Lee el cuerpo por trozos y corta en cuanto pasa de MAX_RESPONSE_BYTES.
    Leer `response.content` de golpe descargaria la respuesta entera a memoria
    antes de poder comprobar su tamano -- con respuestas sin Content-Length
    (chunked) el limite llegaria tarde."""
    content_length = response.headers.get("Content-Length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_RESPONSE_BYTES:
        raise requests.RequestException(
            f"Respuesta de {url} demasiado grande segun Content-Length "
            f"({content_length} bytes) -- rechazada como precaucion"
        )
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        total += len(chunk)
        if total > MAX_RESPONSE_BYTES:
            raise requests.RequestException(
                f"Respuesta de {url} demasiado grande (>{MAX_RESPONSE_BYTES} bytes) -- rechazada como precaucion"
            )
        chunks.append(chunk)
    return b"".join(chunks)


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
        # 429 (limite de peticiones) se gestiona a mano en get(): urllib3 obedece
        # Retry-After sin tope y llegaba a dormir horas. Aqui solo errores de
        # servidor, con backoff propio e ignorando Retry-After por el mismo motivo.
        retry = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=[500, 502, 503, 504],
            respect_retry_after_header=False,
        )
        self._session.mount("https://", HTTPAdapter(max_retries=retry))
        self._session.mount("http://", HTTPAdapter(max_retries=retry))
        if api_key and api_key_header:
            self._session.headers[api_key_header] = api_key

    def _get_respecting_rate_limit(self, url: str, params: dict[str, Any]) -> requests.Response:
        for attempt in range(RATE_LIMIT_RETRIES + 1):
            response = self._session.get(url, params=params, timeout=self.timeout, stream=True)
            if response.status_code != 429:
                return response
            wait = _parse_retry_after(response.headers.get("Retry-After"))
            response.close()
            if wait is not None and wait > MAX_RETRY_AFTER_SECONDS:
                raise RateLimitedError(urlsplit(url).netloc, wait)
            if attempt < RATE_LIMIT_RETRIES:
                time.sleep(wait if wait is not None else DEFAULT_RATE_LIMIT_WAIT)
        # Sigue limitando tras esperas cortas: se trata como un fallo de red mas
        # (ese paper se queda sin candidatos), no como un bloqueo largo.
        raise requests.RequestException(f"{urlsplit(url).netloc} sigue limitando las peticiones (429)")

    def get(self, path: str, params: dict[str, Any] | None = None, use_cache: bool = True) -> dict:
        params = dict(params or {})
        if self.contact_email:
            params.setdefault("mailto", self.contact_email)

        url = f"{self.base_url}/{path.lstrip('/')}"

        if use_cache:
            cached = self.cache.get(url, params)
            if cached is not None:
                return cached

        response = self._get_respecting_rate_limit(url, params)
        try:
            response.raise_for_status()
            body = _read_limited(response, url)
        finally:
            response.close()

        try:
            data = json.loads(body)
        except ValueError as exc:
            raise requests.RequestException(f"Respuesta de {url} no es JSON valido") from exc

        if use_cache:
            self.cache.set(url, params, data)

        return data
