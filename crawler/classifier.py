from __future__ import annotations

from crawler.competitors import ALL_COMPETITORS, CW_INTERNAL
from crawler.keywords import CATEGORY_KEYWORDS

BASE_SCORE = {"outflow": 80, "leader": 75, "hiring": 45, "foreign": 35, "hr": 25}
URGENCY_BONUS = {"high": 25, "mid": 12, "low": 4}


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


def priority_from_score(score: int, category: str, urgency: str) -> bool:
    return category in {"outflow", "leader"} and (urgency == "high" or score >= 100)
