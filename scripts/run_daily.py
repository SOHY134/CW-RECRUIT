from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crawler.collect_news import collect_cards  # noqa: E402

KST = ZoneInfo("Asia/Seoul")
HISTORY_LIMIT = int(os.environ.get("HISTORY_LIMIT", "90"))
MAX_AGE_DAYS = int(os.environ.get("MAX_AGE_DAYS", "7"))
MAX_ITEMS = int(os.environ.get("MAX_ITEMS", "6"))
MIN_DISPLAY_ITEMS = int(os.environ.get("MIN_DISPLAY_ITEMS", "3"))


def read_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def item_date(item: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(item.get("date", "")).replace(tzinfo=KST)
    except Exception:
        return None


def fill_with_recent_verified_items(report: dict, history: list[dict], today: str) -> dict:
    items = list(report.get("items", []))
    if len(items) >= MIN_DISPLAY_ITEMS:
        report["items"] = items[:MAX_ITEMS]
        return report

    cutoff = datetime.now(tz=KST) - timedelta(days=MAX_AGE_DAYS)
    seen_urls = {source.get("url") for item in items for source in item.get("sources", [])}
    seen_ids = {item.get("id") for item in items}

    for old_report in history:
        for old_item in old_report.get("items", []):
            published = item_date(old_item)
            if not published or published < cutoff:
                continue
            urls = [source.get("url") for source in old_item.get("sources", []) if source.get("url")]
            if not urls or old_item.get("id") in seen_ids or any(url in seen_urls for url in urls):
                continue
            carry = dict(old_item)
            carry["collected_date"] = today
            carry["id"] = f"{today.replace('-', '')}-carry-{len(items)+1}-{old_item.get('id', 'item')}"
            carry["tags"] = list(carry.get("tags", [])) + ["최근 검증 정보"]
            items.append(carry)
            seen_ids.add(carry["id"])
            seen_urls.update(urls)
            if len(items) >= MIN_DISPLAY_ITEMS:
                report["items"] = items[:MAX_ITEMS]
                report["summary"] = (
                    f"신규 수집 정보와 최근 {MAX_AGE_DAYS}일 이내 실제 URL 검증 정보를 합쳐 "
                    f"{len(report['items'])}건을 표시합니다."
                )
                return report

    report["items"] = items[:MAX_ITEMS]
    return report


def main() -> int:
    today = datetime.now(tz=KST).date().isoformat()
    report = collect_cards(today)

    web_data = ROOT / "web" / "data.json"
    history = read_history(web_data)
    report = fill_with_recent_verified_items(report, history, today)

    # Do not let a transient source outage replace a working dashboard with
    # an empty daily report. Keep the previous web/data.json intact, but write
    # an archive file so the failure is visible in Actions artifacts/commits.
    if len(report.get("items", [])) < MIN_DISPLAY_ITEMS and history:
        failure_report = {
            **report,
            "summary": "최소 표시 기준을 충족할 실제 URL 정보가 부족해 기존 대시보드 데이터를 유지했습니다.",
        }
        write_json(ROOT / "archive" / f"{today}-insufficient.json", failure_report)
        print(
            f"CW Recruit Intelligence: {today} / {len(report.get('items', []))} cards, "
            "kept existing web/data.json"
        )
        return 0

    history = [row for row in history if row.get("date") != today]
    history.insert(0, report)
    history = sorted(history, key=lambda row: row.get("date", ""), reverse=True)[:HISTORY_LIMIT]

    write_json(web_data, history)
    write_json(ROOT / "archive" / f"{today}.json", report)

    print(f"CW Recruit Intelligence: {today} / {len(report.get('items', []))} cards")
    for item in report.get("items", [])[:10]:
        print(f"- [{item.get('cat')}] {item.get('company')} | {item.get('title')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
