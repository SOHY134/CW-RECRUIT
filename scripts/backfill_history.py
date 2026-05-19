from __future__ import annotations

import json
import re
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crawler.quality import dedupe_cards, normalize_card  # noqa: E402
from rapidfuzz import fuzz  # noqa: E402

MAX_ITEMS = 6
MIN_ITEMS = 5
START = date.fromisoformat("2026-05-01")
END = date.fromisoformat("2026-05-20")


def read_json(path: Path):
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_static_entries() -> list[dict]:
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    match = re.search(r"const ENTRIES\s*=\s*(\[[\s\S]*?\n\]);", html)
    if not match:
        return []
    payload = match.group(1)
    script = "const entries = " + payload + "\nprocess.stdout.write(JSON.stringify(entries));"
    import subprocess

    node = r"C:\Users\ad\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as tmp:
        tmp.write(script)
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            [node, tmp_path],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
        )
        return json.loads(result.stdout)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def current_history_entries() -> list[dict]:
    rows = read_json(ROOT / "web" / "data.json")
    out = []
    if isinstance(rows, list):
        for report in rows:
            out.extend(report.get("items", []))
    return out


def normalize_sources(card: dict) -> dict:
    out = dict(card)
    sources = []
    for src in out.get("sources", []):
        if src.get("url"):
            sources.append({
                "name": src.get("name") or "출처",
                "url": src["url"],
                "level": src.get("level", out.get("level", "B")),
                "verified": src.get("verified", True),
                "verify_note": src.get("verify_note", ""),
                "http_status": src.get("http_status"),
                "original_url": src.get("original_url", src["url"]),
            })
    out["sources"] = sources
    out["level"] = out.get("level") or (sources[0].get("level") if sources else "B")
    out["time"] = out.get("time") or "09:00"
    out["urgency"] = out.get("urgency") or "low"
    out["priority"] = bool(out.get("priority"))
    out["tags"] = out.get("tags") or []
    return out


def score(card: dict, target: date) -> tuple[int, str]:
    cat_base = {"leader": 95, "outflow": 90, "hiring": 65, "hr": 50, "foreign": 45}.get(card.get("cat"), 30)
    urg = {"high": 20, "mid": 10, "low": 0}.get(card.get("urgency", "low"), 0)
    priority = 20 if card.get("priority") else 0
    level = {"A": 10, "B": 5, "C": 0}.get(card.get("level"), 0)
    try:
        published = date.fromisoformat(card.get("date", ""))
        age = max(0, (target - published).days)
    except Exception:
        age = 99
    freshness = max(0, 30 - age)
    return (cat_base + urg + priority + level + freshness, card.get("date", ""))


def report_for_day(day: date, pool: list[dict]) -> dict:
    start = day - timedelta(days=30)
    eligible = [
        c for c in pool
        if start.isoformat() <= c.get("date", "") <= day.isoformat()
        and any(s.get("url") for s in c.get("sources", []))
    ]
    same_day = [c for c in eligible if c.get("date") == day.isoformat()]
    earlier = [c for c in eligible if c.get("date") != day.isoformat()]
    ordered = sorted(same_day, key=lambda c: score(c, day), reverse=True)
    ordered.extend(sorted(earlier, key=lambda c: score(c, day), reverse=True))
    items = dedupe_cards(ordered, MAX_ITEMS)
    if len(items) < MIN_ITEMS:
        seen_urls = {src.get("url") for item in items for src in item.get("sources", []) if src.get("url")}
        seen_titles = [item.get("title", "") for item in items]
        for candidate in ordered:
            card = normalize_card(candidate)
            urls = {src.get("url") for src in card.get("sources", []) if src.get("url")}
            if not urls or urls & seen_urls:
                continue
            if any(fuzz.token_set_ratio(card.get("title", ""), old) >= 92 for old in seen_titles):
                continue
            items.append(card)
            seen_urls.update(urls)
            seen_titles.append(card.get("title", ""))
            if len(items) >= MIN_ITEMS:
                break
        items = items[:MAX_ITEMS]
    for idx, item in enumerate(items):
        if item.get("date") != day.isoformat():
            item["collected_date"] = day.isoformat()
            item["id"] = f"{day.strftime('%Y%m%d')}-carry-{idx+1}-{item.get('id', 'item')}"
            item["tags"] = list(dict.fromkeys((item.get("tags") or []) + ["최근 검증 정보"]))
    summary = f"실제 URL이 확인된 채용시장 신호 {len(items)}건을 표시합니다."
    if len([i for i in items if i.get("date") == day.isoformat()]) < len(items):
        summary = f"당일 및 최근 검증 정보를 합쳐 실제 URL 기반 채용시장 신호 {len(items)}건을 표시합니다."
    return {
        "date": day.isoformat(),
        "summary": summary,
        "contact_targets": [
            i.get("company") for i in items
            if i.get("priority") and i.get("company") and i.get("company") != "시장 동향"
        ][:5],
        "items": items,
    }


def main() -> int:
    raw = [normalize_sources(c) for c in extract_static_entries() + current_history_entries()]
    pool = [
        normalize_card(card) for card in raw
        if any(src.get("url") for src in card.get("sources", []))
    ]
    reports = []
    day = END
    while day >= START:
        reports.append(report_for_day(day, pool))
        day -= timedelta(days=1)

    existing = read_json(ROOT / "web" / "data.json")
    existing_by_date = {r.get("date"): r for r in existing if isinstance(r, dict)} if isinstance(existing, list) else {}
    for report in reports:
        existing_by_date[report["date"]] = report

    history = sorted(existing_by_date.values(), key=lambda row: row.get("date", ""), reverse=True)
    write_json(ROOT / "web" / "data.json", history)
    for report in reports:
        write_json(ROOT / "archive" / f"{report['date']}.json", report)

    for report in sorted(reports, key=lambda r: r["date"]):
        print(report["date"], len(report["items"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
