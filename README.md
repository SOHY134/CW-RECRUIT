# CW Recruit Intelligence

기존 `cw_intelligence.html` UI/UX를 그대로 사용하고, 매일 09:00 KST에 실제 URL 기반 채용시장 신호를 수집해 `web/data.json`을 갱신하는 안정 운영형 구조입니다.

## 구조

```text
web/index.html          # 기존 UI 그대로 복사
web/data.json           # 기존 HTML이 읽는 날짜별 리포트 배열
crawler/                # 수집, 분류, 검증, 카드 변환 로직
scripts/run_daily.py    # 일일 실행 진입점
archive/                # 날짜별 원본 리포트 보관
.github/workflows/      # GitHub Actions 자동 실행
```

## 운영 원칙

- 실제 URL이 검증된 정보만 카드로 생성합니다.
- 검색/수집을 먼저 수행하고, 확보된 실제 URL만 분류·분석합니다.
- 수집일 기준 7일 이내 기사만 반영합니다.
- 우선순위는 `인재 유출 > 리더 이탈 > 채용 확대 > 해외/외국계 > HR NEWS`입니다.
- 핵심 정보가 부족할 때만 해외/HR NEWS로 fallback합니다.
- 하루 표시 카드는 최소 3개, 최대 6개입니다.
- 신규 수집이 3개 미만이면 7일 이내의 실제 URL 검증 정보만 보충 후보로 사용합니다.
- 정보가 부족해도 가짜 카드는 생성하지 않습니다.
- 각 source에는 `verified`, `verify_note`, `http_status`를 함께 저장해 운영 중 출처 상태를 확인할 수 있습니다.

## GitHub Pages 설정

1. 이 폴더 전체를 GitHub Repository에 업로드합니다.
2. `Settings -> Actions -> General -> Workflow permissions`에서 `Read and write permissions`를 켭니다.
3. `Settings -> Pages`에서 `Deploy from branch`, `main`, `/web`을 선택합니다.
4. `Actions -> Daily Recruit Intelligence -> Run workflow`로 최초 실행합니다.

업로드 시 `__pycache__`, `.pyc`, 로컬 가상환경 폴더는 제외하세요. 이 배포본의 `.gitignore`에는 Python 캐시 제외 규칙이 들어 있습니다.

## 네이버 뉴스 강화

네이버 뉴스 검색 API 키가 있으면 Repository Secrets에 아래를 추가하세요.

```text
NAVER_CLIENT_ID
NAVER_CLIENT_SECRET
```

키가 없어도 Google News RSS 기반 기본 수집은 동작합니다.

## 로컬 실행

```bash
pip install -r requirements.txt
python scripts/run_daily.py
```

## 배포 전 체크리스트

- `web/index.html`과 `web/data.json`이 모두 업로드되어야 합니다.
- `web/data.json`은 배열 형태여야 합니다. 기존 HTML은 날짜별 리포트 배열을 읽습니다.
- Actions 권한이 `Read and write permissions`가 아니면 자동 커밋이 실패합니다.
- 네이버 API Secret이 없어도 Google News RSS로 동작하지만, 국내 기사 품질을 높이려면 Secret 추가를 권장합니다.
- 최소 3개를 채울 실제 URL 정보가 부족한 날에는 기존 `web/data.json`을 유지해 대시보드가 비지 않도록 처리되어 있습니다.
