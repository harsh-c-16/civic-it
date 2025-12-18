# SentimentPulse 📊

**Transparent, aggregate sentiment monitoring for civic issues.**

SentimentPulse ingests public discussion about local-governance issues (water,
roads, transport, corruption, environment…), enriches each post with sentiment
and a topic label, and serves the results through a read-only dashboard and a
small REST API.

It is a backend portfolio project. The emphasis is on a clean asynchronous data
pipeline rather than on being a product.

> **Scope & ethics.** Sentiment is tracked over *issues*, never over named
> individuals. All sentiment scores are model-estimated, approximate, and shown
> in aggregate only. The dashboard is read-only and uses public data. This is a
> technical demo and is not affiliated with any campaign, party, or candidate.

---

## Architecture

```
                ┌──────────────────────────────────────────┐
   Reddit API   │  Ingestion worker   →   Postgres/SQLite   │
  (or seed set) │  (scheduled)            (async SQLAlchemy)│
                │        │                       ▲          │
                │        ▼                       │          │
                │  Processing worker  ───────────┘          │
                │  (VADER + topics)                         │
                │        │                                  │
                │        ▼                                  │
                │   FastAPI REST API   →   Dashboard (JS)   │
                └──────────────────────────────────────────┘
```

- **Ingestion worker** pulls posts for a configured watch-list of civic-issue
  search terms from the Reddit API (application-only OAuth). Queries fan out
  **concurrently** (`asyncio.gather`) under a **`Semaphore`** that caps in-flight
  requests for rate-limiting, with **retry + exponential backoff** per request.
- Posts are persisted **idempotently** (SAVEPOINT + unique constraint), so
  overlapping runs or duplicate results never double-insert.
- **Processing worker** scores unprocessed posts for sentiment and detects the
  civic issue/topic.
- Both run on an **APScheduler** loop inside the FastAPI app lifespan, and both
  record throughput/latency/error **metrics** exposed at `/api/stats`.
- The **API** exposes aggregate summaries, per-issue breakdowns, hourly trends,
  and a paginated post feed.

### Engineering highlights
- **Concurrency & synchronization** — bounded concurrent I/O fan-out with an
  `asyncio.Semaphore`.
- **Reliability** — retry/backoff, idempotent writes, graceful seed-data
  fallback, health check.
- **Observability** — per-stage latency, throughput, and error-rate metrics.

### Tech stack
Python 3.12 · FastAPI · async SQLAlchemy 2.0 · SQLite (Postgres-ready via
asyncpg) · APScheduler · httpx · VADER (+ a small Marathi lexicon) · Jinja2 +
Chart.js · Docker.

---

## Data sources

| Source | When used |
|--------|-----------|
| **Reddit API** | When `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` are set. |
| **Bundled seed dataset** (`seed_data.json`) | Otherwise — clearly labelled sample data so the app runs with zero setup. |

To use live Reddit data, create a *script* app at
<https://www.reddit.com/prefs/apps> and set the credentials in `.env`.

---

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open <http://localhost:8000>. On first boot the app ingests the watch-list
(Reddit if configured, otherwise the seed dataset) and processes it, so the
dashboard is populated immediately.

### With Docker

```bash
docker build -t sentimentpulse .
docker run -p 8000:8000 sentimentpulse
```

---

## API

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health + post count |
| `GET /api/summary` | Overall sentiment counts/percentages + top issues |
| `GET /api/topics` | Sentiment breakdown per civic issue |
| `GET /api/trends` | Hourly sentiment time series |
| `GET /api/recent_posts` | Paginated post feed (filters: `sentiment`, `topic`) |
| `GET /api/stats` | Pipeline metrics: throughput, latency, error rates, backlog |
| `GET /api/keywords` | The configured watch-list (transparency) |

All accept `?hours=` (default 168). Interactive docs at `/docs`.

Manual triggers (`POST /api/trigger/ingestion`, `/api/trigger/process`) are
disabled unless `ADMIN_TOKEN` is set, then require an `X-Admin-Token` header.

---

## Configuration

The watch-list lives in `config/keywords.yaml` — edit the subreddits, search
terms, and topic keywords without touching code. App settings come from
environment variables; see `.env.example`.

---

## Tests

```bash
pytest
```

---

## Known limitations

- Sentiment is **lexicon-based** (VADER + a small Marathi word list). It is fast
  and dependency-light but less accurate than a transformer model, especially on
  sarcasm, code-mixed text, and longer Marathi passages.
- Topic detection is keyword-matching, not a trained classifier.
- The seed dataset is small sample data, not real measurements.

---

Built by Harsh Chaudhari.
