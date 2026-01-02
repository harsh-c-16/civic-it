"""Tests for the Reddit ingestion service (seed fallback + concurrency)."""

import asyncio

from app.services.reddit import fetch_posts, load_seed_posts


def test_seed_dataset_loads():
    posts = load_seed_posts()
    assert len(posts) > 0
    assert all(p.source == "seed" for p in posts)


async def test_fetch_falls_back_to_seed_without_credentials():
    # No Reddit credentials in the test env -> seed dataset.
    posts = await fetch_posts(
        subreddits=["pune"],
        search_keywords=["water", "roads"],
        limit_per_query=10,
    )
    assert len(posts) > 0
    assert all(p.source == "seed" for p in posts)


async def test_bounded_concurrency_respects_semaphore(monkeypatch):
    """Concurrent fan-out must never exceed max_concurrency in flight."""
    from app.services import reddit

    # Pretend we're configured so the real fan-out path runs.
    monkeypatch.setattr(reddit.RedditClient, "configured", property(lambda self: True))

    async def _noop_auth(self):
        self._token = "test"

    monkeypatch.setattr(reddit.RedditClient, "_authenticate", _noop_auth)

    in_flight = 0
    peak = 0

    async def _fake_search(self, subreddit, query, limit, max_retries):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.01)
        in_flight -= 1
        return [reddit.load_seed_posts()[0]]

    monkeypatch.setattr(reddit.RedditClient, "search_with_retry", _fake_search)

    await fetch_posts(
        subreddits=["a", "b", "c", "d"],
        search_keywords=["q1", "q2", "q3"],  # 12 tasks
        max_concurrency=3,
    )
    assert peak <= 3
