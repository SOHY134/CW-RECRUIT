from __future__ import annotations

import re

from crawler.competitors import ALL_COMPETITORS, CW_INTERNAL
from crawler.keywords import CATEGORY_KEYWORDS

BASE_SCORE = {"outflow": 80, "leader": 75, "hiring": 45, "foreign": 35, "hr": 25}
URGENCY_BONUS = {"high": 25, "mid": 12, "low": 4}
NEWS_SOURCE_SUFFIX = re.compile(
    r"\s[-–—]\s[가-힣A-Za-z0-9 .·&]{2,24}"
    r"(뉴스|경제|신문|일보|방송|저널|투데이|데일리|타임즈|미디어|News|Daily|Times)?\s*$",
    re.IGNORECASE,
)
LEADING_COMPANY = re.compile(r"^\s*([A-Za-z0-9&.\-가-힣·]+(?:\s?[A-Za-z0-9&.\-가-힣·]+){0,3})\s*[,，]")
PUBLIC_ENTITY_SUFFIXES = ("시", "도", "군", "구", "정부", "중기부", "고용노동부")
MEDIA_NAMES = {
    "전자신문", "경향신문", "서울경제", "서울경제TV", "기계신문", "뉴스핌", "굿모닝경제",
    "뉴닉", "이데일리", "IT조선", "약업신문", "직썰", "연합뉴스", "한국경제", "매일경제",
    "조선비즈", "ZDNet Korea", "블로터", "딜사이트", "뉴스1", "머니투데이",
}
KNOWN_COMPANY_ALIASES = [
    "쿠팡풀필먼트서비스",
    "쿠팡",
    "CFS",
    "메타",
    "Meta",
    "HLB",
    "DH",
    "Delivery Hero",
    "딜리버리히어로",
    "배민",
    "배달의민족",
    "우아한형제들",
    "LG전자",
    "삼성전자",
    "홈플러스",
    "롯데마트",
    "이마트24",
    "카카오게임즈",
    "카카오엔터",
    "아모레퍼시픽",
    "LG생활건강",
]


def contains_any(text: str, words: list[str]) -> str | None:
    lowered = text.lower()
    for word in words:
        if word.lower() in lowered:
            return word
    return None


def detect_category(text: str) -> tuple[str | None, str, str | None]:
    best = None
    best_urgency = "low"
    best_keyword = None
    for category, groups in CATEGORY_KEYWORDS.items():
        for urgency in ("high", "mid", "low"):
            keyword = contains_any(text, groups.get(urgency, []))
            if keyword:
                if best is None or URGENCY_BONUS[urgency] > URGENCY_BONUS[best_urgency]:
                    best, best_urgency, best_keyword = category, urgency, keyword
    return best, best_urgency, best_keyword


def detect_competitor(text: str) -> str | None:
    lowered = text.lower().replace(" ", "")
    for name in ALL_COMPETITORS:
        if name.lower().replace(" ", "") in lowered:
            return name
    return None


def is_internal_company(text: str) -> bool:
    lowered = text.lower().replace(" ", "")
    return any(name.lower().replace(" ", "") in lowered for name in CW_INTERNAL)


def strip_source_suffix(title: str) -> str:
    return NEWS_SOURCE_SUFFIX.sub("", title or "").strip()


def is_public_entity(name: str | None) -> bool:
    if not name:
        return False
    return any(name.endswith(suffix) for suffix in PUBLIC_ENTITY_SUFFIXES)


def detect_company(text: str) -> str | None:
    cleaned = strip_source_suffix(text)
    competitor = detect_competitor(cleaned)
    if competitor:
        return competitor

    lowered = cleaned.lower().replace(" ", "")
    for name in KNOWN_COMPANY_ALIASES:
        if name.lower().replace(" ", "") in lowered:
            return name

    match = LEADING_COMPANY.match(cleaned)
    if match:
        candidate = match.group(1).strip(" '\"“”‘’")
        if candidate not in MEDIA_NAMES and not is_internal_company(candidate) and len(candidate) <= 18:
            return candidate
    return None


def calculate_score(category: str, urgency: str, competitor: str | None, age_days: int, source_level: str) -> int:
    score = BASE_SCORE.get(category, 10) + URGENCY_BONUS.get(urgency, 0)
    if competitor:
        score += 30
    if age_days <= 1:
        score += 15
    elif age_days <= 3:
        score += 10
    elif age_days <= 7:
        score += 5
    if source_level == "A":
        score += 20
    elif source_level == "B":
        score += 8
    return score


def priority_from_score(score: int, category: str, urgency: str, company: str | None = None) -> bool:
    if not company or is_public_entity(company):
        return False
    return category in {"outflow", "leader"} and (urgency == "high" or score >= 100)
