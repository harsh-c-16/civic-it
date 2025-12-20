"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# Post schemas
class PostResponse(BaseModel):
    id: int
    post_id: str
    source: str
    text: str
    author: Optional[str] = None
    source_context: Optional[str] = None
    url: Optional[str] = None
    language: Optional[str] = None
    created_at: datetime
    keyword_matched: Optional[str] = None
    sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None
    topic: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PostListResponse(BaseModel):
    posts: list[PostResponse]
    total: int
    page: int
    page_size: int


# Sentiment summary schemas
class SentimentCounts(BaseModel):
    positive: int = 0
    neutral: int = 0
    negative: int = 0
    total: int = 0


class SentimentPercentages(BaseModel):
    positive: float = 0.0
    neutral: float = 0.0
    negative: float = 0.0


class SentimentSummary(BaseModel):
    counts: SentimentCounts
    percentages: SentimentPercentages
    time_range: str
    last_updated: datetime


class OverallSummaryResponse(BaseModel):
    summary: SentimentSummary
    top_topics: list[dict]


# Time series schemas
class TimeSeriesPoint(BaseModel):
    timestamp: datetime
    positive: int = 0
    neutral: int = 0
    negative: int = 0
    total: int = 0
    sentiment_score: float = 0.0


class TrendResponse(BaseModel):
    data: list[TimeSeriesPoint]
    time_range: str
    bucket_size: str


# Topic schemas
class TopicSentiment(BaseModel):
    topic: str
    positive: int = 0
    neutral: int = 0
    negative: int = 0
    total: int = 0
    dominant_sentiment: str = "neutral"


class TopicsResponse(BaseModel):
    topics: list[TopicSentiment]
    time_range: str


# Health check
class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str
    database: str = "connected"
    last_ingestion: Optional[datetime] = None
    posts_count: int = 0
