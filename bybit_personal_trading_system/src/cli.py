from __future__ import annotations

import argparse
import sys

from src.service import TradingService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bybit 개인 트레이딩 시스템 CLI",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="레포 루트 경로입니다. 기본값은 현재 위치한 프로젝트 디렉터리입니다.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("bootstrap", help="초기 디렉터리와 SQLite DB를 준비합니다.")
    subparsers.add_parser("data-fetch", help="Bybit 시장 데이터를 내려받고 갱신합니다.")
    subparsers.add_parser("research-all", help="백테스트, 워크포워드, 자동 평가를 한 번에 수행합니다.")
    subparsers.add_parser("report", help="최신 연구 결과 기준으로 HTML/CSV/JSON 리포트를 다시 생성합니다.")
    subparsers.add_parser("paper-start", help="Bybit 공개 시장데이터로 실시간 페이퍼 트레이딩을 시작합니다.")
    subparsers.add_parser("demo-start", help="Bybit 데모 트레이딩 엔진을 시작합니다.")
    subparsers.add_parser("live-start", help="Bybit 실거래 엔진을 시작합니다.")
    subparsers.add_parser("status", help="현재 제어 상태, 포지션, 최근 이벤트를 보여줍니다.")
    subparsers.add_parser("pause", help="신규 진입을 일시 중지합니다.")
    subparsers.add_parser("resume", help="일시 중지 또는 킬 스위치를 해제하고 재개합니다.")
    subparsers.add_parser("kill", help="킬 스위치를 켜고 실행 중인 엔진을 정리 종료하도록 지시합니다.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    service = TradingService(repo_root=args.root)

    try:
        if args.command == "bootstrap":
            print(service.bootstrap())
        elif args.command == "data-fetch":
            print(service.data_fetch())
        elif args.command == "research-all":
            print(service.research_all())
        elif args.command == "report":
            print(service.report())
        elif args.command == "paper-start":
            print(service.start("paper"))
        elif args.command == "demo-start":
            print(service.start("demo"))
        elif args.command == "live-start":
            print(service.start("live"))
        elif args.command == "status":
            print(service.status())
        elif args.command == "pause":
            print(service.pause())
        elif args.command == "resume":
            print(service.resume())
        elif args.command == "kill":
            print(service.kill())
        else:
            parser.print_help()
            return 1
    except KeyboardInterrupt:
        print("사용자 중단으로 종료했습니다.")
        return 130
    except Exception as exc:
        print(f"오류가 발생했습니다: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
