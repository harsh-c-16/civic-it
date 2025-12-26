"""
Enrichment worker: runs sentiment analysis and topic detection on any
posts that haven't been processed yet.
"""

import asyncio
import logging
import time

from sqlalchemy import select

from app.database import get_session_context
from app.metrics import metrics
from app.models import Post
from app.services.sentiment import analyze_sentiment
from app.services.topics import detect_topic
from app.utils import utcnow

logger = logging.getLogger(__name__)


class SentimentProcessor:
    """Processes unanalysed posts in batches."""

    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size

    async def process_batch(self) -> tuple[int, int]:
        """Process one batch; returns (processed, errors)."""
        async with get_session_context() as session:
            result = await session.execute(
                select(Post)
                .where(Post.is_processed == False)  # noqa: E712
                .order_by(Post.fetched_at.asc())
                .limit(self.batch_size)
            )
            posts = result.scalars().all()
            if not posts:
                return 0, 0

            errors = 0
            for post in posts:
                try:
                    sentiment, score = analyze_sentiment(post.text)
                    post.sentiment = sentiment
                    post.sentiment_score = score
                    post.topic = detect_topic(post.text)
                except Exception as e:
                    errors += 1
                    logger.error("Error processing %s: %s", post.post_id, e)
                finally:
                    post.is_processed = True
                    post.processed_at = utcnow()

            await session.commit()
            logger.info("Processed %d posts (%d errors)", len(posts), errors)
            return len(posts), errors

    async def process_all(self) -> tuple[int, int]:
        total, total_errors = 0, 0
        while True:
            processed, errors = await self.process_batch()
            total += processed
            total_errors += errors
            if processed < self.batch_size:
                break
            await asyncio.sleep(0.1)
        return total, total_errors


async def run_processor(batch_size: int = 100) -> int:
    """Run a single processing cycle over all unprocessed posts."""
    started = time.perf_counter()
    processed, errors = await SentimentProcessor(batch_size=batch_size).process_all()
    metrics.record_processing(
        processed=processed,
        errors=errors,
        duration_ms=(time.perf_counter() - started) * 1000,
    )
    return processed
