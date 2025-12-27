"""
API routes for the SentimentPulse dashboard.

All endpoints report aggregate sentiment over civic issues. There is no
per-individual scoring by design.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.models import Post
from app.schemas import (
    HealthResponse,
    OverallSummaryResponse,
    PostListResponse,
    PostResponse,
    TrendResponse,
    TopicsResponse,
    SentimentSummary,
    SentimentCounts,
    SentimentPercentages,
    TimeSeriesPoint,
    TopicSentiment,
)
from app.config import watchlist
from app.metrics import metrics
from app.utils import utcnow

router = APIRouter()


def _since(hours: int) -> datetime:
    return utcnow() - timedelta(hours=hours)


def _percentages(counts: SentimentCounts) -> SentimentPercentages:
    if counts.total == 0:
        return SentimentPercentages()
    return SentimentPercentages(
        positive=round(counts.positive / counts.total * 100, 1),
        neutral=round(counts.neutral / counts.total * 100, 1),
        negative=round(counts.negative / counts.total * 100, 1),
    )


# Reusable processed-post filter
def _processed_since(since: datetime):
    return and_(Post.is_processed == True, Post.created_at >= since)  # noqa: E712


@router.get("/health", response_model=HealthResponse)
async def health_check(session: AsyncSession = Depends(get_async_session)):
    try:
        count = (await session.execute(select(func.count(Post.id)))).scalar() or 0
        last = (
            await session.execute(
                select(Post.fetched_at).order_by(Post.fetched_at.desc()).limit(1)
            )
        ).scalar()
        return HealthResponse(
            status="healthy", version="2.0.0", database="connected",
            posts_count=count, last_ingestion=last,
        )
    except Exception as e:
        return HealthResponse(
            status="unhealthy", version="2.0.0",
            database=f"error: {e}", posts_count=0,
        )


@router.get("/api/summary", response_model=OverallSummaryResponse)
async def get_summary(
    hours: int = Query(default=168, ge=1, le=720),
    session: AsyncSession = Depends(get_async_session),
):
    since = _since(hours)
    row = (
        await session.execute(
            select(
                func.count(Post.id).label("total"),
                func.count(case((Post.sentiment == "positive", 1))).label("positive"),
                func.count(case((Post.sentiment == "neutral", 1))).label("neutral"),
                func.count(case((Post.sentiment == "negative", 1))).label("negative"),
            ).where(_processed_since(since))
        )
    ).one()
    counts = SentimentCounts(
        total=row.total or 0, positive=row.positive or 0,
        neutral=row.neutral or 0, negative=row.negative or 0,
    )

    topic_rows = await session.execute(
        select(
            Post.topic,
            func.count(Post.id).label("total"),
            func.count(case((Post.sentiment == "positive", 1))).label("positive"),
            func.count(case((Post.sentiment == "negative", 1))).label("negative"),
        )
        .where(and_(_processed_since(since), Post.topic.isnot(None)))
        .group_by(Post.topic)
        .order_by(func.count(Post.id).desc())
        .limit(10)
    )
    top_topics = [
        {"topic": r.topic, "total": r.total, "positive": r.positive, "negative": r.negative}
        for r in topic_rows
    ]

    return OverallSummaryResponse(
        summary=SentimentSummary(
            counts=counts,
            percentages=_percentages(counts),
            time_range=f"last_{hours}h",
            last_updated=utcnow(),
        ),
        top_topics=top_topics,
    )


@router.get("/api/topics", response_model=TopicsResponse)
async def get_topics(
    hours: int = Query(default=168, ge=1, le=720),
    session: AsyncSession = Depends(get_async_session),
):
    since = _since(hours)
    rows = await session.execute(
        select(
            Post.topic,
            func.count(Post.id).label("total"),
            func.count(case((Post.sentiment == "positive", 1))).label("positive"),
            func.count(case((Post.sentiment == "neutral", 1))).label("neutral"),
            func.count(case((Post.sentiment == "negative", 1))).label("negative"),
        )
        .where(and_(_processed_since(since), Post.topic.isnot(None)))
        .group_by(Post.topic)
        .order_by(func.count(Post.id).desc())
    )

    topics = []
    for r in rows:
        counts = {"positive": r.positive, "neutral": r.neutral, "negative": r.negative}
        dominant = max(counts, key=counts.get)
        topics.append(
            TopicSentiment(
                topic=r.topic, total=r.total, positive=r.positive,
                neutral=r.neutral, negative=r.negative, dominant_sentiment=dominant,
            )
        )
    return TopicsResponse(topics=topics, time_range=f"last_{hours}h")


@router.get("/api/trends", response_model=TrendResponse)
async def get_trends(
    hours: int = Query(default=168, ge=1, le=720),
    session: AsyncSession = Depends(get_async_session),
):
    """Hourly sentiment trend, bucketed in Python (DB-engine agnostic)."""
    since = _since(hours)
    rows = await session.execute(
        select(Post.created_at, Post.sentiment, Post.sentiment_score)
        .where(_processed_since(since))
        .order_by(Post.created_at.asc())
    )

    buckets: dict[datetime, dict] = defaultdict(
        lambda: {"positive": 0, "neutral": 0, "negative": 0, "total": 0, "score_sum": 0.0}
    )
    for created_at, sentiment, score in rows:
        bucket = created_at.replace(minute=0, second=0, microsecond=0)
        b = buckets[bucket]
        b["total"] += 1
        b["score_sum"] += score or 0.0
        if sentiment in ("positive", "neutral", "negative"):
            b[sentiment] += 1

    data = [
        TimeSeriesPoint(
            timestamp=ts,
            positive=b["positive"], neutral=b["neutral"], negative=b["negative"],
            total=b["total"],
            sentiment_score=round(b["score_sum"] / b["total"], 3) if b["total"] else 0.0,
        )
        for ts, b in sorted(buckets.items())
    ]
    return TrendResponse(data=data, time_range=f"last_{hours}h", bucket_size="60min")


@router.get("/api/recent_posts", response_model=PostListResponse)
async def get_recent_posts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    hours: int = Query(default=168, ge=1, le=720),
    sentiment: Optional[str] = Query(default=None),
    topic: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_async_session),
):
    since = _since(hours)
    query = select(Post).where(_processed_since(since))
    if sentiment:
        query = query.where(Post.sentiment == sentiment)
    if topic:
        query = query.where(Post.topic == topic)

    total = (
        await session.execute(select(func.count()).select_from(query.subquery()))
    ).scalar() or 0

    query = (
        query.order_by(Post.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    posts = (await session.execute(query)).scalars().all()

    return PostListResponse(
        posts=[PostResponse.model_validate(p) for p in posts],
        total=total, page=page, page_size=page_size,
    )


@router.get("/api/stats")
async def get_stats(session: AsyncSession = Depends(get_async_session)):
    """Pipeline metrics: ingestion/processing throughput, latency, reliability."""
    total = (await session.execute(select(func.count(Post.id)))).scalar() or 0
    processed = (
        await session.execute(
            select(func.count(Post.id)).where(Post.is_processed == True)  # noqa: E712
        )
    ).scalar() or 0
    by_source_rows = await session.execute(
        select(Post.source, func.count(Post.id)).group_by(Post.source)
    )
    by_source = {src: count for src, count in by_source_rows}

    snap = metrics.snapshot()
    snap["database"] = {
        "total_posts": total,
        "processed": processed,
        "backlog": total - processed,
        "by_source": by_source,
    }
    return snap


@router.get("/api/keywords")
async def get_watchlist():
    """The configured civic-issue watch-list (transparency)."""
    return {
        "project": watchlist.project_info,
        "subreddits": watchlist.subreddits,
        "search_keywords": watchlist.search_keywords,
        "topics": list(watchlist.topics.keys()),
    }
