# ============================================================
# HoofMarketIQ — Dockerfile
# Scraper container: Python 3.12 + httpx
# ============================================================

FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ── Minimal system deps ───────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── Non-root user ─────────────────────────────────────────────
RUN useradd -m -u 1000 scraper
WORKDIR /app

# ── Python deps ───────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── App source ────────────────────────────────────────────────
COPY --chown=scraper:scraper . .

# ── Logs directory ────────────────────────────────────────────
RUN mkdir -p /app/logs && chown scraper:scraper /app/logs
VOLUME ["/app/logs"]

USER scraper

ENV TESTING_MODE=false \
    LOG_DIR=/app/logs \
    TZ=America/Chicago

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8010"]
