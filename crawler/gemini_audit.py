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
당신은 커넥트웨이브 채용 인텔리전스 품질 검수자입니다.

역할:
- 이미 수집된 실제 기사 카드만 검수합니다.
- 새로운 기사, URL, 사실을 만들지 않습니다.
- source.url은 절대 수정하지 않습니다.
- 기사 제목/본문/출처만 근거로 company, category, urgency, priority, signal, tags를 보정합니다.
- 관련성이 낮거나 채용 인텔리전스 가치가 낮으면 keep=false로 제외합니다.

카테고리:
- outflow: 인재 유출, 구조조정, 희망퇴직, 감원, 경영난, 매각, 투자 실패, 유동성 위기
- leader: 대표/임원/창업자/CTO/CPO/CISO/CFO/CHRO 이동, 사임, 선임, 합류
- hiring: 대규모 채용, 채용 확대, 인재 확보
- foreign: 해외/외국계 대형 감원, 채용, M&A, 한국 시장 영향 가능성
- hr: 인사/노무/노동법/파업/제도 변화

중요 검수 규칙:
- company가 언론사명(예: 약업신문, 전자신문, 서울경제, 기계신문, 뉴스핌)이면 제목에서 실제 기업명을 찾아 교정합니다.
- 실제 기업명을 확정할 수 없으면 company="시장 동향"으로 둡니다.
- 기사 내용이 채용, 인재 이동, 조직 변화, HR/노무와 무관하면 keep=false입니다.
- 커넥트웨이브 그룹사(다나와, 에누리, 에누리닷컴, 메이크샵, 플레이오토, 몰테일, 스윗트래커)는 keep=false입니다.
- priority=true는 인재유출/리더이탈 중 컨택 가치가 높은 경우에만 사용합니다.

응답은 JSON 배열만 출력하세요.
[
  {
    "id": "원본 id",
    "keep": true,
    "company": "교정 기업명",
    "cat": "outflow|leader|hiring|foreign|hr",
    "urgency": "high|mid|low",
    "priority": true,
    "signal": "짧은 신호 요약",
    "tags": ["태그1", "태그2"],
    "reason": "검수 이유"
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


def _request_audit(cards: list[dict[str, Any]], api_key: str) -> list[dict[str, Any]]:
    compact_cards = []
    for card in cards:
        compact_cards.append({
            "id": card.get("id"),
            "company": card.get("company"),
            "cat": card.get("cat"),
            "urgency": card.get("urgency"),
            "priority": card.get("priority"),
            "title": card.get("title"),
            "body": card.get("body"),
            "signal": card.get("signal"),
            "source_name": (card.get("sources") or [{}])[0].get("name"),
            "source_url": (card.get("sources") or [{}])[0].get("url"),
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
                "temperature": 0.1,
                "maxOutputTokens": 4000,
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

        company = str(row.get("company") or "").strip()
        if company:
            card["company"] = company[:40]
        if isinstance(row.get("priority"), bool):
            card["priority"] = row["priority"]
        if row.get("signal"):
            card["signal"] = str(row["signal"])[:80]
        if isinstance(row.get("tags"), list):
            tags = [str(tag)[:30] for tag in row["tags"] if str(tag).strip()]
            card["tags"] = tags[:6] or card.get("tags", [])

        card["ai_audit"] = {
            "status": "passed",
            "reason": str(row.get("reason") or "")[:180],
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
