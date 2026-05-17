from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

ALLOWED_CATEGORIES = {"outflow", "leader", "hiring", "foreign", "hr"}
ALLOWED_URGENCY = {"high", "mid", "low"}
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_TIMEOUT = int(os.environ.get("GEMINI_TIMEOUT", "45"))

SYSTEM_PROMPT = """
당신은 커넥트웨이브 채용 인텔리전스의 품질 검수자이자 채용 리서치 분석가입니다.

핵심 원칙:
- 이미 크롤링된 실제 기사 카드만 검수합니다.
- 새로운 기사, 새로운 URL, 출처에 없는 사실을 만들지 않습니다.
- source_url은 절대 수정하지 않습니다.
- 기사 제목, 기존 요약, 출처명, URL만 근거로 판단합니다.
- 확실하지 않은 사실은 단정하지 말고 보수적으로 작성합니다.
- 채용담당자가 바로 행동할 수 있게 실용적인 인사이트와 액션을 작성합니다.

커넥트웨이브 그룹사, 즉 자사 관련 내용은 제외해야 합니다:
- 커넥트웨이브, 다나와, 에누리, 에누리닷컴, 메이크샵, 플레이오토, 몰테일, 스윗트래커

카테고리 정의:
- outflow: 인재 유출 가능성. 구조조정, 희망퇴직, 권고사직, 감원, 인력 효율화, 경영난, 매각, 투자 실패, 유동성 위기, 법정관리, 사업 철수
- leader: 리더 이탈/이동. 대표, 창업자, CTO, CPO, CISO, CFO, CHRO 등 주요 리더의 사임, 선임, 합류, 이직
- hiring: 채용 확대. 대규모 채용, 채용 드라이브, AI/개발/커머스 인재 확보, 조직 확대
- foreign: 해외/외국계. 글로벌 해고, 채용, M&A, 한국 채용시장에 영향을 줄 수 있는 해외 빅테크/외국계 이슈
- hr: HR NEWS. 노동법, 노무, 파업, 임금, 육아휴직, 근로시간, HR 트렌드, 채용 제도 변화

검수 규칙:
- 언론사명(약업신문, 전자신문, 서울경제, 기계신문, 뉴스핌 등)이 company로 들어가 있으면 실제 기업명을 찾아 교정합니다.
- 실제 기업명을 확정할 수 없으면 company="시장 동향"으로 둡니다.
- 채용/인재/조직/리더/HR 관점의 가치가 낮으면 keep=false로 제외합니다.
- priority=true는 채용팀이 즉시 봐야 할 인재유출 또는 리더이탈 카드에만 사용합니다.
- HR NEWS와 일반 채용확대는 보통 priority=false입니다. 단, 파업/법령 변화처럼 긴급성이 높으면 urgency를 높일 수 있습니다.

상세 페이지 작성 지침:
- body: 실제 기사 기반 이슈 요약입니다. 무엇이 발생했는지, 어떤 기업/조직 이슈인지 160~220자 내외로 씁니다.
- insight: 채용담당자 관점의 해석입니다. 이 이슈가 후보자 시장, 인재 이탈, 경쟁 채용, 컨택 타이밍에 어떤 의미인지 100~160자 내외로 씁니다.
- action: 추천 액션입니다. 어떤 직군/대상자를 어디서 찾고, 어떤 메시지 또는 타이밍으로 접근할지 100~160자 내외로 구체적으로 씁니다.
- contact_strategy: action과 유사하지만 더 짧은 실행 문장으로 씁니다. 80~140자 내외입니다.

응답은 JSON 배열만 출력하세요. 마크다운 금지.
[
  {
    "id": "원본 id",
    "keep": true,
    "company": "교정 기업명 또는 시장 동향",
    "cat": "outflow|leader|hiring|foreign|hr",
    "urgency": "high|mid|low",
    "priority": true,
    "signal": "짧은 신호 요약",
    "body": "실제 기사 기반 이슈 요약",
    "insight": "채용 담당자 인사이트",
    "action": "추천 액션",
    "contact_strategy": "짧은 컨택 전략",
    "tags": ["태그1", "태그2"],
    "reason": "검수 및 보정 이유"
  }
]
"""


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _gemini_url(api_key: str) -> str:
    return (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{GEMINI_MODEL}:generateContent?key={api_key}"
    )


def _limit(value: Any, max_len: int) -> str:
    return str(value or "").strip()[:max_len]


def _request_audit(cards: list[dict[str, Any]], api_key: str) -> list[dict[str, Any]]:
    compact_cards = []
    for card in cards:
        source = (card.get("sources") or [{}])[0]
        compact_cards.append({
            "id": card.get("id"),
            "company": card.get("company"),
            "cat": card.get("cat"),
            "urgency": card.get("urgency"),
            "priority": card.get("priority"),
            "title": card.get("title"),
            "body": card.get("body"),
            "insight": card.get("insight"),
            "action": card.get("action"),
            "signal": card.get("signal"),
            "source_name": source.get("name"),
            "source_url": source.get("url"),
            "tags": card.get("tags", []),
        })

    prompt = (
        SYSTEM_PROMPT
        + "\n\n[검수 대상 카드]\n"
        + json.dumps(compact_cards, ensure_ascii=False, indent=2)
    )
    response = requests.post(
        _gemini_url(api_key),
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.15,
                "maxOutputTokens": 8000,
                "responseMimeType": "application/json",
            },
        },
        timeout=GEMINI_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    parsed = json.loads(_strip_json_fence(text))
    return parsed if isinstance(parsed, list) else []


def _apply_audit(cards: list[dict[str, Any]], audit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {row.get("id"): row for row in audit_rows if row.get("id")}
    audited = []
    for card in cards:
        row = by_id.get(card.get("id"))
        if not row:
            card["ai_audit"] = {"status": "missing"}
            audited.append(card)
            continue
        if row.get("keep") is False:
            continue

        cat = row.get("cat")
        urgency = row.get("urgency")
        if cat in ALLOWED_CATEGORIES:
            card["cat"] = cat
        if urgency in ALLOWED_URGENCY:
            card["urgency"] = urgency

        company = _limit(row.get("company"), 40)
        if company:
            card["company"] = company
        if isinstance(row.get("priority"), bool):
            card["priority"] = row["priority"]
        if row.get("signal"):
            card["signal"] = _limit(row["signal"], 80)
        if row.get("body"):
            card["body"] = _limit(row["body"], 260)
        if row.get("insight"):
            card["insight"] = _limit(row["insight"], 220)
        if row.get("action"):
            card["action"] = _limit(row["action"], 220)
        if row.get("contact_strategy"):
            card["contact_strategy"] = _limit(row["contact_strategy"], 180)

        if isinstance(row.get("tags"), list):
            tags = [_limit(tag, 30) for tag in row["tags"] if str(tag).strip()]
            card["tags"] = tags[:6] or card.get("tags", [])

        card["ai_audit"] = {
            "status": "passed",
            "reason": _limit(row.get("reason"), 180),
        }
        audited.append(card)
    return audited


def audit_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or not cards:
        for card in cards:
            card["ai_audit"] = {"status": "skipped", "reason": "GEMINI_API_KEY not set"}
        return cards

    try:
        audit_rows = _request_audit(cards, api_key)
        audited = _apply_audit(cards, audit_rows)
        return audited or cards
    except Exception as exc:
        for card in cards:
            card["ai_audit"] = {"status": "failed", "reason": str(exc)[:180]}
        return cards
