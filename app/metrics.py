"""
Lightweight in-process metrics for the ingestion/enrichment pipeline.

Counters are updated from background workers and read by the /api/stats
endpoint. No lock is needed: the workers run as async jobs on the single
event loop (APScheduler's AsyncIOScheduler), so updates never interleave
across threads.
"""

from app.utils import utcnow


class PipelineMetrics:
    def __init__(self) -> None:
        # Ingestion stage
        self.ingestion_runs = 0
        self.ingestion_last_at = None
        self.ingestion_last_ms = 0.0
        self.posts_fetched = 0
        self.posts_saved = 0
        # Reddit request reliability
        self.reddit_requests = 0
        self.reddit_failures = 0
        self.reddit_retries = 0
        # Processing stage
        self.processing_runs = 0
        self.processing_last_at = None
        self.processing_last_ms = 0.0
        self.posts_processed = 0
        self.processing_errors = 0

    def record_request(self, *, success: bool, retries: int = 0) -> None:
        self.reddit_requests += 1
        self.reddit_retries += retries
        if not success:
            self.reddit_failures += 1

    def record_ingestion(self, *, fetched: int, saved: int, duration_ms: float) -> None:
        self.ingestion_runs += 1
        self.ingestion_last_at = utcnow()
        self.ingestion_last_ms = round(duration_ms, 1)
        self.posts_fetched += fetched
        self.posts_saved += saved

    def record_processing(self, *, processed: int, errors: int, duration_ms: float) -> None:
        self.processing_runs += 1
        self.processing_last_at = utcnow()
        self.processing_last_ms = round(duration_ms, 1)
        self.posts_processed += processed
        self.processing_errors += errors

    def snapshot(self) -> dict:
        failure_rate = (
            round(self.reddit_failures / self.reddit_requests, 3)
            if self.reddit_requests else 0.0
        )
        return {
            "ingestion": {
                "runs": self.ingestion_runs,
                "last_run_at": self.ingestion_last_at,
                "last_duration_ms": self.ingestion_last_ms,
                "posts_fetched_total": self.posts_fetched,
                "posts_saved_total": self.posts_saved,
            },
            "reddit_requests": {
                "total": self.reddit_requests,
                "failures": self.reddit_failures,
                "retries": self.reddit_retries,
                "failure_rate": failure_rate,
            },
            "processing": {
                "runs": self.processing_runs,
                "last_run_at": self.processing_last_at,
                "last_duration_ms": self.processing_last_ms,
                "posts_processed_total": self.posts_processed,
                "errors": self.processing_errors,
            },
        }


# Global instance
metrics = PipelineMetrics()
