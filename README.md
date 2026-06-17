# SentimentPulse

A small backend service that tracks public sentiment around civic issues. It
pulls posts from Reddit about local-governance topics (water, roads, transport,
corruption, environment, and so on), tags each one with a sentiment label and a
topic, stores the results, and serves them through a read-only dashboard and a
JSON API.

The focus of the project is the data pipeline: scheduled ingestion, async I/O,
and a clean separation between fetching, enrichment, and serving. It targets
Pune, India and handles both English and Marathi text.

A note on scope: sentiment is only ever aggregated over *issues*, never over
named people. Scores are model estimates and are shown in aggregate. The data is
public and the dashboard is read-only. It's a technical project, not affiliated
with any campaign or party.

## How it works

```
Reddit API (or seed data)
        |
        v
  Ingestion worker  -->  database (async SQLAlchemy)
        |                      ^
        v                      |
 Processing worker  -----------+
 (sentiment + topic)
        |
        v
   FastAPI  -->  dashboard + JSON API
```

Two background jobs run inside the FastAPI app on an APScheduler loop:

- **Ingestion** runs every `INGESTION_INTERVAL_MINUTES` (default 15). For each
  subreddit/keyword pair it sends a search request to Reddit's OAuth API. The
  requests fan out concurrently with `asyncio.gather`, capped by an
  `asyncio.Semaphore` so we stay inside rate limits, and each request retries
  with exponential backoff. Posts are written idempotently, so overlapping runs
  never create duplicates. If Reddit credentials are missing or a run fails, it
  falls back to the bundled `seed_data.json` so the app still has data to show.
- **Processing** runs every 2 minutes. It picks up unprocessed posts in batches,
  scores each with VADER (plus a small Marathi lexicon for Devanagari text), and
  assigns a topic by keyword matching.

Both stages update in-process counters (throughput, latency, retries, failures)
that are exposed at `/api/stats`.

## Tech

Python 3.13, FastAPI, async SQLAlchemy 2.0, SQLite by default (Postgres works
via asyncpg), APScheduler, httpx, vaderSentiment, Jinja2 + Chart.js, Docker.

## Running it

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Then open http://localhost:8000. On the first boot the app ingests and processes
the watch-list, so the dashboard isn't empty.

There's also a Makefile:

```bash
make install   # install deps
make dev       # run with reload
make test      # run tests
```

### Docker

```bash
docker build -t sentimentpulse .
docker run -p 8000:8000 sentimentpulse
```

## Reddit credentials

Without credentials the app runs on the seed dataset. To pull live data, create
a "script" app at https://www.reddit.com/prefs/apps and set these in `.env`:

```
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=sentimentpulse/2.0 (civic sentiment demo)
```

Copy `.env.example` to `.env` for the full list of settings (ingestion interval,
concurrency limits, retry count, database URL, admin token).

## API

| Endpoint | What it returns |
|----------|-----------------|
| `GET /health` | Status and post count |
| `GET /api/summary` | Overall sentiment counts/percentages and top issues |
| `GET /api/topics` | Sentiment breakdown per issue |
| `GET /api/trends` | Hourly sentiment time series |
| `GET /api/recent_posts` | Paginated feed (filters: `sentiment`, `topic`) |
| `GET /api/stats` | Pipeline metrics and backlog |
| `GET /api/keywords` | The configured watch-list |

Most endpoints take `?hours=` (default 168, i.e. one week). Interactive docs are
at `/docs`.

The manual triggers `POST /api/trigger/ingestion` and `POST /api/trigger/process`
are disabled unless `ADMIN_TOKEN` is set, and then need an `X-Admin-Token`
header.

## Configuration

The watch-list (subreddits, search terms, and topic keywords) lives in
`config/keywords.yaml` and can be edited without touching code. Everything else
comes from environment variables.

## Tests

```bash
pytest
```

## Limitations

- Sentiment is lexicon-based (VADER plus a hand-built Marathi word list). It's
  fast and has no heavy dependencies, but it's weaker than a transformer model
  on sarcasm and code-mixed text.
- Topic detection is keyword matching, not a trained classifier.
- The seed dataset is small sample data, not real measurements.

---

Built by Harsh Chaudhari.
