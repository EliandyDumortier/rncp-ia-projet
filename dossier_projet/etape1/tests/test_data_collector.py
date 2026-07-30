from pathlib import Path
import sys
from unittest.mock import Mock

import pytest
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from data_collector import CSVCollector, MyDramaListScraper, run_collection


def test_csv_collector_sets_english_name_from_column(tmp_path):
    csv_path = tmp_path / "kdramas.csv"
    csv_path.write_text(
        "Name,English Name,Year of Release,Genre,Score\n"
        "The Glory,The Glory,2022,Drama,8.7\n",
        encoding="utf-8",
    )

    collector = CSVCollector(csv_path)
    records = collector.collect()

    assert records[0]["english_name"] == "The Glory"


def test_run_collection_skips_sources_when_pages_are_zero(tmp_path, monkeypatch):
    calls = []

    def fake_tmdb_run_full_collection(*args, **kwargs):
        calls.append("tmdb")
        return []

    def fake_scrape_top_kdramas(*args, **kwargs):
        calls.append("scrape")
        return []

    monkeypatch.setattr(
        "data_collector.TMDBCollector.run_full_collection",
        fake_tmdb_run_full_collection,
    )
    monkeypatch.setattr(
        "data_collector.MyDramaListScraper.scrape_top_kdramas",
        fake_scrape_top_kdramas,
    )

    run_collection(max_tmdb_pages=0, max_scrape_pages=0, output_dir=tmp_path)

    assert calls == []


def test_fetch_page_uses_html_body_when_request_is_forbidden(monkeypatch):
    scraper = MyDramaListScraper(delay=0)
    fake_response = Mock()
    fake_response.raise_for_status.side_effect = requests.exceptions.HTTPError("403")
    fake_response.status_code = 403
    fake_response.text = "<html><body><a href='/735043-life'>Drama</a></body></html>"

    monkeypatch.setattr(scraper.session, "get", lambda *args, **kwargs: fake_response)
    monkeypatch.setattr(scraper, "_fetch_page_with_playwright", lambda url: None)

    soup = scraper._fetch_page("https://example.com")

    assert soup is not None
    assert soup.select_one("a[href='/735043-life']") is not None


def test_fetch_page_falls_back_to_playwright(monkeypatch):
    scraper = MyDramaListScraper(delay=0)
    fake_response = Mock()
    fake_response.raise_for_status.side_effect = None
    fake_response.status_code = 403
    fake_response.text = "Attention Required! | Cloudflare"

    monkeypatch.setattr(scraper.session, "get", lambda *args, **kwargs: fake_response)

    fake_soup = object()
    monkeypatch.setattr(scraper, "_fetch_page_with_playwright", lambda url: fake_soup)

    assert scraper._fetch_page("https://example.com") is fake_soup


def test_tmdb_makes_english_api_requests_by_default(monkeypatch):
    from data_collector import TMDBCollector

    collector = TMDBCollector(api_key="dummy")

    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"results": []}
        return response

    monkeypatch.setattr(collector.session, "get", fake_get)
    collector._make_request("/discover/tv", params={"page": 1})

    assert captured["params"]["language"] == "en-US"
    assert captured["params"]["api_key"] == "dummy"


def test_tmdb_normalize_uses_english_name_when_available():
    from data_collector import TMDBCollector

    collector = TMDBCollector(api_key="dummy")
    raw = {"id": 1, "name": "달의 연인", "original_name": "달의 연인"}
    details = {
        "original_name": "달의 연인",
        "overview": "A gentle romance story",
        "translations": {
            "translations": [
                {
                    "iso_639_1": "en",
                    "data": {"name": "Love in the Moonlight"},
                }
            ]
        },
    }

    normalized = collector.normalize_kdrama(raw, details)

    assert normalized["english_name"] == "Love in the Moonlight"
    assert normalized["titre"] == "Love in the Moonlight"
    assert normalized["titre_original"] == "달의 연인"
    assert normalized["synopsis"] == "A gentle romance story"


def test_extract_synopsis_prefers_english_show_synopsis():
    scraper = MyDramaListScraper(delay=0)
    soup = BeautifulSoup(
        """
        <html>
          <head>
            <meta name="description" content="Fallback synopsis" />
          </head>
          <body>
            <div class="show-synopsis">A beautiful English synopsis for the drama.</div>
          </body>
        </html>
        """,
        "lxml",
    )

    assert scraper._extract_synopsis(soup) == "A beautiful English synopsis for the drama."


def test_extract_drama_links_matches_relative_and_absolute_hrefs():
    scraper = MyDramaListScraper(delay=0)
    soup = BeautifulSoup(
        """
        <html><body>
            <a href="/735043-life">Relative drama</a>
            <a href="https://mydramalist.com/739603-sparkling-watermelon">Absolute drama</a>
            <a href="/shows/top">Other page</a>
        </body></html>
        """,
        "lxml",
    )

    links = scraper._extract_drama_links(soup)

    assert len(links) == 2
    assert links[0].get("href") == "/735043-life"
    assert links[1].get("href") == "https://mydramalist.com/739603-sparkling-watermelon"
