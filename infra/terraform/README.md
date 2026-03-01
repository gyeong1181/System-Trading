# Terraform IaC

이 디렉터리는 현재 수동으로 운영 중인 자동매매 서버 구성을 Terraform으로 옮기기 위한 최소 실전형 골격입니다.

포함 범위:
- EC2 인스턴스
- 보안 그룹(SSH / HTTP / 선택적 모니터링 포트)
- IAM Role / Instance Profile
- Elastic IP
- 초기 부트스트랩용 `user_data`

## 디렉터리
- `versions.tf`: Terraform / Provider 버전
- `variables.tf`: 입력 변수
- `main.tf`: 인프라 리소스
- `outputs.tf`: 출력값
- `user_data.sh.tftpl`: 초기 서버 부트스트랩
- `terraform.tfvars.example`: 예시 변수 파일

## 시작 방법
1. 예시 파일 복사
```bash
cp terraform.tfvars.example terraform.tfvars
```

2. 값 수정
- `key_name`
- `ssh_allowed_cidrs`
- 필요 시 `monitoring_allowed_cidrs`

3. 실행
```bash
terraform init
terraform plan
terraform apply
```

## 현재 의도
- 기존 수동 운영 인프라를 코드로 재현 가능하게 만들기
- 이후 Nginx, Docker Compose, CloudWatch Agent 설정까지 점진적으로 추가하기

## 다음 확장
- Route53 / 도메인
- ALB / HTTPS
- SSM Parameter Store / Secrets 연동
- CloudWatch Agent 상세 설정
- 기존 수동 생성 리소스 `terraform import`
