CW_COMPETITORS = {
    "price_compare": [
        "네이버쇼핑", "네이버가격비교", "카카오쇼핑", "쿠팡", "11번가", "G마켓",
        "옥션", "롯데온", "SSG닷컴"
    ],
    "seller_saas": [
        "카페24", "고도몰", "NHN커머스", "아임웹", "사방넷", "셀러허브",
        "샵링커", "이지어드민", "위사"
    ],
    "crossborder_logistics": [
        "CJ대한통운", "큐익스프레스", "로지스팟", "두손컴퍼니", "메쉬코리아",
        "포워더스"
    ],
    "adtech": [
        "네이버 성과형 광고", "카카오쇼핑 광고", "크리테오코리아", "RTB House",
        "몰인원", "샵플링"
    ],
    "fintech_infra": [
        "카카오페이", "토스", "NHN페이코", "KG이니시스", "나이스페이", "채널톡"
    ],
    "large_ecommerce_platform": [
        "티몬", "위메프", "인터파크커머스", "AK몰", "현대H몰", "CJ온스타일"
    ],
}

CW_INTERNAL = {
    "커넥트웨이브", "다나와", "에누리", "에누리닷컴", "메이크샵", "플레이오토",
    "몰테일", "스윗트래커", "connectwave", "danawa", "enuri", "enuri.com",
    "makeshop", "playauto", "malltail", "sweettracker"
}

ALL_COMPETITORS = sorted(
    {name for names in CW_COMPETITORS.values() for name in names},
    key=len,
    reverse=True,
)
