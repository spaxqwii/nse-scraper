#!/usr/bin/env python3
"""
NSE Local Scraper — Laptop-side client
Fetches NSE stock data and pushes to SQS for the stock-notifier pipeline.
Run daily at 4:30 PM EAT via cron or manually.
"""
import os
import sys
import json
import re
import argparse
from datetime import datetime, timezone

import boto3
import requests

# ── Config ──────────────────────────────────────────────────────
NSE_URL = "https://afx.kwayisi.org/nse/"
SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL", "")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-1")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ── Scraper ─────────────────────────────────────────────────────
def fetch_html():
    resp = requests.get(NSE_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def extract_stocks(html):
    """Parse NSE table with unclosed HTML5 tags."""
    table_blocks = []
    for m in re.finditer(r'<table[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE):
        table_blocks.append(m.group(1))

    stock_raw = max(table_blocks, key=lambda t: t.lower().count('<tr'))
    raw_rows = re.split(r'<tr[^>]*>', stock_raw, flags=re.IGNORECASE)

    stocks = []
    for raw in raw_rows:
        cells = re.split(r'<t[dh][^>]*>', raw, flags=re.IGNORECASE)
        if len(cells) < 6:
            continue
        clean = [re.sub(r'<[^>]+>', '', c).strip() for c in cells[1:6]]
        if len(clean) < 5:
            continue
        ticker, name, volume, price, change = clean
        if ticker == "Ticker" or not price:
            continue
        stocks.append({
            "ticker": ticker,
            "name": name,
            "volume": int(volume.replace(",", "")) if volume else 0,
            "price": float(price.replace(",", "")) if price else 0.0,
            "change": change,
        })
    return stocks


# ── SQS Push ────────────────────────────────────────────────────
def push_to_sqs(stocks):
    if not SQS_QUEUE_URL:
        print("[ERR] SQS_QUEUE_URL not set. Set it in your .env file.")
        sys.exit(1)

    sqs = boto3.client("sqs", region_name=AWS_REGION)
    msg = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "stocks": stocks,
        "source": "laptop-nse-scraper",
        "scraped_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    }
    resp = sqs.send_message(
        QueueUrl=SQS_QUEUE_URL,
        MessageBody=json.dumps(msg)
    )
    print(f"[OK] Pushed {len(stocks)} stocks to SQS — MessageId: {resp['MessageId']}")


# ── Main ────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="NSE Local Scraper")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, don't push to SQS")
    parser.add_argument("--limit", type=int, default=5, help="Preview limit (default: 5)")
    args = parser.parse_args()

    print(f"Fetching {NSE_URL} ...")
    html = fetch_html()
    print(f"HTTP Status: 200 | Content length: {len(html)} bytes")

    stocks = extract_stocks(html)
    print(f"Total stocks parsed: {len(stocks)}")

    if not stocks:
        print("[!] No stocks found. Check nse_debug.html.")
        with open("nse_debug.html", "w", encoding="utf-8") as f:
            f.write(html)
        sys.exit(1)

    for s in stocks[:args.limit]:
        print(f"  {s['ticker']:<8} | {s['name'][:35]:<35} | "
              f"Vol: {s['volume']:>10,} | Price: {s['price']:>8.2f} | Change: {s['change']}")

    if not args.dry_run:
        push_to_sqs(stocks)
    else:
        print("
(Dry run — not pushing to SQS)")


if __name__ == "__main__":
    main()
