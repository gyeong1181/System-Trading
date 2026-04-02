# AI Cloud Career Opportunity Watcher

한국 내 AI/클라우드 채용과 기업 변화 신호를 모아, 운영자가 짧게 검토하고 승인한 항목만 Telegram 다이제스트로 보내는 승인 기반 MVP입니다. 목적은 단순 정보 나열이 아니라 `판단 보조형 기회 워처`를 만드는 것입니다.

## 구현 계획
1. 프로젝트 골격과 설정, DB, 모델 생성
2. 채용 수집기 1종 이상, 뉴스/변화 신호 수집기 1종 이상 구현
3. 정규화, dedupe hash, 규칙 기반 점수화 적용
4. 구조화 요약 생성과 승인 큐 연결
5. FastAPI + Jinja 경량 관리 UI 제공
6. Telegram 다이제스트 발송
7. 테스트와 운영 문서 정리

## 현재 MVP 범위
- 채용 소스: `Moloco / Sendbird / Coupang` Greenhouse 기반 공개 채용 + `Wanted` 검색 기반 공개 공고
- 변화 신호 소스: `Moloco Newsroom / Sendbird Blog`
- 저장소: SQLite
- 백엔드: FastAPI + SQLAlchemy
- 스케줄링: APScheduler
- UI: Jinja Template 기반 관리자 화면
- 알림: Telegram Bot API

## 파일 트리
```text
ai_cloud_career_opportunity_watcher/
├─ app/
├─ collectors/
├─ parsers/
├─ scorers/
├─ summarizers/
├─ database/
├─ admin_ui/
├─ scheduler/
├─ integrations/telegram/
├─ services/
├─ core/
├─ tests/
├─ docs/
├─ data/sample_sources.json
├─ .env.example
├─ Dockerfile
├─ docker-compose.yml
├─ AGENTS.md
└─ README.md
```

## 핵심 동작
- 공개 소스를 수집해 `Opportunity`로 정규화
- 제목/회사/URL/위치 기준 dedupe hash 생성
- 규칙 기반 `relevance_score`, `urgency_score` 계산
- 3줄 요약, 왜 중요한지, 추천 행동을 생성
- 관리자 UI에서 승인/거절
- 승인된 항목만 일일 다이제스트에 포함
- 다이제스트에는 아래 요소를 포함
  - 이번 주 주목할 만한 기회 3개
  - 왜 지금 봐야 하는지
  - 타깃 독자가 당장 취할 행동 1개

## 수집처 확장 판단
- `Wanted`는 공식 공개 검색 페이지가 확인되어 기본 샘플 소스로 추가했다.
- `Jumpit`는 공개 개별 포지션 페이지는 확인됐지만, 이 환경에서 안정적인 검색/목록 URL을 공식적으로 확정하기 어려워 수집기 지원만 추가하고 기본 활성화는 꺼 두었다.
- 효과는 `플랫폼 자체 채용보드 + 채용 플랫폼 집계`를 함께 보게 되어 누락률을 낮추는 데 있다.
- 단점은 중복 증가와 HTML 구조 변경 리스크이므로, 현재는 dedupe hash와 승인 큐로 이를 흡수한다.

## 빠른 실행
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

브라우저에서 `http://127.0.0.1:8000/admin/`으로 접속합니다.

## Docker 실행
```bash
copy .env.example .env
docker compose up --build
```

## 환경 변수
- `DATABASE_URL`: 기본값 `sqlite:///./data/opportunity_watcher.db`
- `SOURCE_CATALOG_PATH`: 기본값 `data/sample_sources.json`
- `COLLECTION_CRON`: 기본값 `0 8,13,18 * * *`
- `SCHEDULER_ENABLED`: 스케줄러 사용 여부
- `COLLECTION_ON_STARTUP`: 앱 시작 시 즉시 수집 여부
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`: Telegram 발송 설정

## 운영 흐름
1. 관리 화면에서 `지금 수집 실행`
2. 대기 항목을 5~10분 안에 승인/거절
3. 다이제스트 미리보기 확인
4. Telegram 발송

## 테스트
```bash
pytest -q
```

## 주의
- 기본 수집기는 공개 페이지와 공식 채용 API 성격의 엔드포인트만 사용합니다.
- HTML 수집기는 `robots.txt` 확인 후 접근합니다.
- 첫 버전은 작은 규모와 신뢰성을 우선하며, 시각적 화려함보다 운영 단순성을 우선합니다.
