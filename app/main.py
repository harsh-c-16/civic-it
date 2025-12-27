"""
SentimentPulse — FastAPI application.

A transparent, aggregate sentiment monitor for civic issues. Public discourse
(via the Reddit API, or a bundled seed dataset) is ingested on a schedule,
enriched with sentiment + topic, and served through a read-only dashboard.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.api.routes import router as api_router
from app.config import settings, watchlist
from app.database import init_db, close_db
from app.workers.ingestion import run_ingestion
from app.workers.processor import run_processor

logging.basicConfig(
    level=logging.INFO if settings.debug else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def scheduled_ingestion():
    try:
        count = await run_ingestion()
        logger.info("Ingestion complete: %d new posts", count)
    except Exception as e:
        logger.error("Ingestion error: %s", e)


async def scheduled_processing():
    try:
        count = await run_processor()
        logger.info("Processing complete: %d posts", count)
    except Exception as e:
        logger.error("Processing error: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting SentimentPulse...")
    await init_db()

    # Populate on first boot so the dashboard isn't empty
    async def _bootstrap():
        await scheduled_ingestion()
        await scheduled_processing()

    asyncio.create_task(_bootstrap())

    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduled_ingestion, "interval",
                      minutes=settings.ingestion_interval_minutes, id="ingestion")
    scheduler.add_job(scheduled_processing, "interval", minutes=2, id="processing")
    scheduler.start()
    logger.info("Scheduler started (ingestion every %d min)",
                settings.ingestion_interval_minutes)

    yield

    logger.info("Shutting down...")
    scheduler.shutdown(wait=False)
    await close_db()


app = FastAPI(
    title="SentimentPulse",
    description="Transparent aggregate sentiment monitoring for civic issues.",
    version="2.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
app.include_router(api_router)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Public, read-only dashboard."""
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "project": watchlist.project_info},
    )


def _require_admin_token(x_admin_token: str | None) -> None:
    """Guard manual trigger endpoints. If ADMIN_TOKEN is unset, they're disabled."""
    if not settings.admin_token or x_admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Forbidden")


@app.post("/api/trigger/ingestion")
async def trigger_ingestion(x_admin_token: str | None = Header(default=None)):
    _require_admin_token(x_admin_token)
    return {"status": "success", "posts_ingested": await run_ingestion()}


@app.post("/api/trigger/process")
async def trigger_processing(x_admin_token: str | None = Header(default=None)):
    _require_admin_token(x_admin_token)
    return {"status": "success", "posts_processed": await run_processor()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
