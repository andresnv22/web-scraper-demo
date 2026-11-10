"""Tests run with no network: pages are simulated."""
import pandas as pd
import pytest
import requests

import scraper

PAGE_1 = """
<html><body>
<article class="product_pod">
  <p class="star-rating Three"></p>
  <h3><a href="a-book_1/index.html" title="A Book">A Book...</a></h3>
  <p class="price_color">£51.77</p>
  <p class="instock availability">In stock</p>
</article>
<article class="product_pod">
  <p class="star-rating Five"></p>
  <h3><a href="second_2/index.html" title="Second">Second</a></h3>
  <p class="price_color">£12.50</p>
  <p class="instock availability">In stock</p>
</article>
<article class="product_pod"><h3>broken card without link or price</h3></article>
<ul class="pager"><li class="next"><a href="page-2.html">next</a></li></ul>
</body></html>
"""

PAGE_2 = """
<html><body>
<article class="product_pod">
  <p class="star-rating One"></p>
  <h3><a href="third_3/index.html" title="Third">Third</a></h3>
  <p class="price_color">£9.99</p>
  <p class="instock availability">In stock</p>
</article>
<article class="product_pod">
  <p class="star-rating Three"></p>
  <h3><a href="a-book_1/index.html" title="A Book">A Book...</a></h3>
  <p class="price_color">£51.77</p>
  <p class="instock availability">In stock</p>
</article>
</body></html>
"""


class FakeResponse:
    def __init__(self, text="", status=200):
        self.text, self.status_code, self.encoding = text, status, "utf-8"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    """Serves pages from a dict; records every requested URL."""

    def __init__(self, pages, robots=None):
        self.pages, self.robots, self.calls = pages, robots, []

    def get(self, url, **kwargs):
        self.calls.append(url)
        if url.endswith("/robots.txt"):
            return FakeResponse(self.robots or "", 200 if self.robots is not None else 404)
        return FakeResponse(self.pages[url]) if url in self.pages else FakeResponse("", 404)


BASE = "https://shop.test/catalogue/page-1.html"
PAGES = {BASE: PAGE_1, "https://shop.test/catalogue/page-2.html": PAGE_2}


def test_parse_listing_extracts_items_and_next_link():
    rows, nxt = scraper.parse_listing(PAGE_1, BASE)
    assert [r["title"] for r in rows] == ["A Book", "Second"]  # broken card skipped
    assert rows[0]["url"] == "https://shop.test/catalogue/a-book_1/index.html"
    assert rows[0]["rating"] == "Three" and rows[0]["in_stock"] is True
    assert nxt == "https://shop.test/catalogue/page-2.html"


def test_parse_listing_last_page_has_no_next():
    _, nxt = scraper.parse_listing(PAGE_2, "https://shop.test/catalogue/page-2.html")
    assert nxt is None


def test_clean_types_and_dedup():
    rows = scraper.parse_listing(PAGE_1, BASE)[0] + scraper.parse_listing(PAGE_2, BASE)[0]
    df = scraper.clean(rows)
    assert len(df) == 3                     # the repeated "A Book" is removed
    assert df["price_gbp"].dtype == float and df["price_gbp"].iloc[0] == 51.77
    assert list(df["rating"]) == [3, 5, 1]


def test_scrape_follows_pagination():
    session = FakeSession(PAGES)
    df = scraper.scrape(BASE, max_pages=5, delay=0, session=session)
    assert len(df) == 3
    assert "https://shop.test/catalogue/page-2.html" in session.calls


def test_scrape_respects_max_pages():
    session = FakeSession(PAGES)
    df = scraper.scrape(BASE, max_pages=1, delay=0, session=session)
    assert len(df) == 2
    assert "https://shop.test/catalogue/page-2.html" not in session.calls


def test_scrape_obeys_robots_txt():
    session = FakeSession(PAGES, robots="User-agent: *\nDisallow: /catalogue/")
    with pytest.raises(scraper.ScrapeError):
        scraper.scrape(BASE, max_pages=2, delay=0, session=session)
    assert BASE not in session.calls        # never touched the forbidden page


def test_fetch_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(scraper.time, "sleep", lambda s: None)

    class Flaky:
        n = 0

        def get(self, url, **kwargs):
            Flaky.n += 1
            return FakeResponse("ok", 503 if Flaky.n < 3 else 200)

    assert scraper.fetch("https://shop.test/x", Flaky()) == "ok"
    assert Flaky.n == 3


def test_fetch_gives_up_with_clear_error(monkeypatch):
    monkeypatch.setattr(scraper.time, "sleep", lambda s: None)

    class Down:
        def get(self, url, **kwargs):
            raise requests.ConnectionError("down")

    with pytest.raises(scraper.ScrapeError):
        scraper.fetch("https://shop.test/x", Down(), retries=2)


def test_save_writes_excel_and_csv(tmp_path):
    df = scraper.clean(scraper.parse_listing(PAGE_1, BASE)[0])
    xlsx, csv = scraper.save(df, str(tmp_path / "out"))
    assert len(pd.read_excel(xlsx)) == 2
    assert len(pd.read_csv(csv)) == 2
