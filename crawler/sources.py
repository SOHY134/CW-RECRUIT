from urllib.parse import quote_plus

from crawler.competitors import ALL_COMPETITORS

RSS_QUERIES = {
    "outflow": [
        "구조조정 OR 희망퇴직 OR 권고사직 IT 플랫폼 커머스",
        "인력 감축 OR 감원 OR 조직개편 스타트업 플랫폼",
        "투자 유치 실패 OR 매각 추진 OR 사업 철수 스타트업",
        "채용 동결 OR 비용 절감 OR 인력 효율화 기업",
        "경영난 OR 유동성 위기 OR 회생절차 OR 워크아웃 기업",
    ],
    "leader": [
        "CEO 교체 OR 대표 사임 OR 임원 교체 커머스 플랫폼",
        "CTO OR CPO OR CISO 퇴사 OR 영입 IT",
        "대표이사 사임 OR 신임 대표 선임 스타트업",
        "창업자 사임 OR 공동창업자 사임 OR 경영진 개편",
    ],
    "hiring": [
        "대규모 채용 OR 채용 확대 OR 공채 스타트업",
        "AI 인재 채용 OR 개발자 채용 OR 경력직 채용",
        "토스 대규모 채용 OR 채널톡 채용 OR 플랫폼 채용",
        "인재 확보 OR 외부인력 수혈 OR 채용 공고 증가",
    ],
    "foreign": [
        "mass layoff tech OR workforce reduction OR hiring freeze",
        "global hiring AI OR tech acquisition OR merger",
        "Meta layoff OR Amazon layoff OR Google layoff OR SpaceX acquisition",
    ],
    "hr": [
        "근로기준법 OR 노동법 개정 OR 최저임금",
        "육아휴직 OR 근로자의 날 OR 공휴일 법정",
        "포괄임금제 OR 주4일제 OR 재택근무 OR 파업",
        "노조 파업 OR 긴급조정 OR 단체교섭",
    ],
}

NAVER_FOCUSED_QUERIES = [
    "site:n.news.naver.com 구조조정 희망퇴직 권고사직",
    "site:n.news.naver.com 대표 사임 CTO 퇴사 임원 교체",
    "site:n.news.naver.com 대규모 채용 채용 확대",
    "site:n.news.naver.com 근로기준법 육아휴직 최저임금",
    "site:n.news.naver.com 삼성전자 파업 긴급조정",
]

COMPETITOR_SIGNAL_TERMS = [
    "구조조정 희망퇴직 권고사직",
    "대표 사임 CEO 교체 임원 교체",
    "대규모 채용 채용 확대 인재 확보",
]


def google_news_rss_url(query: str, lang: str = "ko", region: str = "KR") -> str:
    ceid = f"{region}:{lang}"
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl={lang}&gl={region}&ceid={ceid}"


def chunks(items: list[str], size: int):
    for idx in range(0, len(items), size):
        yield items[idx:idx + size]


def build_feed_urls():
    urls = []

    # Competitor-focused feeds are placed first because the collector caps feed
    # count for runtime stability. This gives CW-adjacent companies first pass.
    for names in chunks(ALL_COMPETITORS, 6):
        target = " OR ".join(names)
        for signal in COMPETITOR_SIGNAL_TERMS:
            urls.append(google_news_rss_url(f"({target}) {signal}"))

    for queries in RSS_QUERIES.values():
        for query in queries:
            lang, region = ("en-US", "US") if query.lower().startswith(("mass ", "global ", "meta ")) else ("ko", "KR")
            urls.append(google_news_rss_url(query, lang=lang, region=region))
    for query in NAVER_FOCUSED_QUERIES:
        urls.append(google_news_rss_url(query))
    return urls
