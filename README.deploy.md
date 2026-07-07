# HoofMarketIQ — Scraper Deployment Guide

## What this container does
Scrapes WildlifeBuyer, BuckTrader, and OnlineHuntingAuctions on a schedule,
stores listings in Supabase, and runs analytics after each scrape.

---

## Requirements
- Docker 20.10+
- Docker Compose v2+
- Supabase project with credentials

---

## Environment Variables

Create a `.env` file (never commit this):

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
TESTING_MODE=false
```

| Variable             | Description                              | Default  |
|----------------------|------------------------------------------|----------|
| `SUPABASE_URL`       | Supabase project URL                     | required |
| `SUPABASE_SERVICE_KEY` | Supabase service role key              | required |
| `TESTING_MODE`       | `true` = 30min schedule, `false` = 24h  | `false`  |
| `LOG_DIR`            | Log file directory inside container      | `/app/logs` |
| `TZ`                 | Timezone for scheduler                   | `America/Chicago` |

---

## Build

```bash
docker build -t hoofmarket-scraper:latest .
```

---

## Run — Production (24h scheduler)

```bash
# Using docker compose (recommended)
docker compose up -d

# Or plain docker
docker run -d \
  --name hoofmarket_scraper \
  --restart unless-stopped \
  --env-file .env \
  --shm-size=256m \
  -v $(pwd)/logs:/app/logs \
  hoofmarket-scraper:latest
```

---

## Run — Single scrape (testing / manual trigger)

```bash
docker run --rm \
  --env-file .env \
  --shm-size=256m \
  hoofmarket-scraper:latest \
  python main.py --once
```

---

## Logs

```bash
# Follow live logs
docker compose logs -f

# Or from the volume
tail -f ./logs/hoofmarket.log
```

---

## Stop / Restart

```bash
docker compose down        # stop
docker compose up -d       # start
docker compose restart     # restart
```

---

## Push to Registry (for cloud deployment)

```bash
# Tag for your registry
docker tag hoofmarket-scraper:latest your-registry/hoofmarket-scraper:latest

# Push
docker push your-registry/hoofmarket-scraper:latest
```

---

## Deploy on a VPS / Cloud VM

```bash
# 1. Copy files to server
scp -r . user@your-server:/opt/hoofmarket/

# 2. SSH in
ssh user@your-server

# 3. Build and start
cd /opt/hoofmarket
docker compose up -d --build

# 4. Verify running
docker compose ps
docker compose logs -f
```

---

## Health Check

The container is healthy if:
- `docker compose ps` shows `Up`
- `docker compose logs` shows `✅ All scrapers done` periodically
- Supabase `listings` table row count increases after each run

---

## Scheduler

| Mode            | Interval | Set via                    |
|-----------------|----------|----------------------------|
| Production      | 24 hours | `TESTING_MODE=false` (default) |
| Testing         | 30 min   | `TESTING_MODE=true`        |

Scheduler timezone: `America/Chicago` (Texas time)
First run happens immediately on container start.
