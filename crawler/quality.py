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
    "hr": "노사·노무·제도 변화가 조직 안정성과 근로조건 커뮤니케이션에 미칠 영향을 정리하고 관련 실무 리스크를 점검하세요.",
}

EVENT_RULES = [
    {
        "needles": ["희망퇴직", "권고사직", "구조조정", "감원", "인력 감축", "정리해고"],
        "event": "{company} 인력 조정",
        "subtitle": "핵심 인재 이동 가능성 확대",
        "summary": "{company}에서 인력 조정 신호가 확인됐습니다. 해당 이슈는 재직자의 이직 탐색과 핵심 직군 이동 가능성으로 직접 이어질 수 있습니다.",
        "insight": "{company}의 인력 조정은 개발, PM, 운영, 영업 등 핵심 실무자의 시장 유입 가능성을 높입니다. 유사 업권 후보자 풀을 빠르게 갱신하세요.",
        "action": "{company} 재직자와 최근 퇴직자를 직군별로 매핑하고, 리멤버·LinkedIn에서 핵심 실무자 중심으로 24~48시간 내 접촉 우선순위를 정하세요.",
    },
    {
        "needles": ["매각", "인수", "M&A", "인수합병"],
        "event": "{company} 매각 이슈",
        "subtitle": "조직 불확실성에 따른 이탈 리스크 주시",
        "summary": "{company}에서 매각·인수 관련 이슈가 확인됐습니다. 소유구조 변화 가능성은 조직 불확실성을 키워 핵심 인재 이탈 리스크로 이어질 수 있습니다.",
        "insight": "매각 이슈는 보상, 조직개편, 리더십 변화 우려를 만들 수 있습니다. {company}의 전략, 제품, 개발, 운영 리더급 움직임을 함께 봐야 합니다.",
        "action": "{company} 핵심 조직의 리더와 시니어 실무자를 우선 모니터링하고, 조직 안정성 우려에 반응할 수 있는 후보자군을 선별하세요.",
    },
    {
        "needles": ["회생", "법정관리", "워크아웃", "유동성", "경영난", "생존 경고등", "실적 부진", "적자"],
        "event": "{company} 경영 리스크",
        "subtitle": "조직 안정성 저하와 인재 이탈 가능성 점검",
        "summary": "{company}의 경영 리스크가 확인됐습니다. 재무·사업 안정성 저하는 핵심 인재의 이탈 검토와 조직 불안정으로 이어질 수 있습니다.",
        "insight": "{company}의 경영 리스크는 단기적으로 핵심 인재의 외부 기회 탐색을 자극할 수 있습니다. 직군별 시장 유입 가능성을 선제적으로 확인하세요.",
        "action": "{company}의 개발, 커머스 운영, 영업, 재무·전략 직군을 우선 분류하고 이직 의향이 생길 가능성이 높은 후보자를 추적하세요.",
    },
    {
        "needles": ["CEO", "대표", "대표이사", "CTO", "CPO", "CISO", "CFO", "CHRO", "창업자", "공동 창업자", "공동창업자", "임원"],
        "event": "{company} 리더십 변화",
        "subtitle": "후속 조직개편과 직속 조직 이동 주시",
        "summary": "{company}의 대표·임원급 리더십 변화가 확인됐습니다. 리더 이동은 후속 조직개편과 직속 조직의 연쇄 이동 가능성으로 이어질 수 있습니다.",
        "insight": "{company} 리더십 변화는 팀 방향성, 의사결정 구조, 핵심 인재 유지에 영향을 줄 수 있습니다. 해당 리더 직속 조직을 별도로 추적하세요.",
        "action": "{company}의 리더 직속 조직, 전 소속 팀, 후임 체계 변화를 확인하고 핵심 실무 리더의 이동 가능성을 후보자 맵에 반영하세요.",
    },
    {
        "needles": ["대규모 채용", "채용 확대", "채용 드라이브", "인재 확보", "공채", "세 자릿수 채용", "두 자릿수 채용"],
        "event": "{company} 채용 확대",
        "subtitle": "동일 직군 후보자 확보 경쟁 심화",
        "summary": "{company}의 채용 확대 움직임이 확인됐습니다. 이는 동일 직군 후보자 풀에서 제안 경쟁과 응답 속도 경쟁이 커질 수 있음을 뜻합니다.",
        "insight": "{company}의 공격적 채용은 후보자의 기대 보상과 선택지를 넓힐 수 있습니다. 우리 채용 포지션과 겹치는 직군을 먼저 확인하세요.",
        "action": "{company} 채용 직군과 우리 포지션의 겹침을 확인하고, JD·보상·제안 메시지·컨택 속도를 경쟁 기준으로 재점검하세요.",
    },
    {
        "needles": ["파업", "노사갈등", "임금협상", "단체교섭", "긴급조정"],
        "event": "{company} 노사갈등",
        "subtitle": "조직 안정성 및 핵심 인력 이탈 가능성 점검",
        "summary": "{company}의 노사갈등 이슈가 확인됐습니다. 이 이슈는 채용 운영 자체보다 조직 안정성, 직원 정서, 핵심 인력 유지 리스크와 직접 연결됩니다.",
        "insight": "{company}의 노사갈등은 구성원의 조직 신뢰와 잔류 의사에 영향을 줄 수 있습니다. 관련 사업부의 핵심 인력 이동 가능성을 관찰하세요.",
        "action": "{company} 관련 직군의 이직 신호를 모니터링하고, 노사 이슈에 민감한 핵심 인력이 외부 기회를 탐색하는지 확인하세요.",
    },
    {
        "needles": ["육아휴직", "최저임금", "근로기준법", "노동법", "포괄임금", "근로자의 날", "노동절", "공휴일", "주4일제"],
        "event": "HR 제도 변화",
        "subtitle": "근로조건 커뮤니케이션 업데이트 필요",
        "summary": "HR·노무 제도 변화가 확인됐습니다. 이 이슈는 채용 운영 전반보다 후보자에게 안내할 근로조건과 내부 제도 설명의 정확성에 직접 영향을 줍니다.",
        "insight": "제도 변화는 후보자가 근무조건을 판단하는 기준에 영향을 줄 수 있습니다. 채용 공고, 오퍼 안내, 후보자 FAQ의 표현을 점검하세요.",
        "action": "변경된 제도 내용을 채용 공고와 오퍼 커뮤니케이션에 반영하고, 후보자 문의가 예상되는 항목을 FAQ로 정리하세요.",
    },
    {
        "needles": ["layoff", "job cuts", "workforce reduction", "hiring freeze"],
        "event": "{company} 글로벌 인력 조정",
        "subtitle": "국내 유사 직군 영향 모니터링",
        "summary": "{company}의 글로벌 인력 조정 이슈가 확인됐습니다. 국내 직접 영향은 별도 확인이 필요하지만 유사 직군 수급 변화 가능성은 모니터링할 만합니다.",
        "insight": "글로벌 인력 조정은 외국계와 플랫폼 직군의 후보자 이동성을 높일 수 있습니다. 국내 지사와 유사 직군 채용 흐름을 함께 확인하세요.",
        "action": "국내 지사, 외국계 출신 후보자, 글로벌 플랫폼 경험자의 이동 신호를 분리해 추적하고 관련 포지션 후보자 풀을 갱신하세요.",
    },
]


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


def context_text(card: dict) -> str:
    return " ".join([
        clean_text(card.get("company", "")),
        clean_text(card.get("title", "")),
        clean_text(card.get("body", "")),
        clean_text(card.get("signal", "")),
        " ".join(clean_text(tag) for tag in card.get("tags", [])),
    ]).lower()


def direct_rule(card: dict) -> dict:
    company = infer_company(card)
    text = context_text(card)
    for rule in EVENT_RULES:
        if any(needle.lower() in text for needle in rule["needles"]):
            return rule
    cat = card.get("cat")
    if cat == "leader":
        return EVENT_RULES[3]
    if cat == "hiring":
        return EVENT_RULES[4]
    if cat == "foreign":
        return EVENT_RULES[7]
    if cat == "hr":
        return EVENT_RULES[6]
    return EVENT_RULES[0]


def render_template(template: str, company: str) -> str:
    if company == "시장 동향":
        return template.replace("{company} ", "").replace("{company}", "시장")
    return template.format(company=company)


def intelligence_title(card: dict) -> str:
    company = infer_company(card)
    rule = direct_rule(card)
    main = render_template(rule["event"], company)
    sub = render_template(rule["subtitle"], company)
    return f"{main} - {sub}"[:86]


def compact_summary(card: dict) -> str:
    company = infer_company(card)
    rule = direct_rule(card)
    original = clean_title(card.get("title", ""), company, card.get("sources", []))
    summary = render_template(rule["summary"], company)
    if original:
        summary = f"{summary} 원문 이슈: {original}."
    return summary[:230]


def insight_for(card: dict) -> str:
    company = infer_company(card)
    return render_template(direct_rule(card)["insight"], company)[:220]


def action_for(card: dict) -> str:
    company = infer_company(card)
    return render_template(direct_rule(card)["action"], company)[:220]


def quality_key(card: dict) -> str:
    company = infer_company(card)
    title = clean_title(card.get("title", ""), company, card.get("sources", []))
    tokens = re.sub(r"[^0-9A-Za-z가-힣]+", " ", title).lower()
    return f"{card.get('cat')}|{company}|{tokens[:48]}"


def event_key(card: dict) -> str:
    company = infer_company(card)
    rule = direct_rule(card)
    event = render_template(rule["event"], company)
    return f"{card.get('cat')}|{company}|{event}"


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
    out["raw_title"] = clean_title(out.get("raw_title") or out.get("title", ""), out["company"], out.get("sources", []))
    out["title"] = intelligence_title(out)
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
    seen_events: set[str] = set()
    seen_titles: list[str] = []
    for raw in cards:
        card = normalize_card(raw)
        if not is_meaningful(card):
            continue
        urls = {src.get("url") for src in card.get("sources", []) if src.get("url")}
        title = card.get("title", "")
        event = event_key(card)
        if urls & seen_urls:
            continue
        if event in seen_events:
            continue
        if any(fuzz.token_set_ratio(title, old) >= 88 for old in seen_titles):
            continue
        selected.append(card)
        seen_urls.update(urls)
        seen_events.add(event)
        seen_titles.append(title)
        if limit and len(selected) >= limit:
            break
    return selected
