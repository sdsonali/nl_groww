"""One LangChain tool that fetches recent mutual-fund and SIP headlines.

The tool runs once. The existing NVIDIA client writes the summary. This does not
loop the model, and it does not turn a headline into a buy or sell.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool

from chat.llm import complete
from chat.router import first_json
from chat.safety import FUND_RE, allowed_scheme_names

HERE_PROMPT = PromptTemplate.from_template(
    "Language: {language}\n\nHeadlines JSON:\n{headlines}\n\nUser message:\n{message}\n"
)
SYSTEM = (Path(__file__).resolve().parent / "prompts" / "news.txt").read_text().strip()

NEWS_RE = re.compile(
    r"\bnews\b|\bheadlines?\b|\bsamachar\b|\bkhabar\b|"
    r"\b(latest|recent|any)\s+updates?\b|\bupdates?\s+on\b|\bkya\s+update\b",
    re.I,
)
FILLER_RE = re.compile(
    r"\b(what|whats|what's|is|are|the|a|an|any|latest|recent|news|headline|"
    r"headlines|update|updates|about|on|for|me|tell|please|can|you|kya|hai|"
    r"of|in|this|my|show|give)\b",
    re.I,
)
RSS = "https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
NO_HEADLINES = (
    "I couldn't find a recent headline for that, so I don't want to guess. "
    "You can try the scheme name, or ask about the SIP instalment."
)


def is_news_question(text):
    return bool(NEWS_RE.search(text or ""))


def search_url(query):
    return RSS.format(query=quote_plus(query or "India SIP mutual fund"))


def build_query(message):
    """Prefer a scheme name from the notes. Otherwise use the user's topic."""
    text = message or ""
    lowered = text.lower()
    match = ""
    for name in allowed_scheme_names():
        if name.lower() in lowered and len(name) > len(match):
            match = name
    if match:
        return match + " mutual fund"
    cleaned = FILLER_RE.sub(" ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ?.,")
    if len(cleaned) < 3:
        cleaned = "India SIP mutual fund"
    return (cleaned[:120] + " mutual fund India").strip()


def fetch_rss(url, timeout=8):
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


STOP_WORDS = {
    "mutual",
    "fund",
    "india",
    "scheme",
    "direct",
    "growth",
    "latest",
    "news",
    "update",
    "about",
}


def within_days(items, days=45):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    kept = []
    for item in items:
        try:
            when = parsedate_to_datetime(item.get("published") or "")
        except (TypeError, ValueError, IndexError, OverflowError):
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when >= cutoff:
            kept.append(item)
    return kept


def relevant_headlines(items, query, limit=5):
    """Keep headlines that mention the scheme or topic, so a loose match is not treated as news."""
    tokens = [
        word.lower()
        for word in re.findall(r"[A-Za-z0-9]+", query or "")
        if len(word) >= 4 and word.lower() not in STOP_WORDS
    ]
    specific = [word for word in tokens if word != "groww"]
    needed = specific or tokens
    if not needed:
        return items[:limit]
    kept = []
    for item in items:
        title = (item.get("title") or "").lower()
        if any(word in title for word in needed):
            kept.append(item)
        if len(kept) >= limit:
            break
    return kept


def parse_rss(xml_bytes, limit=12):
    if isinstance(xml_bytes, str):
        xml_bytes = xml_bytes.encode("utf-8")
    root = ElementTree.fromstring(xml_bytes)
    items = []
    for node in root.findall("./channel/item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        published = (node.findtext("pubDate") or "").strip()
        if not title:
            continue
        items.append({"title": title, "link": link, "published": published})
        if len(items) >= limit:
            break
    return items


@tool
def mutual_fund_news(query: str) -> str:
    """Recent Indian mutual-fund and SIP headlines. Input is a short search query."""
    url = search_url(query)
    xml_bytes = fetch_rss(url)
    items = within_days(relevant_headlines(parse_rss(xml_bytes), query, limit=12))[:5]
    return json.dumps(items, ensure_ascii=True)


def prepare_news(message):
    """Run the news tool once. Returns (headlines, source_url)."""
    query = build_query(message)
    url = search_url(query)
    try:
        raw = mutual_fund_news.invoke({"query": query})
        items = json.loads(raw)
    except Exception:
        return [], url
    if not isinstance(items, list):
        return [], url
    return items, url


def headline_names(items):
    """Names the summary is allowed to repeat, because they are in a fetched headline."""
    names = []
    for item in items or []:
        title = item.get("title") or ""
        names.append(title)
        names.extend(match.group(0) for match in FUND_RE.finditer(title))
    return names


def summarize_news(message, language, items, llm=None):
    caller = llm or complete
    user = HERE_PROMPT.format(
        language=language or "english",
        headlines=json.dumps(items, ensure_ascii=True),
        message=message,
    )
    text = caller(SYSTEM, user, 500)
    return first_json(text)
