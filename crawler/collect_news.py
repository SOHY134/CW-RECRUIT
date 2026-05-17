from __future__ import annotations

import hashlib
import html
import os
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

import feedparser
import requests
from dateutil import parser as date_parser

from crawler.classifier import calculate_score, detect_category, detect_competitor, is_internal_company, priority_from_score
from crawler.dedupe import is_duplicate
from crawler.insight import make_card
from crawler.keywords import CATEGORY_ORDER, FALLBACK_CATEGORIES
from crawler.sources import RSS_QUERIES, build_feed_urls
from crawler.validator import fetch_meta, source_level

KST = ZoneInfo("Asia/Seoul")
MAX_AGE_DAYS = int(os.environ.get("MAX_AGE_DAYS", "7"))
MAX_ITEMS = int(os.environ.get("MAX_ITEMS", "6"))
MIN_DISPLAY_ITEMS = int(os.environ.get("MIN_DISPLAY_ITEMS", "3"))
MAX_CANDIDATES = int(os.environ.get("MAX_CANDIDATES", "80"))
ENTRIES_PER_FEED = int(os.environ.get("ENTRIES_PER_FEED", "10"))
MAX_FEEDS = int(os.environ.get("MAX_FEEDS", "50"))
FEED_TIMEOUT = int(os.environ.get("FEED_TIMEOUT", "6"))


def now_kst() -> datetime:
    return datetime.now(tz=KST)


def parse_published(entry) -> datetime | None:
    for key in ("published", "updated", "created"):
        value = getattr(entry, key, None) or entry.get(key)
        if not value:
            continue
        try:
            return date_parser.parse(value).astimezone(KST)
        except Exception:
            try:
                return parsedate_to_datetime(value).astimezone(KST)
            except Exception:
                continue
    return None


def clean_text(value: str) -> str:
    return html.unescape(value or "").replace("<b>", "").replace("</b>", "").strip()


def stable_id(title: str, url: str, date: str) -> str:
    digest = hashlib.sha1(f"{title}|{url}".encode("utf-8")).hexdigest()[:10]
    return f"{date.replace('-', '')}-{digest}"


def age_days(published: datetime, base: datetime) -> int:
    return max(0, (base.date() - published.date()).days)


def collect_from_naver_api(base_time: datetime) -> list[dict]:
    client_id = os.environ.get("NAVER_CLIENT_ID")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET")
    if not client_id or not client_secret:
        return []

    headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
    collected = []
    queries = [q for values in RSS_QUERIES.values() for q in values]
    for query in queries:
        try:
            r = requests.get(
                "https://openapi.naver.com/v1/search/news.json",
                params={"query": query.replace(" OR ", " "), "display": 10, "sort": "date"},
                headers=headers,
                timeout=10,
            )
            if r.status_code >= 400:
                continue
            for item in r.json().get("items", []):
                published = parsedate_to_datetime(item.get("pubDate", "")).astimezone(KST)
                if age_days(published, base_time) > MAX_AGE_DAYS:
                    continue
                url = item.get("link") or item.get("originallink")
                collected.append({
                    "title": clean_text(item.get("title", "")),
                    "url": url,
                    "published": published,
                    "source": "네이버뉴스",
                    "description": clean_text(item.get("description", ""))[:240],
                })
        except Exception:
            continue
    return collected


def collect_from_google_rss(base_time: datetime) -> list[dict]:
    collected = []
    for feed_url in build_feed_urls()[:MAX_FEEDS]:
        try:
            response = requests.get(feed_url, timeout=FEED_TIMEOUT, headers={"User-Agent": "Mozilla/5.0 CWRecruitIntel/1.0"})
            if response.status_code >= 400:
                continue
            feed = feedparser.parse(response.content)
        except Exception:
            continue
        for entry in feed.entries[:ENTRIES_PER_FEED]:
            published = parse_published(entry)
            if not published or age_days(published, base_time) > MAX_AGE_DAYS:
                continue
            source = "Google News"
            if getattr(entry, "source", None):
                source = entry.source.get("title") or source
            collected.append({
                "title": clean_text(entry.get("title", "")),
                "url": entry.get("link", ""),
                "published": published,
                "source": source,
                "description": clean_text(entry.get("summary", ""))[:240],
            })
    return collected


def normalize_candidate(candidate: dict, base_time: datetime) -> dict | None:
    title = candidate.get("title", "").strip()
    url = candidate.get("url", "").strip()
    published = candidate.get("published")
    if not title or not url or not published:
        return None
    if is_internal_company(title):
        return None

    category, urgency, keyword = detect_category(" ".join([title, candidate.get("description", "")]))
    if not category:
        return None

    meta = fetch_meta(url)
    if not meta.get("ok"):
        return None
    final_url = meta.get("url") or url
    level = source_level(final_url)
    competitor = detect_competitor(title)
    days = age_days(published, base_time)
    score = calculate_score(category, urgency, competitor, days, level)
    published_date = published.date().isoformat()
    published_time = published.strftime("%H:%M")

    return {
        "id": stable_id(title, final_url, published_date),
        "title": title,
        "url": final_url,
        "original_url": url,
        "category": category,
        "urgency": urgency,
        "keyword": keyword,
        "competitor": competitor,
        "score": score,
        "priority": priority_from_score(score, category, urgency),
        "published_date": published_date,
        "published_time": published_time,
        "source": candidate.get("source") or "뉴스",
        "level": level,
        "description": meta.get("description") or candidate.get("description", ""),
        "verified": bool(meta.get("verified", True)),
        "verify_note": meta.get("verify_note", ""),
        "http_status": meta.get("status"),
    }


def rank_items(items: list[dict]) -> list[dict]:
    order = {cat: idx for idx, cat in enumerate(CATEGORY_ORDER)}
    return sorted(items, key=lambda x: (x.get("score", 0), -order.get(x.get("category", "hr"), 99)), reverse=True)


def select_final_items(items: list[dict]) -> list[dict]:
    ranked = rank_items(items)
    core = [x for x in ranked if x["category"] in {"outflow", "leader", "hiring"}]
    fallback = [x for x in ranked if x["category"] in FALLBACK_CATEGORIES]
    selected = []
    seen_ids = set()
    for item in core + fallback + ranked:
        if item["id"] in seen_ids:
            continue
        selected.append(item)
        seen_ids.add(item["id"])
        if len(selected) >= max(MIN_DISPLAY_ITEMS, MAX_ITEMS):
            break
    return selected[:MAX_ITEMS]


def collect_cards(report_date: str | None = None) -> dict:
    base_time = now_kst()
    report_date = report_date or base_time.date().isoformat()
    raw_candidates = collect_from_naver_api(base_time) + collect_from_google_rss(base_time)

    titles = []
    normalized = []
    for candidate in raw_candidates[:MAX_CANDIDATES]:
        title = candidate.get("title", "")
        if is_duplicate(title, titles):
            continue
        item = normalize_candidate(candidate, base_time)
        if not item:
            continue
        normalized.append(item)
        titles.append(title)

    selected = select_final_items(normalized)
    cards = [make_card(item, report_date) for item in selected]
    summary = f"최근 {MAX_AGE_DAYS}일 이내 실제 URL이 확인된 채용시장 신호 {len(cards)}건을 수집했습니다."
    contact_targets = [c["company"] for c in cards if c.get("priority")][:5]
    return {"date": report_date, "summary": summary, "contact_targets": contact_targets, "items": cards}
