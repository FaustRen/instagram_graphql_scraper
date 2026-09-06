"""Asynchronous Instagram Embed fetching and normalization utilities."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
from typing import Any

import httpx

try:
    from .detail import parse_post_detail_html
except ImportError:
    from detail import parse_post_detail_html

try:
    from .instagram_context_json import extract_context_json, get_media, normalize_media
except ImportError:
    from instagram_context_json import extract_context_json, get_media, normalize_media


class InstagramEmbedClient:
    """Fetch and normalize Instagram Embed posts with bounded concurrency."""

    def __init__(
        self,
        max_concurrency: int = 10,
        timeout: float = 30,
        max_retries: int = 2,
        client: httpx.AsyncClient | None = None,
    ):
        """Configure a reusable async Embed client.

        Args:
            max_concurrency: Maximum number of requests running concurrently.
            timeout: Per-request timeout in seconds.
            max_retries: Number of retries for transient failures.
            client: Optional externally managed ``httpx.AsyncClient``.
        """
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be at least 1")
        self.max_concurrency = max_concurrency
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = client
        self._owns_client = client is None
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._tasks: dict[str, asyncio.Task[dict[str, Any]]] = {}

    async def __aenter__(self) -> "InstagramEmbedClient":
        """Create the shared HTTP client when entering the context."""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        """Close the internally owned HTTP client on context exit."""
        await self.aclose()

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Return the shared async HTTP client, creating it if needed."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(
                    max_connections=self.max_concurrency,
                    max_keepalive_connections=self.max_concurrency,
                ),
                headers={"User-Agent": "Mozilla/5.0"},
                follow_redirects=True,
            )
        return self._client

    @staticmethod
    def embed_url(shortcode: str, media_type: Any = None) -> str:
        """Build the public Embed URL for a post or Reel."""
        path = "reel" if media_type == 2 or media_type == "video" else "p"
        return f"https://www.instagram.com/{path}/{shortcode}/embed/captioned/"

    async def fetch_post(self, shortcode: str, media_type: Any = None) -> dict[str, Any]:
        """Fetch one post, reusing an in-flight task for duplicate shortcodes."""
        if not shortcode:
            return {"shortcode": shortcode, "error": "missing shortcode"}
        if shortcode in self._tasks:
            return await self._tasks[shortcode]
        task = asyncio.create_task(self._fetch_post_once(shortcode, media_type))
        self._tasks[shortcode] = task
        return await task

    async def _fetch_post_once(self, shortcode: str, media_type: Any) -> dict[str, Any]:
        """Fetch, parse, and normalize one Embed response with retry handling."""
        client = await self._ensure_client()
        url = self.embed_url(shortcode, media_type)
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                async with self._semaphore:
                    response = await client.get(url)
                if response.status_code == 404:
                    return {"shortcode": shortcode, "error": "HTTP 404"}
                if response.status_code in {401, 403}:
                    return {"shortcode": shortcode, "error": f"HTTP {response.status_code}"}
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                response.raise_for_status()
                return normalize_embed_html(response.text, shortcode)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as error:
                last_error = error
                if attempt < self.max_retries:
                    await asyncio.sleep(2**attempt)
            except httpx.HTTPStatusError as error:
                status_code = error.response.status_code
                if status_code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
                return {"shortcode": shortcode, "error": f"HTTP {status_code}"}
            except (ValueError, KeyError) as error:
                return {"shortcode": shortcode, "error": str(error)}
        return {"shortcode": shortcode, "error": str(last_error or "request failed")}

    async def fetch_many(self, posts: Iterable[Mapping[str, Any] | str]) -> list[dict[str, Any]]:
        """Fetch many posts while preserving input order and failure results."""
        items = list(posts)
        tasks = []
        for item in items:
            if isinstance(item, str):
                tasks.append(self.fetch_post(item))
            else:
                tasks.append(self.fetch_post(str(item.get("shortcode") or ""), item.get("media_type")))
        return await asyncio.gather(*tasks)

    async def aclose(self) -> None:
        """Close the internally owned HTTP client."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None


async def fetch_posts_embed(
    posts: Iterable[Mapping[str, Any] | str],
    max_concurrency: int = 10,
    timeout: float = 30,
    max_retries: int = 2,
) -> list[dict[str, Any]]:
    """Fetch a batch of Embed posts using a temporary bounded client.

    Args:
        posts: Shortcodes or timeline post dictionaries.
        max_concurrency: Maximum number of concurrent requests.
        timeout: Per-request timeout in seconds.
        max_retries: Number of transient retries.

    Returns:
        Normalized detail results in input order.
    """
    async with InstagramEmbedClient(max_concurrency, timeout, max_retries) as client:
        return await client.fetch_many(posts)


def normalize_embed_html(html: str, shortcode: str | None = None) -> dict[str, Any]:
    """Normalize context JSON, falling back to exact HTML metrics when needed."""
    try:
        context = extract_context_json(html)
        return normalize_media(get_media(context))
    except (ValueError, KeyError) as error:
        fallback = parse_post_detail_html(html, shortcode)
        if fallback.get("detail_source"):
            return fallback
        raise ValueError(str(error)) from error
