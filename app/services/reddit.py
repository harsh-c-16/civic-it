"""
Reddit ingestion for SentimentPulse.

Pulls public posts matching civic-issue search terms via Reddit's official
OAuth API (application-only / client_credentials grant). When no credentials
are configured — or a request fails — it falls back to a bundled, clearly
labelled seed dataset so the dashboard is always populated for a demo.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from app.config import settings
from app.metrics import metrics
from app.utils import utcnow

logger = logging.getLogger(__name__)

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
API_BASE = "https://oauth.reddit.com"
SEED_PATH = Path(__file__).parent.parent.parent / "seed_data.json"


@dataclass
class PostData:
    """Normalised public post, source-agnostic."""
    post_id: str
    source: str
    text: str
    author: str
    source_context: str  # subreddit
    url: str
    language: str
    created_at: datetime
    keyword_matched: str


def _detect_language(text: str) -> str:
    """Devanagari (Marathi/Hindi) vs Latin script."""
    return "mr" if re.search(r"[ऀ-ॿ]", text) else "en"


class RedditClient:
    """Read-only Reddit API client using application-only OAuth."""

    def __init__(self) -> None:
        self.client_id = settings.reddit_client_id
        self.client_secret = settings.reddit_client_secret
        self.user_agent = settings.reddit_user_agent
        self._token: str | None = None
        self.http = httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": self.user_agent},
        )

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    async def _authenticate(self) -> None:
        resp = await self.http.post(
            TOKEN_URL,
            auth=(self.client_id, self.client_secret),
            data={"grant_type": "client_credentials"},
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        logger.info("Reddit OAuth token acquired")

    async def search(
        self, subreddit: str, query: str, limit: int = 25
    ) -> list[PostData]:
        """Single search request against a subreddit (newest first)."""
        url = f"{API_BASE}/r/{subreddit}/search"
        params = {
            "q": query,
            "restrict_sr": 1,
            "sort": "new",
            "t": "month",
            "limit": min(limit, 100),
        }
        resp = await self.http.get(
            url,
            params=params,
            headers={"Authorization": f"bearer {self._token}"},
        )
        resp.raise_for_status()

        posts: list[PostData] = []
        for child in resp.json().get("data", {}).get("children", []):
            d = child.get("data", {})
            title = d.get("title", "") or ""
            body = d.get("selftext", "") or ""
            text = f"{title}\n{body}".strip()
            if not text:
                continue
            posts.append(
                PostData(
                    post_id=f"reddit_{d.get('id')}",
                    source="reddit",
                    text=text[:4000],
                    author=str(d.get("author", "unknown")),
                    source_context=subreddit,
                    url=f"https://reddit.com{d.get('permalink', '')}",
                    language=_detect_language(text),
                    created_at=datetime.fromtimestamp(
                        d.get("created_utc", utcnow().timestamp()), timezone.utc
                    ).replace(tzinfo=None),
                    keyword_matched=query,
                )
            )
        return posts

    async def search_with_retry(
        self, subreddit: str, query: str, limit: int, max_retries: int
    ) -> list[PostData]:
        """Retry a search with exponential backoff; record request metrics."""
        delay = 0.5
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                posts = await self.search(subreddit, query, limit)
                metrics.record_request(success=True, retries=attempt)
                logger.info("Reddit r/%s '%s': %d posts", subreddit, query, len(posts))
                return posts
            except Exception as e:  # transient HTTP/network errors
                last_exc = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
        metrics.record_request(success=False, retries=max_retries - 1)
        logger.warning("Reddit search failed (r/%s '%s') after %d attempts: %s",
                       subreddit, query, max_retries, last_exc)
        return []

    async def close(self) -> None:
        await self.http.aclose()


# Module-level singleton: one client (and its connection pool) is reused across
# ingestion runs instead of being rebuilt every cycle.
_client: RedditClient | None = None


def _get_client() -> RedditClient:
    global _client
    if _client is None:
        _client = RedditClient()
    return _client


async def close_client() -> None:
    """Dispose the shared client (e.g. on app shutdown)."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def load_seed_posts(keyword_filter: str | None = None) -> list[PostData]:
    """Load the bundled sample dataset (used when Reddit is unconfigured)."""
    if not SEED_PATH.exists():
        return []
    with open(SEED_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    posts: list[PostData] = []
    now = utcnow()
    for i, item in enumerate(raw):
        text = item.get("text", "")
        posts.append(
            PostData(
                post_id=item.get("post_id", f"seed_{i}"),
                source="seed",
                text=text,
                author=item.get("author", "sample_user"),
                source_context=item.get("source_context", "sample"),
                url=item.get("url", ""),
                language=_detect_language(text),
                # Spread sample posts across the past week so the trend chart
                # and time-window filter are meaningful in the demo.
                created_at=now - timedelta(hours=i * 6),
                keyword_matched=item.get("keyword_matched", ""),
            )
        )
    return posts


async def fetch_posts(
    subreddits: list[str],
    search_keywords: list[str],
    limit_per_query: int = 25,
    max_concurrency: int | None = None,
    max_retries: int | None = None,
) -> list[PostData]:
    """
    Fetch posts from Reddit for the configured watch-list.

    Each (subreddit x keyword) query runs as a concurrent task, but a
    Semaphore caps how many hit Reddit at once so we stay within rate limits.
    Falls back to the seed dataset if Reddit is not configured or fails.
    """
    max_concurrency = max_concurrency or settings.max_concurrent_requests
    max_retries = max_retries or settings.request_max_retries

    client = _get_client()
    if not client.configured:
        logger.warning("Reddit credentials not set — using seed dataset")
        return load_seed_posts()

    # Authenticate once per run (refreshes the token), before fanning out.
    try:
        await client._authenticate()
    except Exception as e:
        logger.warning("Reddit auth failed (%s) — using seed dataset", e)
        return load_seed_posts()

    semaphore = asyncio.Semaphore(max_concurrency)

    async def _bounded_search(subreddit: str, query: str) -> list[PostData]:
        async with semaphore:  # cap concurrent in-flight requests
            return await client.search_with_retry(
                subreddit, query, limit_per_query, max_retries
            )

    tasks = [
        _bounded_search(subreddit, query)
        for query in search_keywords
        for subreddit in subreddits
    ]

    all_posts: list[PostData] = []
    for posts in await asyncio.gather(*tasks):
        all_posts.extend(posts)

    if not all_posts:
        logger.warning("Reddit returned no posts — using seed dataset")
        return load_seed_posts()
    return all_posts
