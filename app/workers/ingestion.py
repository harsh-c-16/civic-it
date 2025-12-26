"""
Ingestion worker: fetch public posts for the configured civic-issue
watch-list and persist them (deduplicated) for later enrichment.
"""

import logging
import time

from sqlalchemy.exc import IntegrityError

from app.config import settings, watchlist
from app.database import AsyncSessionLocal
from app.metrics import metrics
from app.models import Post
from app.services.reddit import fetch_posts, PostData
from app.utils import utcnow

logger = logging.getLogger(__name__)


async def _save_posts(posts: list[PostData]) -> int:
    """
    Persist posts idempotently. Each insert runs in a SAVEPOINT and relies on
    the unique constraint on post_id, so duplicates — whether from overlapping
    runs or the same post matching several queries — are skipped safely.
    """
    if not posts:
        return 0

    saved = 0
    async with AsyncSessionLocal() as session:
        for p in posts:
            try:
                async with session.begin_nested():
                    session.add(
                        Post(
                            post_id=p.post_id,
                            source=p.source,
                            text=p.text,
                            author=p.author,
                            source_context=p.source_context,
                            url=p.url,
                            language=p.language,
                            created_at=p.created_at,
                            fetched_at=utcnow(),
                            keyword_matched=p.keyword_matched,
                            is_processed=False,
                        )
                    )
                    await session.flush()  # trigger the unique check now
                saved += 1
            except IntegrityError:
                pass  # already stored — idempotent skip

        await session.commit()

    logger.info("Ingestion saved %d new posts (of %d fetched)", saved, len(posts))
    return saved


async def run_ingestion() -> int:
    """Run a single ingestion cycle over the configured watch-list."""
    started = time.perf_counter()
    posts = await fetch_posts(
        subreddits=watchlist.subreddits,
        search_keywords=watchlist.search_keywords,
        limit_per_query=settings.posts_per_keyword,
    )
    saved = await _save_posts(posts)
    metrics.record_ingestion(
        fetched=len(posts),
        saved=saved,
        duration_ms=(time.perf_counter() - started) * 1000,
    )
    return saved
