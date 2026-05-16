from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

try:
    from curl_cffi import requests as curl_requests
except Exception:  # noqa: BLE001
    curl_requests = None


@dataclass
class RateLimiter:
    per_sec: float
    _last_ts: float = 0.0

    def wait(self) -> None:
        if self.per_sec <= 0:
            return
        interval = 1.0 / self.per_sec
        now = time.time()
        sleep_s = (self._last_ts + interval) - now
        if sleep_s > 0:
            time.sleep(sleep_s)
        self._last_ts = time.time()


def build_client(user_agent: str, extra_headers: dict[str, str] | None = None) -> httpx.Client:
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if extra_headers:
        headers.update(extra_headers)

    return httpx.Client(headers=headers, timeout=httpx.Timeout(20.0), follow_redirects=True, http2=True)


class CurlCffiClient:
    def __init__(self, headers: dict[str, str], proxy: str | None = None):
        if curl_requests is None:
            raise RuntimeError("curl_cffi is not installed")
        self._headers = headers
        self._proxy = proxy

    def get(self, url: str):
        # impersonate Chrome to improve compatibility with anti-bot/TLS fingerprinting
        proxies = None
        if self._proxy:
            proxies = {"http": self._proxy, "https": self._proxy}
        return curl_requests.get(url, headers=self._headers, timeout=20, impersonate="chrome", proxies=proxies)

    def close(self) -> None:
        return


def build_client_any(
    user_agent: str,
    extra_headers: dict[str, str] | None = None,
    use_curl_cffi: bool = False,
    proxy: str | None = None,
):
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if extra_headers:
        headers.update(extra_headers)

    if use_curl_cffi:
        return CurlCffiClient(headers=headers, proxy=proxy)

    # httpx backend
    proxies = None
    if proxy:
        proxies = {"http://": proxy, "https://": proxy}
    return httpx.Client(headers=headers, timeout=httpx.Timeout(20.0), follow_redirects=True, http2=True, proxies=proxies)


def fetch_text(client: httpx.Client, url: str, limiter: RateLimiter, retries: int = 3) -> str:
    last_exc: Exception | None = None
    for i in range(retries):
        try:
            limiter.wait()
            r = client.get(url)
            r.raise_for_status()
            return r.text
        except Exception as e:  # noqa: BLE001
            last_exc = e
            time.sleep(min(2 ** i, 8))
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"fetch failed: {url}")


def fetch_bytes(client: httpx.Client, url: str, limiter: RateLimiter, retries: int = 3) -> bytes:
    last_exc: Exception | None = None
    for i in range(retries):
        try:
            limiter.wait()
            r = client.get(url)
            r.raise_for_status()
            return r.content
        except Exception as e:  # noqa: BLE001
            last_exc = e
            time.sleep(min(2 ** i, 8))
    if last_exc is not None:
        raise last_exc
    raise RuntimeError(f"fetch failed: {url}")


def get_rate_limit(fetch_cfg: dict[str, Any]) -> float:
    try:
        return float(fetch_cfg.get("rate_limit_per_sec", 1.0))
    except Exception:  # noqa: BLE001
        return 1.0
