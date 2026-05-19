from urllib.parse import quote_plus

from crawler.competitors import ALL_COMPETITORS

RSS_QUERIES = {
    "outflow": [
        "구조조정 희망퇴직 권고사직 이커머스 플랫폼",
        "인력 감축 감원 조직개편 스타트업 플랫폼",
        "투자 유치 실패 매각 추진 사업 철수 스타트업",
        "채용 동결 비용 절감 인력 효율화 기업",
        "경영난 유동성 위기 회생절차 워크아웃 기업",
        "홈플러스 법정관리 구조조정 인력 이탈",
        "11번가 희망퇴직 구조조정 감원",
        "롯데온 SSG닷컴 이커머스 희망퇴직 조직개편",
        "커머스 플랫폼 법정관리 회생 매각 인력 구조조정",
        "스타트업 런웨이 부족 투자 실패 인력 감축",
        "대기업 계열사 조직개편 희망퇴직 IT 인력",
    ],
    "leader": [
        "CEO 교체 대표 사임 임원 교체 커머스 플랫폼",
        "CTO CPO CISO 퇴사 영입 IT",
        "대표이사 사임 신임 대표 선임 스타트업",
        "창업자 사임 공동창업자 사임 경영진 개편",
        "딜리버리히어로 DH CEO 사임 배달의민족",
        "대표 퇴임 창업자 사임 최고기술책임자 이직",
        "CFO CISO CHRO CTO 선임 사임 스타트업",
    ],
    "hiring": [
        "대규모 채용 채용 확대 공채 스타트업",
        "AI 인재 채용 개발자 채용 경력직 채용",
        "토스 대규모 채용 채널톡 채용 플랫폼 채용",
        "인재 확보 외부인력 수혈 채용 공고 증가",
        "쿠팡 채용 드라이브 물류 인재 확보",
        "세 자릿수 채용 개발자 PM 데이터 채용",
        "스타트업 투자유치 채용 확대 인재 영입",
    ],
    "foreign": [
        "mass layoff tech workforce reduction hiring freeze",
        "global hiring AI tech acquisition merger",
        "Meta layoff Amazon layoff Google layoff SpaceX acquisition",
        "tech layoffs ecommerce acquisition Korea impact",
    ],
    "hr": [
        "근로기준법 노동법 개정 최저임금",
        "육아휴직 근로자의 날 공휴일 법정",
        "포괄임금제 주4일제 재택근무 파업",
        "노조 파업 긴급조정 단체교섭",
        "삼성전자 파업 긴급조정 노사 교섭",
        "육아휴직 제도 개정 채용 근로조건",
        "노동절 근로자의 날 유급휴일 수당",
    ],
}

NAVER_FOCUSED_QUERIES = [
    "site:n.news.naver.com 구조조정 희망퇴직 권고사직",
    "site:n.news.naver.com 대표 사임 CTO 퇴사 임원 교체",
    "site:n.news.naver.com 대규모 채용 채용 확대",
    "site:n.news.naver.com 근로기준법 육아휴직 최저임금",
    "site:n.news.naver.com 삼성전자 파업 긴급조정",
    "site:n.news.naver.com 홈플러스 법정관리 인력 이탈",
    "site:n.news.naver.com 스타트업 투자 실패 감원",
    "site:n.news.naver.com 커머스 플랫폼 매각 추진",
    "site:n.news.naver.com 세 자릿수 채용 개발자",
]

COMPETITOR_SIGNAL_TERMS = [
    "구조조정 희망퇴직 권고사직",
    "대표 사임 CEO 교체 임원 교체",
    "대규모 채용 채용 확대 인재 확보",
    "매각 추진 사업 철수 경영난",
]


def google_news_rss_url(query: str, lang: str = "ko", region: str = "KR") -> str:
    ceid = f"{region}:{lang}"
    return f"https://news.google.com/rss/search?q={quote_plus(query)}&hl={lang}&gl={region}&ceid={ceid}"


def chunks(items: list[str], size: int):
    for idx in range(0, len(items), size):
        yield items[idx:idx + size]


def build_feed_urls():
    urls = []
    for names in chunks(ALL_COMPETITORS, 6):
        target = " OR ".join(names)
        for signal in COMPETITOR_SIGNAL_TERMS:
            urls.append(google_news_rss_url(f"({target}) {signal}"))

    for category, queries in RSS_QUERIES.items():
        for query in queries:
            lang, region = ("en-US", "US") if category == "foreign" else ("ko", "KR")
            urls.append(google_news_rss_url(query, lang=lang, region=region))
    for query in NAVER_FOCUSED_QUERIES:
        urls.append(google_news_rss_url(query))
    return urls
