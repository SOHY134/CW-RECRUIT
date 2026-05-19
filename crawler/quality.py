from __future__ import annotations

import html
import re
from copy import deepcopy
from urllib.parse import urlparse

from rapidfuzz import fuzz

from crawler.classifier import detect_company, detect_competitor, strip_source_suffix

MEDIA_SUFFIX = re.compile(
    r"\s[-–—]\s[가-힣A-Za-z0-9 .·&]{2,24}"
    r"(뉴스|경제|신문|일보|방송|저널|투데이|데일리|타임즈|미디어|News|Daily|Times)?\s*$",
    re.IGNORECASE,
)
HTML_TAG = re.compile(r"<[^>]+>")
WHITESPACE = re.compile(r"\s+")
LEADING_BRAND = re.compile(r"^[가-힣A-Za-z0-9 .·&()]+?\s*[,，:：·]\s*")
SYMBOL_NOISE = re.compile(
    "[\U0001f300-\U0001faff\U00002700-\U000027bf\U00002600-\U000026ff]"
)

MEDIA_NAMES = {
    "전자신문", "경향신문", "서울경제", "서울경제TV", "기계신문", "뉴스핌", "굿모닝경제",
    "뉴닉", "이데일리", "IT조선", "약업신문", "직썰", "연합뉴스", "한국경제", "매일경제",
    "조선비즈", "ZDNet Korea", "블로터", "딜사이트", "뉴스1", "머니투데이",
}

COMPANY_ALIASES = {
    "DH": "딜리버리히어로",
    "Delivery Hero": "딜리버리히어로",
    "배민": "배달의민족",
    "우아한형제들": "배달의민족",
    "CFS": "쿠팡풀필먼트서비스",
    "쿠팡풀필먼트서비스": "쿠팡",
    "Meta": "메타",
    "메타": "메타",
}

CAT_LABEL = {
    "outflow": "인재 유출",
    "leader": "리더 이탈",
    "hiring": "채용 확대",
    "foreign": "해외/외국계",
    "hr": "HR NEWS",
}

ACTION_BY_CAT = {
    "outflow": "{company} 재직/퇴직 예정자를 리멤버·LinkedIn에서 직군별로 매핑하고, 개발·PM·커머스 운영·영업 핵심 후보자에게 24~48시간 내 1차 접촉하세요.",
    "leader": "{company}의 리더십 변동 후속 조직개편 가능성을 보고, 해당 리더 직속 조직과 핵심 실무 리더의 이동 경로를 추적하세요.",
    "hiring": "{company}가 선점하려는 직군을 확인하고, 우리 채용 포지션과 겹치는 후보자군의 제안 메시지와 보상 경쟁력을 점검하세요.",
    "foreign": "국내 유사 직군에 미칠 영향을 분리해 보고, 외국계·글로벌 플랫폼 출신 후보자 풀을 모니터링하세요.",
    "hr": "제도 변화가 채용 운영, 근로조건 안내, 후보자 FAQ에 미칠 영향을 정리해 내부 채용 커뮤니케이션에 반영하세요.",
}


def clean_text(value: str) -> str:
    text = html.unescape(str(value or ""))
    text = HTML_TAG.sub(" ", text)
    text = re.sub(r"<[^>\s]*(?:\s|$)", " ", text)
    text = SYMBOL_NOISE.sub("", text)
    return WHITESPACE.sub(" ", text).strip()


def strip_media_names(text: str) -> str:
    cleaned = clean_text(text)
    for name in MEDIA_NAMES:
        cleaned = re.sub(rf"\s[-–—]\s{re.escape(name)}\s*$", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(rf"^{re.escape(name)}\s*[,，:：·]\s*", "", cleaned, flags=re.IGNORECASE)
    return WHITESPACE.sub(" ", cleaned).strip()


def source_names(card: dict) -> list[str]:
    return [str(src.get("name", "")).strip() for src in card.get("sources", []) if src.get("name")]


def canonical_company(value: str | None) -> str:
    name = clean_text(value or "")
    name = MEDIA_SUFFIX.sub("", name).strip(" -–—·|")
    for alias, canonical in COMPANY_ALIASES.items():
        if alias.lower().replace(" ", "") == name.lower().replace(" ", ""):
            return canonical
    if name in MEDIA_NAMES or not name:
        return ""
    return name[:40]


def clean_title(title: str, company: str = "", sources: list[dict] | None = None) -> str:
    text = strip_source_suffix(strip_media_names(title))
    for src in sources or []:
        name = clean_text(src.get("name", ""))
        if name:
            text = re.sub(rf"\s[-–—]\s{re.escape(name)}\s*$", "", text, flags=re.IGNORECASE).strip()
    text = strip_media_names(MEDIA_SUFFIX.sub("", text).strip())
    comp = canonical_company(company)
    if comp:
        text = re.sub(rf"^{re.escape(comp)}\s*[,，:：·]\s*", "", text).strip()
    text = LEADING_BRAND.sub(lambda m: "" if len(m.group(0)) < 24 else m.group(0), text).strip()
    return text[:86]


def infer_company(card: dict) -> str:
    joined = " ".join([
        clean_text(card.get("company", "")),
        clean_text(card.get("title", "")),
        clean_text(card.get("body", "")),
        clean_text(card.get("signal", "")),
    ])
    explicit = canonical_company(card.get("company"))
    if explicit:
        return explicit
    for alias, canonical in COMPANY_ALIASES.items():
        if alias.lower().replace(" ", "") in joined.lower().replace(" ", ""):
            return canonical
    detected = detect_competitor(joined) or detect_company(joined)
    detected = canonical_company(detected)
    return detected or "시장 동향"


def compact_summary(card: dict) -> str:
    company = infer_company(card)
    title = clean_title(card.get("title", ""), company, card.get("sources", []))
    signal = clean_text(card.get("signal", ""))
    keyword = signal.split("·")[-1].strip() if "·" in signal else signal
    if card.get("cat") == "outflow":
        lead = f"{company}에서 {keyword or '인력 변동'} 이슈가 포착됐습니다."
        tail = "핵심 인재의 이직 탐색 가능성을 열어두고 관련 직군을 확인할 필요가 있습니다."
    elif card.get("cat") == "leader":
        lead = f"{company}의 리더십 변동 신호가 확인됐습니다."
        tail = "후속 조직개편이나 직속 조직의 연쇄 이동 가능성을 함께 추적해야 합니다."
    elif card.get("cat") == "hiring":
        lead = f"{company}의 채용 확대 움직임이 확인됐습니다."
        tail = "동일 후보자 풀에서 경쟁이 커질 수 있어 채용 메시지와 접촉 속도 점검이 필요합니다."
    elif card.get("cat") == "foreign":
        lead = "해외·외국계 채용시장 변화가 확인됐습니다."
        tail = "국내 유사 직군과 외국계 후보자 수급에 미칠 영향을 모니터링하세요."
    else:
        lead = "HR·노무 관련 변화가 확인됐습니다."
        tail = "채용 운영과 후보자 안내에 반영할 실무 체크포인트를 정리하세요."
    return f"{lead} {title}. {tail}"[:230]


def insight_for(card: dict) -> str:
    company = infer_company(card)
    cat = card.get("cat", "hr")
    if cat == "outflow":
        return f"{company}의 구조조정·매각·실적 악화 신호는 핵심 인재가 이직 탐색을 시작할 가능성을 높입니다. 동일 업권의 개발, PM, 커머스 운영 인재를 우선 추적하세요."
    if cat == "leader":
        return f"{company}의 대표·임원급 이동은 후속 조직개편과 팀 단위 이탈의 선행 신호가 될 수 있습니다. 리더 직속 조직의 핵심 실무자를 함께 확인하세요."
    if cat == "hiring":
        return f"{company}의 채용 확대는 동일 후보자 풀 경쟁을 키울 수 있습니다. 우리 포지션과 겹치는 직군의 제안 속도와 메시지를 점검하세요."
    if cat == "foreign":
        return "글로벌 감원·M&A·채용 변화는 국내 외국계 및 유사 직군 수급에 후행 영향을 줄 수 있습니다. 한국 시장 영향 가능성을 별도로 모니터링하세요."
    return "HR·노무·제도 변화는 채용 조건 안내와 후보자 커뮤니케이션에 직접 영향을 줄 수 있습니다. 실무 적용 항목을 빠르게 정리하세요."


def action_for(card: dict) -> str:
    company = infer_company(card)
    template = ACTION_BY_CAT.get(card.get("cat"), ACTION_BY_CAT["hr"])
    return template.format(company=company)[:220]


def quality_key(card: dict) -> str:
    company = infer_company(card)
    title = clean_title(card.get("title", ""), company, card.get("sources", []))
    tokens = re.sub(r"[^0-9A-Za-z가-힣]+", " ", title).lower()
    return f"{card.get('cat')}|{company}|{tokens[:48]}"


def is_meaningful(card: dict) -> bool:
    title = clean_title(card.get("title", ""), card.get("company", ""), card.get("sources", []))
    if len(title) < 8:
        return False
    if not any(src.get("url") for src in card.get("sources", [])):
        return False
    if infer_company(card) == "시장 동향" and card.get("cat") in {"outflow", "leader", "hiring"}:
        return False
    return True


def normalize_card(card: dict) -> dict:
    out = deepcopy(card)
    out.pop("ai" + "_audit", None)
    out["company"] = infer_company(out)
    out["title"] = clean_title(out.get("title", ""), out["company"], out.get("sources", []))
    out["body"] = compact_summary(out)
    out["insight"] = insight_for(out)
    out["action"] = action_for(out)
    out["contact_strategy"] = out["action"]
    out["signal"] = clean_text(out.get("signal", "")).replace("시장 동향 · ", "")[:90]
    out["tags"] = [clean_text(tag).replace("#", "")[:24] for tag in out.get("tags", []) if clean_text(tag)]
    out["tags"] = list(dict.fromkeys([tag for tag in out["tags"] if tag not in MEDIA_NAMES]))[:5]
    for src in out.get("sources", []):
        src["name"] = clean_text(src.get("name", "")) or host_label(src.get("url", ""))
    return out


def host_label(url: str) -> str:
    host = urlparse(url or "").netloc.replace("www.", "")
    return host or "출처"


def dedupe_cards(cards: list[dict], limit: int | None = None) -> list[dict]:
    selected: list[dict] = []
    seen_urls: set[str] = set()
    seen_comp_cat: set[tuple[str, str]] = set()
    seen_titles: list[str] = []
    for raw in cards:
        card = normalize_card(raw)
        if not is_meaningful(card):
            continue
        urls = {src.get("url") for src in card.get("sources", []) if src.get("url")}
        title = card.get("title", "")
        comp_cat = (card.get("company", ""), card.get("cat", ""))
        if urls & seen_urls:
            continue
        if comp_cat in seen_comp_cat and card.get("cat") in {"outflow", "leader", "hiring"}:
            continue
        if any(fuzz.token_set_ratio(title, old) >= 88 for old in seen_titles):
            continue
        selected.append(card)
        seen_urls.update(urls)
        seen_comp_cat.add(comp_cat)
        seen_titles.append(title)
        if limit and len(selected) >= limit:
            break
    return selected
