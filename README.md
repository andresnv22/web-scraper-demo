# Web scraper demo — public pages to clean Excel / CSV

A small, polite Python scraper that follows pagination and delivers a clean, typed spreadsheet.
Demo target: [books.toscrape.com](https://books.toscrape.com), a sandbox site built for scraping practice.

```bash
uv sync
uv run python scraper.py --pages 3 --out books      # -> books.xlsx + books.csv
uv run pytest                                       # 9 tests, no network needed
```

Sample output: [books.xlsx](books.xlsx) (60 rows, 3 pages).

## What it does

- **Pagination:** follows the "next" link up to `--pages` pages.
- **Polite:** checks `robots.txt` first (refuses to scrape if forbidden), identifies itself with a User-Agent, waits `--delay` seconds between requests.
- **Resilient:** retries with growing waits on network errors, 429 and 5xx; skips malformed cards instead of crashing; clear error if a page can't be fetched.
- **Clean data:** price as a number, rating as 1-5, no duplicate rows, consistent columns.
- **Output:** Excel and CSV (Google Sheets can import either).
- **Tested:** 9 pytest tests with simulated pages (pagination, robots.txt, retries, cleaning, file output).

## Scope

Public pages only. No logins, no captcha bypassing, no personal data.

## Español

Scraper en Python que recorre las páginas de un listado público y entrega una hoja de cálculo limpia (Excel/CSV): precios como número, sin duplicados, respetando `robots.txt` y con pausas entre peticiones. Incluye reintentos y 9 pruebas automáticas que corren sin internet.

---
Built by [Andrés Nuñez](https://github.com/andresnv22).
