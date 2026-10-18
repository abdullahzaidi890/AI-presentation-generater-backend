"""Common provider interface + HTTP error mapping. Never logs keys or prompts."""
import asyncio
import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

log = logging.getLogger("providers")
logging.getLogger("httpx").setLevel(logging.WARNING)

# Tests set this to an httpx.MockTransport so no real network is used.
_TRANSPORT: httpx.AsyncBaseTransport | None = None


@dataclass
class ProviderResult:
    text: str
    provider: str
    model: str


class ProviderError(Exception):
    """kind: bad_key | bad_model | rate_limit | server | timeout | network | malformed | not_configured"""

    def __init__(self, kind: str, message: str, status: int | None = None, retry_after: float | None = None):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.status = status
        self.retry_after = retry_after


class AIProvider(Protocol):
    name: str

    def is_configured(self) -> bool: ...

    async def generate(self, system: str, user: str, model: str, json_mode: bool) -> ProviderResult: ...


def map_http_error(resp: httpx.Response) -> ProviderError:
    s = resp.status_code
    ra = None
    try:
        ra = float(resp.headers.get("retry-after", ""))
    except ValueError:
        pass
    if s in (401, 403):
        return ProviderError("bad_key", "The API key was rejected (401/403). Check the key in .env.", s)
    if s == 404:
        return ProviderError("bad_model", "Model or endpoint not found (404). Check the model name.", s)
    if s == 429:
        return ProviderError("rate_limit", "Rate limit reached (429). Wait a bit and try again.", s, ra)
    if s >= 500:
        return ProviderError("server", f"The provider had a server error ({s}).", s)
    return ProviderError("server", f"Unexpected response from provider ({s}).", s)


async def post_json(url: str, headers: dict, body: dict, timeout: float, max_wait: float = 20.0) -> dict:
    """POST JSON. Honors Retry-After on a 429 (one retry, only if the wait is short)."""
    for attempt in (1, 2):
        try:
            async with httpx.AsyncClient(timeout=timeout, transport=_TRANSPORT) as client:
                resp = await client.post(url, headers=headers, json=body)
        except httpx.TimeoutException as e:
            raise ProviderError("timeout", f"The provider did not answer within {int(timeout)}s.") from e
        except httpx.HTTPError as e:
            raise ProviderError("network", "Network error while contacting the provider.") from e
        if resp.status_code == 429 and attempt == 1:
            err = map_http_error(resp)
            if err.retry_after is not None and err.retry_after <= max_wait:
                log.info("429 received, waiting %.1fs (Retry-After)", err.retry_after)
                await asyncio.sleep(err.retry_after)
                continue
            raise err
        if resp.status_code >= 400:
            raise map_http_error(resp)
        try:
            return resp.json()
        except ValueError as e:
            raise ProviderError("malformed", "Provider returned a non-JSON HTTP body.") from e
    raise ProviderError("rate_limit", "Rate limit reached (429).")
