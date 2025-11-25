"""
S3 백업 모듈
거래 로그, 자산 곡선 등을 S3에 자동 백업
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    boto3 = None
    ClientError = Exception
    NoCredentialsError = Exception


class S3Storage:
    """S3에 파일을 백업하는 클래스"""

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: str = "ap-northeast-2",
    ):
        """
        초기화
        
        Args:
            bucket_name: S3 버킷 이름 (환경변수 S3_BUCKET_NAME에서도 읽음)
            aws_access_key_id: AWS Access Key (환경변수에서도 읽음)
            aws_secret_access_key: AWS Secret Key (환경변수에서도 읽음)
            region_name: AWS 리전 (기본값: 서울)
        """
        self.bucket_name = bucket_name or os.getenv("S3_BUCKET_NAME")
        self.region_name = region_name
        self.logger = logging.getLogger("S3Storage")
        self.enabled = bool(self.bucket_name)

        if not self.enabled:
            self.logger.warning("S3 백업이 비활성화되었습니다. S3_BUCKET_NAME을 설정하세요.")
            return

        if boto3 is None:
            self.logger.error("boto3 패키지가 설치되지 않았습니다. pip install boto3")
            self.enabled = False
            return

        try:
            # AWS 자격증명은 환경변수 또는 IAM 역할에서 자동으로 읽음
            # EC2에서 실행 시 IAM 역할을 사용하면 키가 필요 없음
            self.s3_client = boto3.client(
                "s3",
                region_name=self.region_name,
                aws_access_key_id=aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY"),
            )
            # 버킷 존재 확인
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            self.logger.info(f"S3 백업이 활성화되었습니다. 버킷: {self.bucket_name}")
        except NoCredentialsError:
            self.logger.error("AWS 자격증명을 찾을 수 없습니다.")
            self.enabled = False
        except ClientError as e:
            self.logger.error(f"S3 버킷 접근 실패: {e}")
            self.enabled = False
        except Exception as e:
            self.logger.error(f"S3 초기화 실패: {e}")
            self.enabled = False

    def upload_file(self, local_file_path: str, s3_key: Optional[str] = None) -> bool:
        """
        파일을 S3에 업로드
        
        Args:
            local_file_path: 로컬 파일 경로
            s3_key: S3에 저장할 키 (경로). None이면 파일명 사용
        
        Returns:
            업로드 성공 여부
        """
        if not self.enabled:
            return False

        try:
            file_path = Path(local_file_path)
            if not file_path.exists():
                self.logger.warning(f"업로드할 파일이 없습니다: {local_file_path}")
                return False

            if s3_key is None:
                # 날짜별 폴더 구조: reports/2025-11-18/trade_log.csv
                date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                s3_key = f"reports/{date_str}/{file_path.name}"

            self.s3_client.upload_file(str(file_path), self.bucket_name, s3_key)
            self.logger.info(f"S3 업로드 성공: {s3_key}")
            return True
        except Exception as e:
            self.logger.error(f"S3 업로드 실패 ({local_file_path}): {e}")
            return False

    def backup_reports(self, reports_dir: str = "reports") -> bool:
        """
        reports 폴더의 모든 CSV 파일을 S3에 백업
        
        Args:
            reports_dir: 리포트 폴더 경로
        
        Returns:
            백업 성공 여부
        """
        if not self.enabled:
            return False

        try:
            reports_path = Path(reports_dir)
            if not reports_path.exists():
                self.logger.warning(f"리포트 폴더가 없습니다: {reports_dir}")
                return False

            success_count = 0
            for csv_file in reports_path.glob("*.csv"):
                if self.upload_file(str(csv_file)):
                    success_count += 1

            self.logger.info(f"S3 백업 완료: {success_count}개 파일")
            return success_count > 0
        except Exception as e:
            self.logger.error(f"S3 백업 실패: {e}")
            return False

    def upload_log(self, log_file_path: str) -> bool:
        """
        로그 파일을 S3에 업로드
        
        Args:
            log_file_path: 로그 파일 경로
        
        Returns:
            업로드 성공 여부
        """
        if not self.enabled:
            return False

        try:
            # 로그는 logs/날짜/파일명 구조로 저장
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            log_file = Path(log_file_path)
            s3_key = f"logs/{date_str}/{log_file.name}"
            return self.upload_file(log_file_path, s3_key)
        except Exception as e:
            self.logger.error(f"로그 업로드 실패: {e}")
            return False

