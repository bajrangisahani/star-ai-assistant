from html.parser import HTMLParser
from urllib.parse import urlparse

import requests
from ddgs import DDGS

from star_files import summarize_text


REQUEST_TIMEOUT = 12


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip_depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if self.skip_depth:
            return

        text = " ".join(data.split())
        if len(text) > 1:
            self.parts.append(text)

    def text(self):
        return " ".join(self.parts)


def search_web(query, max_results=5):
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=int(max_results))
    except Exception as exc:
        return [{"title": "Search failed", "href": None, "body": str(exc)}]

    return [
        {
            "title": item.get("title"),
            "href": item.get("href"),
            "body": item.get("body"),
        }
        for item in results
    ]


def research_summary(query, max_results=5):
    results = search_web(query, max_results=max_results)
    if results and results[0].get("title") == "Search failed":
        return {
            "query": query,
            "summary": "Research search failed right now.",
            "results": results,
        }

    combined = " ".join(item.get("body") or "" for item in results)
    return {
        "query": query,
        "summary": summarize_text(combined, max_sentences=4) if combined else "No results found.",
        "results": results,
    }


def latest_news(query="latest news", max_results=5):
    return research_summary(f"{query} latest news", max_results=max_results)


def weather(query):
    location = query.strip() or "current location"
    return research_summary(f"weather in {location} today", max_results=4)


def market_price(query):
    target = query.strip()
    return research_summary(f"{target} current price today", max_results=4)


def wikipedia_search(query):
    return research_summary(f"{query} site:wikipedia.org", max_results=4)


def fetch_webpage(url, max_chars=20000):
    parsed = urlparse(url)
    if not parsed.scheme:
        url = "https://" + url

    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT,
        headers={"User-Agent": "STAR Assistant/1.0"},
    )
    response.raise_for_status()

    extractor = TextExtractor()
    extractor.feed(response.text)
    text = extractor.text()

    return {
        "url": url,
        "title": extract_title(response.text),
        "text": text[: int(max_chars)],
        "chars": len(text),
        "truncated": len(text) > int(max_chars),
    }


def summarize_webpage(url):
    page = fetch_webpage(url)
    page["summary"] = summarize_text(page["text"], max_sentences=5)
    return page


def extract_title(html):
    lower = html.lower()
    start = lower.find("<title")
    if start == -1:
        return None

    start = lower.find(">", start)
    end = lower.find("</title>", start)
    if start == -1 or end == -1:
        return None

    return " ".join(html[start + 1:end].split())
