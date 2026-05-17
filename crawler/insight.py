from __future__ import annotations

CAT_LABEL = {"outflow": "인재 유출", "leader": "리더 이탈", "hiring": "채용 확대", "foreign": "해외/외국계", "hr": "HR NEWS"}

SIGNAL_PREFIX = {
    "outflow": "인재 유출 가능성",
    "leader": "리더 이동 신호",
    "hiring": "공격적 채용 신호",
    "foreign": "글로벌 채용시장 영향",
    "hr": "HR/노무 변화"
}

INSIGHT = {
    "outflow": "경영난·구조조정·인력 효율화 신호는 핵심 인재의 이직 탐색 가능성을 높일 수 있습니다. 해당 기업의 직군별 핵심 인력을 우선 매핑하세요.",
    "leader": "대표·임원급 이동은 후속 조직개편과 연쇄 이탈의 선행 신호가 될 수 있습니다. 리더 직속 조직과 핵심 실무 리더를 함께 추적하세요.",
    "hiring": "공격적으로 채용을 확대하는 기업은 후보자 경쟁 강도를 높입니다. 동일 직군의 보상·메시지·접촉 속도를 점검하세요.",
    "foreign": "해외 대형 해고·채용·M&A는 국내 외국계와 유사 직군 이동성에 영향을 줄 수 있습니다. 한국 지사 및 관련 직군 변화를 모니터링하세요.",
    "hr": "인사·노무 제도 변화는 채용 메시지와 근무조건 커뮤니케이션에 영향을 줍니다. 내부 채용 안내와 후보자 FAQ를 업데이트하세요."
}

ACTION = {
    "outflow": "LinkedIn·리멤버에서 해당 기업의 개발, 데이터, 커머스, 플랫폼 운영, 영업 리더 후보군을 우선 확인하고 24~48시간 내 접촉 대상을 선별하세요.",
    "leader": "기사에 언급된 리더의 이전 조직과 이동 회사, 직속 팀을 follow-up하고 후속 이탈 가능성이 있는 핵심 인재 리스트를 만드세요.",
    "hiring": "해당 기업이 채용 중인 직군과 우리 채용 포지션의 후보자 풀이 겹치는지 확인하고, 경쟁 메시지를 보강하세요.",
    "foreign": "국내 영향 가능성이 있는 직군을 분리해 모니터링하고, 외국계 출신 후보자에게 적용할 메시지를 준비하세요.",
    "hr": "법령·제도 변경 내용을 채용 운영 체크리스트에 반영하고, 후보자 문의가 예상되는 항목을 사전에 정리하세요."
}

SUBCATEGORY = {
    "구조조정": "구조조정",
    "희망퇴직": "희망퇴직",
    "권고사직": "권고사직",
    "유동성 위기": "경영리스크",
    "생존 경고등": "투자/생존 리스크",
    "투자 유치 실패": "투자실패",
    "대표 사임": "리더 사임",
    "CEO 교체": "리더 교체",
    "신임 대표": "리더 선임",
    "대규모 채용": "공격적 채용",
    "인재 확보": "인재 확보",
    "AI 인재": "AI 인재 경쟁",
    "파업": "노무 리스크",
    "근로기준법 개정": "제도 변화",
}


def subcategory_for(keyword: str | None, category: str) -> str:
    if keyword:
        for needle, label in SUBCATEGORY.items():
            if needle in keyword:
                return label
    return CAT_LABEL.get(category, category)


def make_card(raw: dict, report_date: str) -> dict:
    category = raw["category"]
    title = raw["title"]
    company = raw.get("competitor") or raw.get("source") or "시장 동향"
    keyword = raw.get("keyword") or CAT_LABEL.get(category, "채용 인텔리전스")
    published_date = raw.get("published_date") or report_date
    source_name = raw.get("source") or "뉴스"
    level = raw.get("level", "B")
    urgency = raw.get("urgency", "low")
    score = raw.get("score", 0)
    subcategory = subcategory_for(keyword, category)
    action = ACTION.get(category, "관련 기업과 직군을 모니터링하세요.")
    return {
        "id": raw["id"],
        "date": published_date,
        "collected_date": report_date,
        "time": raw.get("published_time", "09:00"),
        "cat": category,
        "priority": raw.get("priority", False),
        "urgency": urgency,
        "company": company,
        "signal": f"{SIGNAL_PREFIX.get(category, '채용 신호')} · {keyword}",
        "level": level,
        "title": title[:90],
        "body": raw.get("description") or f"{source_name}에서 {published_date}에 보도된 '{title}' 기사입니다. 실제 기사 URL이 확인된 정보만 카드로 반영했습니다.",
        "insight": INSIGHT.get(category, "채용 시장 변화를 모니터링할 필요가 있습니다."),
        "action": action,
        "contact_strategy": action,
        "subcategory": subcategory,
        "tags": [CAT_LABEL.get(category, category), subcategory, keyword, f"score:{score}"],
        "sources": [{
            "name": source_name,
            "url": raw["url"],
            "level": level,
            "verified": raw.get("verified", True),
            "verify_note": raw.get("verify_note", ""),
            "http_status": raw.get("http_status"),
            "original_url": raw.get("original_url", raw["url"]),
        }]
    }
