# ============================================================
# HoofMarketIQ — Dockerfile
# Multi-stage build: scraper → Bubble.io (no Supabase)
# ============================================================

# ── Stage 1: deps ────────────────────────────────────────────
FROM python:3.12-slim AS deps

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ── Stage 2: runtime ─────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && cp /usr/share/zoneinfo/America/Chicago /etc/localtime \
    && echo "America/Chicago" > /etc/timezone

# ── Copy installed packages from deps stage ──────────────────
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# ── Create non-root user ────────────────────────────────────
RUN useradd -m -u 1000 scraper

WORKDIR /app

# ── Copy application code ───────────────────────────────────
COPY --chown=scraper:scraper . .

# ── Create log directory ────────────────────────────────────
RUN mkdir -p /app/logs && chown scraper:scraper /app/logs
VOLUME ["/app/logs"]

USER scraper

# ── Environment defaults (override via docker-compose or .env) ─
ENV TESTING_MODE=false \
    SCRAPE_INTERVAL_HOURS=6 \
    LOG_DIR=/app/logs \
    TZ=America/Chicago \
    PYTHONPATH=/app

EXPOSE 8010

# ── Health check: ping the /health endpoint ──────────────────
HEALTHCHECK --interval=5m --timeout=10s --start-period=60s --retries=3 \
CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8010/health', timeout=5).status == 200 else 1)"

# ── Start FastAPI server with scheduler ──────────────────────
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8010"]
