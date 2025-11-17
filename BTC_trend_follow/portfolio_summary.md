# Portfolio Summary – BTC 추세추종 (AuraBot v1.6.1 Python)

## Elevator Pitch
“BTC 추세추종은 TradingView PineScript 전략을 AWS에서 돌아가는 파이썬 서비스로 옮긴 프로젝트입니다. 실시간 WebSocket, ATR 리스크 관리, 시스템드 배포와 운영 런북까지 직접 설계해 비전공 신입이라도 클라우드+자동매매 업무를 완주할 수 있음을 보여줍니다.”

## Talking Points
1. **Full-stack build**: 모듈형(`btc_trend_follow`, `indicators`, `risk`, `exchange`, `utils`) 구조로 Pine 규칙을 1:1로 재현.
2. **Cloud mindset**: systemd 서비스, AWS 배포 체크리스트, 아키텍처 문서로 EC2·IAM·SSM·CloudWatch 연계를 설계.
3. **Ops readiness**: 샘플 로그·페이퍼 리포트·Operations Runbook을 통해 모니터링/트러블슈팅 시나리오를 제시.
4. **Security awareness**: `.env` 비밀키를 Parameter Store로 관리하고 최소 권한 IAM/재시작 절차를 정의.

## Resume / Interview Highlights
- Binance WebSocket 재연결 + ATR 포지션 사이징 기반 BTCUSDT 트렌드 팔로워 구현.
- ZIP 아티팩트(`BTCTrendFollower_package.zip`)로 S3/CodeDeploy에 곧바로 배포 가능.
- 운영 문서 세트(DeploymentChecklist, OperationsRunbook, CloudArchitecture) 작성 경험.
- 포트폴리오 문서와 로그, 테스트 결과를 통해 실전 검증 데이터를 제시.

## Next Enhancements
- Terraform 또는 CloudFormation으로 EC2/네트워크 IaC 화.
- CloudWatch 대시보드 + SNS 알림 파이프라인.
- GitHub Actions로 테스트/패키징 자동화 (BTC 추세추종 릴리스 파이프라인).
