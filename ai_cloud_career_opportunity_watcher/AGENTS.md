# AGENTS.md

## 프로젝트 목적
`AI Cloud Career Opportunity Watcher`는 한국 내 AI/클라우드 채용과 기업 변화 신호를 모아 운영자가 빠르게 판단하고 승인한 항목만 배포하는 승인 기반 자동화 시스템이다.

핵심 원칙은 `approval-based automation first` 이다. 자동 수집과 요약은 하되, 최종 발송은 운영자 승인 후에만 이뤄진다.

## 아키텍처 요약
- `collectors/`: 공개 채용/뉴스 소스 수집기
- `parsers/`: RSS/HTML 파서
- `database/`: SQLAlchemy 모델과 DB 연결
- `services/`: 수집, 승인, 다이제스트, 부트스트랩 로직
- `admin_ui/`: Jinja 기반 관리 화면
- `scheduler/`: APScheduler 등록
- `integrations/telegram/`: Telegram Bot API 전송

## 코딩 규칙
- Python 위주로 단순하고 읽기 쉬운 구조를 유지한다.
- SQLite 우선, 무거운 외부 인프라는 MVP에 넣지 않는다.
- 승인 흐름을 우회하는 자동 발송 기능을 추가하지 않는다.
- 새로운 기능은 실제 동작하는 수준으로 구현하고, TODO 스캐폴딩을 남발하지 않는다.
- 수집 로직은 공개적이고 저위험인 소스만 사용한다.
- 소스별 파싱 로직은 작고 독립적으로 유지한다.

## 새 소스 추가 방법
1. `data/sample_sources.json`에 새 항목을 추가한다.
2. 기존 `collector_kind`로 처리 가능하면 설정만 추가한다.
3. Greenhouse 외 집계형 채용 페이지는 `html_job_listings`를 우선 검토한다.
4. 새 유형이 필요하면 `collectors/`에 구현하고 `collectors/registry.py`에 등록한다.
5. 필요하면 `parsers/`에 전용 파서를 추가한다.
6. 샘플 항목이 실제로 `Opportunity`, `Summary`, `ApprovalQueue`까지 생성되는지 테스트한다.

## 테스트 실행
```bash
pytest -q
```

## 로컬 실행
```bash
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

## 배포 메모
- Docker 또는 docker-compose로 실행 가능하다.
- 운영 DB는 기본적으로 SQLite 파일 하나를 사용한다.
- Telegram 발송을 쓰려면 `.env`에 Bot Token과 Chat ID를 넣어야 한다.
- 스케줄러는 앱 프로세스 내부에서 돌기 때문에, 단일 인스턴스 운영을 기본으로 가정한다.

## 승인 기반 원칙
- 수집 자동화는 허용한다.
- 요약 자동화는 허용한다.
- 승인 없는 외부 발송은 허용하지 않는다.
- 운영자가 5~10분 안에 검토 가능한 양을 유지하도록 점수화와 dedupe를 우선한다.
