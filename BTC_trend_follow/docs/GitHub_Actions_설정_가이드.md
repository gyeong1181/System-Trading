# 🔄 GitHub Actions 자동 배포 설정 가이드

GitHub Actions를 사용하면 코드를 GitHub에 푸시할 때마다 자동으로 AWS EC2 서버에 배포됩니다.

---

## 📋 목차

1. [GitHub Actions란?](#1-github-actions란)
2. [필요한 준비물](#2-필요한-준비물)
3. [GitHub Secrets 설정](#3-github-secrets-설정)
4. [워크플로우 파일 확인](#4-워크플로우-파일-확인)
5. [테스트 및 사용](#5-테스트-및-사용)
6. [문제 해결](#6-문제-해결)

---

## 1. GitHub Actions란?

**간단 설명:**
- GitHub에 코드를 올리면 자동으로 서버에 배포해주는 기능
- "코드 푸시 → 자동 배포" 자동화

**비유:**
- 코드를 GitHub에 올리면 → 자동으로 AWS 서버에 반영됨
- 수동으로 파일 전송할 필요 없음

---

## 2. 필요한 준비물

### 필수
- ✅ GitHub 계정
- ✅ GitHub 저장소 (이 프로젝트)
- ✅ AWS EC2 인스턴스 (이미 생성됨)
- ✅ EC2 SSH 키 파일 (`.pem` 파일)

---

## 3. GitHub Secrets 설정

GitHub Secrets는 민감한 정보(IP 주소, SSH 키 등)를 안전하게 저장하는 곳입니다.

### 3.1 GitHub 저장소 접속

1. GitHub에서 프로젝트 저장소 열기
2. **Settings** (설정) 클릭
3. 왼쪽 메뉴에서 **Secrets and variables** → **Actions** 클릭
4. **New repository secret** 클릭

### 3.2 Secret 1: EC2_HOST (EC2 퍼블릭 IP)

1. **Name**: `EC2_HOST`
2. **Secret**: EC2 퍼블릭 IPv4 주소 (예: `54.123.45.67`)
3. **Add secret** 클릭

### 3.3 Secret 2: EC2_SSH_KEY (SSH 개인키)

1. **Name**: `EC2_SSH_KEY`
2. **Secret**: `.pem` 파일의 전체 내용 복사
   - Windows: 메모장으로 `.pem` 파일 열기
   - 전체 내용 복사 (첫 줄부터 마지막 줄까지)
   - 예:
     ```
     -----BEGIN RSA PRIVATE KEY-----
     MIIEpAIBAAKCAQEA...
     (전체 내용)
     -----END RSA PRIVATE KEY-----
     ```
3. **Add secret** 클릭

### 3.4 확인

다음 2개의 Secret이 생성되어야 합니다:
- ✅ `EC2_HOST`
- ✅ `EC2_SSH_KEY`

---

## 4. 워크플로우 파일 확인

프로젝트에 `.github/workflows/deploy.yml` 파일이 있어야 합니다.

**파일 위치:**
```
BTC_trend_follow/
  └── .github/
      └── workflows/
          └── deploy.yml
```

**파일 내용 확인:**
- EC2 호스트: `${{ secrets.EC2_HOST }}`
- 사용자명: `ec2-user` (Amazon Linux)
- 배포 경로: `/opt/btc_trend_follow`

---

## 5. 테스트 및 사용

### 5.1 첫 배포 테스트

1. **코드 수정** (아무 파일이나)
   - 예: `README.md`에 한 줄 추가

2. **Git에 커밋 및 푸시**
   ```bash
   git add .
   git commit -m "GitHub Actions 테스트"
   git push origin main
   ```

3. **GitHub에서 확인**
   - 저장소 → **Actions** 탭 클릭
   - "Deploy to AWS EC2" 워크플로우 실행 중 확인
   - ✅ 초록색 체크 = 성공
   - ❌ 빨간색 X = 실패 (로그 확인)

### 5.2 자동 배포 확인

배포가 성공하면:
- EC2 서버의 `/opt/btc_trend_follow`에 파일이 업데이트됨
- Docker 컨테이너가 자동으로 재시작됨

**EC2에서 확인:**
```bash
# SSH 접속
ssh -i your-key.pem ec2-user@YOUR_EC2_IP

# 파일 확인
ls -la /opt/btc_trend_follow

# Docker 상태 확인
cd /opt/btc_trend_follow
docker-compose ps
docker-compose logs --tail=50
```

---

## 6. 문제 해결

### 문제 1: "Permission denied" 오류

**원인**: SSH 키 권한 문제

**해결:**
1. GitHub Secrets에서 `EC2_SSH_KEY` 확인
2. `.pem` 파일 전체 내용이 정확히 복사되었는지 확인
3. 줄바꿈이 올바른지 확인

### 문제 2: "Host key verification failed"

**원인**: EC2 호스트 키 문제

**해결:**
EC2에서 다음 명령어 실행:
```bash
# known_hosts 파일 확인
cat ~/.ssh/known_hosts
```

### 문제 3: 배포는 성공했지만 Docker가 재시작 안 됨

**원인**: Docker Compose 경로 문제

**해결:**
EC2에서 수동 실행:
```bash
cd /opt/btc_trend_follow
docker-compose down
docker-compose build
docker-compose up -d
```

### 문제 4: GitHub Actions가 실행되지 않음

**확인 사항:**
1. `.github/workflows/deploy.yml` 파일이 있는지 확인
2. `main` 브랜치에 푸시했는지 확인
3. GitHub Actions가 활성화되어 있는지 확인 (Settings → Actions)

---

## 📝 워크플로우 동작 원리

```
1. 코드 푸시 (git push)
   ↓
2. GitHub Actions 감지
   ↓
3. 코드 체크아웃 (GitHub에서 가져오기)
   ↓
4. SCP로 EC2에 파일 전송
   ↓
5. SSH로 EC2에 접속
   ↓
6. Docker 재빌드 및 재시작
   ↓
7. 완료!
```

---

## ✅ 완료!

이제 코드를 GitHub에 푸시하면 자동으로 AWS 서버에 배포됩니다! 🚀

**다음 단계:**
1. 코드 수정
2. `git push origin main`
3. GitHub Actions에서 자동 배포 확인
4. EC2에서 서비스 확인

---

**문제가 있으면 GitHub Actions의 로그를 확인하세요!**

