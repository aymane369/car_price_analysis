import argparse
import json
import random
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.moteur.ma/fr/voiture/achat-voiture-occasion"
LISTING_STRIDE = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Referer": BASE_URL,
}


def clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def make_page_url(offset: int) -> str:
    return BASE_URL if offset == 0 else f"{BASE_URL}/{offset}"


def fetch_html(session: requests.Session, url: str, retries: int = 5) -> str:
    last_error = None
    for attempt in range(retries):
        try:
            response = session.get(url, headers=HEADERS, timeout=30)
            if response.status_code in {429, 500, 502, 503, 504}:
                raise requests.HTTPError(f"HTTP {response.status_code}")
            response.raise_for_status()
            return response.text
        except Exception as exc:  # noqa: BLE001 - keep scraper resilient
            last_error = exc
            sleep_for = min(10, 1.5 * (attempt + 1)) + random.uniform(0.2, 1.0)
            time.sleep(sleep_for)
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def read_jsonl_urls(path: Path) -> set[str]:
    urls: set[str] = set()
    if not path.exists():
        return urls
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            url = obj.get("url")
            if url:
                urls.add(url)
    return urls


def extract_listing_links(soup: BeautifulSoup, page_url: str) -> list[dict]:
    links: list[dict] = []
    seen: set[str] = set()

    for a in soup.select('a[href*="/detail-annonce/"]'):
        href = a.get("href")
        if not href:
            continue
        abs_url = urljoin(page_url, href)
        if abs_url in seen:
            continue
        seen.add(abs_url)
        links.append(
            {
                "url": abs_url,
                "title_from_listing": clean(a.get_text(" ", strip=True)),
                "source_page": page_url,
            }
        )

    return links


def parse_jsonld(soup: BeautifulSoup) -> list:
    items = []
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text(" ", strip=True)
        raw = raw.strip()
        if not raw:
            continue
        try:
            items.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return items


def add_pair(store: dict, key: str, value: str) -> None:
    key = clean(key).rstrip(":")
    value = clean(value)
    if key and value and key not in store:
        store[key] = value


def extract_key_values(soup: BeautifulSoup) -> dict:
    fields: dict[str, str] = {}

    for dl in soup.find_all("dl"):
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        if len(dts) == len(dds) and dts:
            for dt, dd in zip(dts, dds, strict=False):
                add_pair(fields, dt.get_text(" ", strip=True), dd.get_text(" ", strip=True))

    for tr in soup.find_all("tr"):
        cells = tr.find_all(["th", "td"])
        if len(cells) >= 2:
            add_pair(fields, cells[0].get_text(" ", strip=True), cells[1].get_text(" ", strip=True))

    for li in soup.select("li"):
        txt = clean(li.get_text(" ", strip=True))
        if " : " in txt:
            key, value = txt.split(" : ", 1)
            add_pair(fields, key, value)
        elif ": " in txt:
            key, value = txt.split(": ", 1)
            add_pair(fields, key, value)

    return fields


def extract_images(soup: BeautifulSoup, page_url: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if not src:
            continue
        abs_src = urljoin(page_url, src)
        if abs_src in seen:
            continue
        seen.add(abs_src)
        urls.append(abs_src)

    return urls


def extract_visible_text(soup: BeautifulSoup) -> str:
    main = soup.find("main") or soup.body or soup
    return clean(main.get_text(" ", strip=True))


def extract_detail(session: requests.Session, url: str) -> dict:
    html = fetch_html(session, url)
    soup = BeautifulSoup(html, "html.parser")

    meta = {}
    for tag in soup.select("meta[property], meta[name]"):
        key = tag.get("property") or tag.get("name")
        value = tag.get("content")
        if key and value:
            meta[key] = value

    title = (
        meta.get("og:title")
        or clean(soup.select_one("h1").get_text(" ", strip=True) if soup.select_one("h1") else "")
    )

    description = meta.get("description") or meta.get("og:description") or ""

    canonical = ""
    canonical_tag = soup.select_one('link[rel="canonical"]')
    if canonical_tag and canonical_tag.get("href"):
        canonical = canonical_tag["href"]

    data = {
        "url": url,
        "canonical_url": canonical,
        "title": title,
        "description": description,
        "meta": meta,
        "jsonld": parse_jsonld(soup),
        "fields": extract_key_values(soup),
        "images": extract_images(soup, url),
        "visible_text": extract_visible_text(soup),
    }

    return data


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape all used-car listings from moteur.ma and save them as JSONL."
    )
    parser.add_argument(
        "--output",
        default="data/raw/moteur_ma_cars.jsonl",
        help="Output JSONL file",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.7,
        help="Delay in seconds between requests (use a small value for polite scraping)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=0,
        help="Stop after this many listing pages (0 = no explicit limit)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip URLs that are already present in the output JSONL file",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    processed_urls = read_jsonl_urls(output_path) if args.resume else set()

    session = requests.Session()
    page_index = 0
    scraped = 0

    with output_path.open("a", encoding="utf-8") as out:
        while True:
            if args.max_pages and page_index >= args.max_pages:
                break

            offset = page_index * LISTING_STRIDE
            page_url = make_page_url(offset)
            html = fetch_html(session, page_url)
            soup = BeautifulSoup(html, "html.parser")

            listing_links = extract_listing_links(soup, page_url)
            if not listing_links:
                break

            print(f"page {page_index + 1}: {len(listing_links)} listings")

            for item in listing_links:
                url = item["url"]
                if url in processed_urls:
                    continue

                try:
                    detail = extract_detail(session, url)
                    record = {
                        **item,
                        **detail,
                        "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    }
                    out.write(json.dumps(record, ensure_ascii=False) + "\n")
                    out.flush()
                    processed_urls.add(url)
                    scraped += 1
                except Exception as exc:  # noqa: BLE001 - keep going on single-ad failures
                    error_record = {
                        **item,
                        "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "error": str(exc),
                    }
                    out.write(json.dumps(error_record, ensure_ascii=False) + "\n")
                    out.flush()

                time.sleep(args.delay + random.uniform(0, args.delay))

            page_index += 1
            time.sleep(args.delay)

    print(f"done, scraped {scraped} new detail pages into {output_path}")


if __name__ == "__main__":
    main()
