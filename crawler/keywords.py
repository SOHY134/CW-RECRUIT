CATEGORY_KEYWORDS = {
    "outflow": {
        "high": [
            "구조조정", "희망퇴직", "권고사직", "정리해고", "대규모 감원", "인력 감축", "감원",
            "사업 철수", "채용 동결", "법인 청산", "회생절차", "워크아웃"
        ],
        "mid": [
            "조직개편", "조직 개편", "인력 효율화", "조직 슬림화", "비용 절감", "비용 효율화",
            "부서 통폐합", "매각 추진", "투자 유치 실패", "IPO 철회", "적자 확대", "실적 부진"
        ],
        "low": ["수익성 개선", "경영난", "유동성 위기", "구조 개선", "긴축 경영", "생존 경고등"]
    },
    "leader": {
        "high": [
            "대표 사임", "대표이사 사임", "CEO 사임", "CTO 퇴사", "CPO 퇴사", "CISO 퇴사",
            "CFO 사임", "CHRO 사임", "창업자 사임", "임원 사임"
        ],
        "mid": [
            "CEO 교체", "대표 교체", "경영진 교체", "임원 교체", "신임 대표", "최고책임자",
            "대표이사", "공동 창업자", "공동창업자", "CTO", "CPO", "CISO", "CFO", "CHRO",
            "CAIO", "본부장 이동"
        ],
        "low": ["사임", "영입", "합류", "선임", "내정", "이직"]
    },
    "hiring": {
        "high": ["대규모 채용", "세 자릿수 채용", "두 자릿수 채용", "공개채용", "공채"],
        "mid": ["채용 확대", "경력직 채용", "개발자 채용", "AI 인재", "인재 채용", "조직 확대", "인재 확보"],
        "low": ["수시채용", "채용 캠페인", "인재 영입", "외부인력 수혈", "채용 공고"]
    },
    "foreign": {
        "high": ["mass layoff", "job cuts", "workforce reduction", "hiring freeze", "대규모 해고", "M&A", "인수합병"],
        "mid": ["layoff", "restructuring", "acquisition", "merger", "global hiring", "AI restructuring"],
        "low": ["expansion in Korea", "Korea office", "Asia expansion"]
    },
    "hr": {
        "high": ["근로기준법 개정", "노동법 개정", "최저임금", "육아휴직", "근로자의 날", "공휴일", "파업"],
        "mid": ["포괄임금제", "주4일제", "재택근무", "유연근무", "노사갈등", "임금협상", "단체교섭", "긴급조정"],
        "low": ["HR Tech", "HR테크", "조직문화", "직장 내 괴롭힘", "산업안전", "노조"]
    }
}

CATEGORY_ORDER = ["outflow", "leader", "hiring", "foreign", "hr"]
FALLBACK_CATEGORIES = {"foreign", "hr"}
