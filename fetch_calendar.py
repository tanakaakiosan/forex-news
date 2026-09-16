#!/usr/bin/env python3
"""
scrape_forex_factory.py

Scrapes the Forex Factory economic calendar (https://www.forexfactory.com/calendar)
and writes the current week's events to a JSON file.

Notes on timezone:
    Forex Factory's calendar displays times in the site's configured timezone
    (by default: America/New York). This script does NOT convert those times;
    it stores them exactly as shown on the page. Only "updated_at" is recorded
    in JST, as a run-timestamp for your own reference.

Usage:
    python scrape_forex_factory.py [-o OUTPUT_PATH] [--retries N] [--timeout SECONDS]

Environment variables:
    FF_OUTPUT_PATH   Overrides the default output path (calendar_data.json)

Requirements:
    pip install -r requirements.txt
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import cloudscraper
from bs4 import BeautifulSoup
from bs4.element import Tag

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

URL = "https://www.forexfactory.com/calendar"
JST = timezone(timedelta(hours=9))

# Cycle through a couple of browser fingerprints in case one gets flagged.
BROWSER_PROFILES = [
    {"browser": "chrome", "platform": "windows", "desktop": True},
    {"browser": "chrome", "platform": "darwin", "desktop": True},
    {"browser": "firefox", "platform": "windows", "desktop": True},
]


def fetch_page(timeout: int = 15, retries: int = 3, backoff: float = 2.0) -> Optional[str]:
    """Fetch the calendar page HTML, retrying with backoff on failure."""
    last_error: Optional[Exception] = None

    for attempt in range(1, retries + 1):
        profile = BROWSER_PROFILES[(attempt - 1) % len(BROWSER_PROFILES)]
        scraper = cloudscraper.create_scraper(browser=profile)
        try:
            logger.info("Fetching %s (attempt %d/%d, profile=%s)", URL, attempt, retries, profile)
            response = scraper.get(URL, timeout=timeout)
            response.raise_for_status()
            return response.text
        except Exception as exc:  # noqa: BLE001 - want to retry on anything network-related
            last_error = exc
            logger.warning("Attempt %d failed: %s", attempt, exc)
            if attempt < retries:
                sleep_for = backoff ** attempt
                logger.info("Retrying in %.1fs...", sleep_for)
                time.sleep(sleep_for)

    logger.error("All %d attempts failed. Last error: %s", retries, last_error)
    return None


def classify_impact(impact_cell: Optional[Tag]) -> str:
    """
    Determine impact level from a calendar__impact cell.

    Prefers the `title` attribute of the inner icon span (e.g. "High Impact
    Expected", "Non-Economic"), which is far more reliable than matching CSS
    color classes. Falls back to class-name matching if no title is present.
    """
    if impact_cell is None:
        return "Unknown"

    icon = impact_cell.find("span")
    if icon is None:
        return "Unknown"

    title = (icon.get("title") or "").strip().lower()
    if title:
        if "high" in title:
            return "High"
        if "medium" in title:
            return "Medium"
        if "low" in title:
            return "Low"
        if "non-economic" in title or "non economic" in title:
            return "Non-Economic"

    # Fallback: infer from CSS classes on the icon.
    classes = " ".join(icon.get("class", [])).lower()
    if "red" in classes:
        return "High"
    if "ora" in classes or "orange" in classes:
        return "Medium"
    if "yel" in classes or "yellow" in classes:
        return "Low"
    if "gra" in classes or "gray" in classes or "grey" in classes:
        return "Non-Economic"

    return "Unknown"


def scrape_forex_factory_calendar(timeout: int = 15, retries: int = 3) -> Optional[dict]:
    """Scrape the calendar page and return a dict with events, or None on failure."""
    html = fetch_page(timeout=timeout, retries=retries)
    if html is None:
        return None

    soup = BeautifulSoup(html, "html.parser")
    now_jst = datetime.now(JST)

    result: dict = {
        "updated_at": now_jst.strftime("%Y-%m-%d %H:%M:%S JST"),
        "source_timezone_note": (
            "date/time fields are exactly as displayed on forexfactory.com "
            "at scrape time (site default: America/New York)"
        ),
        "events": [],
    }

    rows = soup.find_all("tr", class_="calendar__row")

    current_date = ""
    current_time = ""

    for row in rows:
        date_cell = row.find("td", class_="calendar__date")
        if date_cell and date_cell.text.strip():
            current_date = date_cell.text.strip()

        time_cell = row.find("td", class_="calendar__time")
        if time_cell and time_cell.text.strip():
            current_time = time_cell.text.strip()

        currency_cell = row.find("td", class_="calendar__currency")
        currency = currency_cell.text.strip() if currency_cell else ""

        event_cell = row.find("td", class_="calendar__event")
        event_title = event_cell.text.strip() if event_cell else ""

        impact_cell = row.find("td", class_="calendar__impact")
        impact_level = classify_impact(impact_cell)

        # Keep only rows that have both a currency and an event title.
        if currency and event_title:
            result["events"].append(
                {
                    "date": current_date,
                    "time": current_time,
                    "currency": currency,
                    "event": event_title,
                    "impact": impact_level,
                }
            )

    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape the Forex Factory economic calendar.")
    parser.add_argument(
        "-o",
        "--output",
        default=os.environ.get("FF_OUTPUT_PATH", "calendar_data.json"),
        help="Output JSON file path (default: calendar_data.json, or $FF_OUTPUT_PATH)",
    )
    parser.add_argument("--timeout", type=int, default=15, help="Request timeout in seconds")
    parser.add_argument("--retries", type=int, default=3, help="Number of fetch retries")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    data = scrape_forex_factory_calendar(timeout=args.timeout, retries=args.retries)

    if not data or not data["events"]:
        logger.error("Failed to retrieve data. No output file written.")
        return 1

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    logger.info("%s successfully written. (%d events extracted)", args.output, len(data["events"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
