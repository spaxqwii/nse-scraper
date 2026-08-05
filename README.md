# nse-scraper

Laptop-side NSE stock scraper. Fetches daily prices from [afx.kwayisi.org](https://afx.kwayisi.org/nse/) and pushes parsed data to an SQS queue consumed by [stock-notifier](https://github.com/spaxqwii/stock-notifier).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your SQS_QUEUE_URL
```

## Run

```bash
# Dry run (parse only, no SQS)
python local_scraper.py --dry-run

# Full pipeline: scrape → push to SQS
python local_scraper.py

# Show more preview rows
python local_scraper.py --limit 20
```

## Cron (daily at 4:30 PM EAT)

```bash
30 16 * * * cd ~/workstuff/nse-scraper && /usr/bin/python3 local_scraper.py >> scraper.log 2>&1
```
