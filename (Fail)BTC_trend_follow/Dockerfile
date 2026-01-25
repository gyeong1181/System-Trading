# Dockerfile - BTC 추세추종 자동매매 봇
# Python 3.11 기반 이미지 사용
FROM python:3.11-slim

# 작업 디렉토리 설정 (컨테이너 내부 경로)
WORKDIR /app

# 시스템 패키지 업데이트 및 필수 도구 설치
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 파일 복사
COPY requirements.txt .

# Python 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY *.py ./
COPY reports/ ./reports/
COPY logs/ ./logs/

# 로그 및 리포트 디렉토리 생성 (권한 설정)
RUN mkdir -p /app/logs /app/reports && \
    chmod -R 755 /app/logs /app/reports

# 환경변수 설정
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# 메인 프로그램 실행
CMD ["python", "main.py"]

