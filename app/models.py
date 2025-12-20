"""
SQLAlchemy ORM models for SentimentPulse.

The schema is intentionally source-agnostic: a `Post` is any piece of public
discourse (currently Reddit posts/comments) that we score for sentiment and
bucket by civic issue. We never store or score named individuals.
"""

from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, Text,
    Index, CheckConstraint
)

from app.database import Base
from app.utils import utcnow


class Post(Base):
    """A unit of public discourse with sentiment-analysis results."""

    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(String(80), unique=True, nullable=False, index=True)
    source = Column(String(20), nullable=False, default="reddit")  # reddit, seed
    text = Column(Text, nullable=False)
    author = Column(String(255))
    source_context = Column(String(255))  # e.g. subreddit name
    url = Column(String(512))
    language = Column(String(10))
    created_at = Column(DateTime, nullable=False, index=True)
    fetched_at = Column(DateTime, default=utcnow)
    keyword_matched = Column(String(255), index=True)

    # Enrichment results
    sentiment = Column(String(20))  # 'positive', 'neutral', 'negative'
    sentiment_score = Column(Float)
    topic = Column(String(50), index=True)  # civic issue category
    is_processed = Column(Boolean, default=False, index=True)
    processed_at = Column(DateTime)

    __table_args__ = (
        CheckConstraint(
            "sentiment IN ('positive', 'neutral', 'negative') OR sentiment IS NULL",
            name="valid_sentiment",
        ),
        Index("idx_posts_unprocessed", "is_processed", "fetched_at"),
    )

    def __repr__(self) -> str:
        return f"<Post {self.post_id}: {self.sentiment}>"
