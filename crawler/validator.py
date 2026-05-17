from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

BLACKLIST = [
    "search.naver.com",
    "google.com/search",
    "jobkorea.co.kr/Search/",
    "jobplanet.co.kr/companies?",
    "teamblind.com/kr/search/",
    "saramin.co.kr/zf_user/search",
    "wanted.co.kr/search",
    "linkedin.com/search",
]

SOURCE_LEVEL_A = ["dart.fss.or.kr", "kind.krx.co.kr", "moel.go.kr", "korea.kr", "fsc.go.kr", "ftc.go.kr"]
SOURCE_LEVEL_B = ["n.news.naver.com", "yna.co.kr", "hankyung.com", "mk.co.kr", "etnews.com", "zdnet.co.kr", "bloter.net"]

HOMEPAGE_DOMAINS = {
    "news.naver.com",
    "n.news.naver.com",
    "www.teamblind.com",
    "www.jobplanet.co.kr",
    "www.jobkorea.co.kr",
    "www.saramin.co.kr",
    "www.incruit.com",
    "www.wanted.co.kr",
    "www.linkedin.com",
    "linkedin.com",
    "it.chosun.com",
    "www.thebell.co.kr",
}


def is_blacklisted(url: str) -> bool:
    if not url:
        return True
    lowered = url.lower()
    return any(b.lower() in lowered for b in BLACKLIST)


def has_article_like_path(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if not parsed.scheme.startswith("http") or not parsed.netloc:
        return False
    path = parsed.path.strip("/")
    if not path:
        return False
    if parsed.netloc.lower() in HOMEPAGE_DOMAINS and path in {"", "search", "kr/search"}:
        return False
    return True


def source_level(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if any(domain in host for domain in SOURCE_LEVEL_A):
        return "A"
    if any(domain in host for domain in SOURCE_LEVEL_B):
        return "B"
    return "B"


def fetch_meta(url: str, timeout: int = 4) -> dict:
    if is_blacklisted(url) or not has_article_like_path(url):
        return {"ok": False, "url": url, "verify_note": "blocked homepage/search URL"}
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 CWRecruitIntel/1.0"}, allow_redirects=True)
        if r.status_code >= 400:
            return {"ok": False, "url": url, "status": r.status_code, "verify_note": f"HTTP {r.status_code}"}
        final_url = r.url
        if is_blacklisted(final_url) or not has_article_like_path(final_url):
            return {"ok": False, "url": final_url, "status": r.status_code, "verify_note": "redirected to blocked URL"}
        soup = BeautifulSoup(r.text[:200000], "html.parser")
        desc = ""
        tag = soup.find("meta", attrs={"property": "og:description"}) or soup.find("meta", attrs={"name": "description"})
        if tag and tag.get("content"):
            desc = re.sub(r"\s+", " ", tag["content"]).strip()
        return {
            "ok": True,
            "url": final_url,
            "status": r.status_code,
            "description": desc[:260],
            "verified": True,
            "verify_note": f"HTTP {r.status_code}",
        }
    except Exception:
        return {"ok": False, "url": url, "verify_note": "request failed"}


def parse_dt(value) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None
