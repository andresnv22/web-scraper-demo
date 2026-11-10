"""Polite web scraper: public pages -> clean Excel / CSV.

Demo target: https://books.toscrape.com (a sandbox site built for scraping practice).
Features: pagination, robots.txt check, delay between requests, retries with
backoff, clean typed columns, no duplicates, Excel + CSV output.
"""
from __future__ import annotations

import argparse
import logging
import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import pandas as pd
import requests
from bs4 import BeautifulSoup

log = logging.getLogger("scraper")

USER_AGENT = "web-scraper-demo/0.1 (educational; contact: github.com/andresnv22)"
RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


class ScrapeError(Exception):
    """A page could not be fetched after all retries."""


# ----------------------------------------------------------------- fetching
def allowed_by_robots(url: str, session: requests.Session | None = None) -> bool:
    """True if robots.txt allows our user agent to fetch `url` (or has no robots.txt)."""
    parts = urlparse(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    parser = RobotFileParser()
    try:
        resp = (session or requests).get(robots_url, timeout=10, headers={"User-Agent": USER_AGENT})
        if resp.status_code >= 400:
            return True  # no robots.txt: nothing forbids us
        parser.parse(resp.text.splitlines())
    except requests.RequestException:
        return True
    return parser.can_fetch(USER_AGENT, url)


def fetch(url: str, session: requests.Session, retries: int = 3, backoff: float = 1.5) -> str:
    """GET a page, retrying on network errors and 5xx/429 with growing waits."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, timeout=15, headers={"User-Agent": USER_AGENT})
            if resp.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {resp.status_code}")
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return resp.text
        except requests.RequestException as exc:
            last_error = exc
            log.warning("attempt %d/%d failed for %s: %s", attempt, retries, url, exc)
            if attempt < retries:
                time.sleep(backoff * attempt)
    raise ScrapeError(f"could not fetch {url}: {last_error}")


# ------------------------------------------------------------------ parsing
def parse_listing(html: str, base_url: str) -> tuple[list[dict], str | None]:
    """Extract the products of one listing page and the URL of the next page (or None)."""
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for card in soup.select("article.product_pod"):
        link = card.select_one("h3 a")
        price = card.select_one("p.price_color")
        rating = card.select_one("p.star-rating")
        stock = card.select_one("p.instock")
        if not (link and price):
            continue  # skip malformed cards instead of crashing the whole run
        rating_word = next((c for c in (rating.get("class") or []) if c in RATINGS), "") if rating else ""
        rows.append(
            {
                "title": link.get("title") or link.get_text(strip=True),
                "price": price.get_text(strip=True),
                "rating": rating_word,
                "in_stock": "In stock" in stock.get_text() if stock else None,
                "url": urljoin(base_url, link.get("href", "")),
            }
        )
    nxt = soup.select_one("li.next a")
    return rows, (urljoin(base_url, nxt["href"]) if nxt and nxt.get("href") else None)


def clean(rows: list[dict]) -> pd.DataFrame:
    """Typed, deduplicated table: price as a number, rating as 1-5."""
    df = pd.DataFrame(rows, columns=["title", "price", "rating", "in_stock", "url"])
    if df.empty:
        return df
    df["price"] = pd.to_numeric(df["price"].str.replace(r"[^\d.]", "", regex=True), errors="coerce")
    df["rating"] = df["rating"].map(RATINGS)
    df = df.drop_duplicates(subset="url").reset_index(drop=True)
    return df.rename(columns={"price": "price_gbp"})


# ------------------------------------------------------------------ running
def scrape(start_url: str, max_pages: int = 3, delay: float = 1.0, session: requests.Session | None = None) -> pd.DataFrame:
    """Follow the 'next' links from start_url, at most max_pages pages."""
    session = session or requests.Session()
    if not allowed_by_robots(start_url, session):
        raise ScrapeError(f"robots.txt does not allow scraping {start_url}")
    rows: list[dict] = []
    url: str | None = start_url
    pages = 0
    while url and pages < max_pages:
        html = fetch(url, session)
        page_rows, url = parse_listing(html, url)
        rows.extend(page_rows)
        pages += 1
        log.info("page %d: %d items (total %d)", pages, len(page_rows), len(rows))
        if url and pages < max_pages:
            time.sleep(delay)  # be polite: do not hammer the server
    return clean(rows)


def save(df: pd.DataFrame, out_prefix: str) -> tuple[str, str]:
    xlsx, csv = f"{out_prefix}.xlsx", f"{out_prefix}.csv"
    df.to_excel(xlsx, index=False)
    df.to_csv(csv, index=False)
    return xlsx, csv


def main() -> None:
    ap = argparse.ArgumentParser(description="Scrape a public listing into Excel/CSV")
    ap.add_argument("--url", default="https://books.toscrape.com/catalogue/page-1.html")
    ap.add_argument("--pages", type=int, default=3, help="max pages to fetch")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    ap.add_argument("--out", default="books", help="output file name without extension")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    df = scrape(args.url, args.pages, args.delay)
    xlsx, csv = save(df, args.out)
    print(f"{len(df)} rows -> {xlsx} and {csv}")


if __name__ == "__main__":
    main()
