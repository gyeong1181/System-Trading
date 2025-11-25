"""
CloudWatch 로그 연동 모듈
모든 로그를 AWS CloudWatch Logs로 자동 전송
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    boto3 = None
    ClientError = Exception
    NoCredentialsError = Exception


class CloudWatchHandler(logging.Handler):
    """CloudWatch Logs에 로그를 전송하는 Handler"""

    def __init__(
        self,
        log_group_name: str,
        log_stream_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: str = "ap-northeast-2",
    ):
        """
        초기화
        
        Args:
            log_group_name: CloudWatch Log Group 이름
            log_stream_name: CloudWatch Log Stream 이름 (None이면 자동 생성)
            aws_access_key_id: AWS Access Key
            aws_secret_access_key: AWS Secret Key
            region_name: AWS 리전
        """
        super().__init__()
        self.log_group_name = log_group_name
        self.log_stream_name = log_stream_name or f"btc-trend-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
        self.region_name = region_name
        self.enabled = False
        self._logs_client = None
        self._sequence_token = None

        if boto3 is None:
            return

        try:
            self._logs_client = boto3.client(
                "logs",
                region_name=self.region_name,
                aws_access_key_id=aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY"),
            )
            # Log Group 생성 (없으면)
            try:
                self._logs_client.create_log_group(logGroupName=self.log_group_name)
            except ClientError as e:
                if e.response["Error"]["Code"] != "ResourceAlreadyExistsException":
                    raise

            # Log Stream 생성 (없으면)
            try:
                self._logs_client.create_log_stream(
                    logGroupName=self.log_group_name, logStreamName=self.log_stream_name
                )
            except ClientError as e:
                if e.response["Error"]["Code"] != "ResourceAlreadyExistsException":
                    raise

            self.enabled = True
        except NoCredentialsError:
            pass  # AWS 자격증명이 없으면 비활성화
        except Exception:
            pass  # 에러 발생 시 비활성화

    def emit(self, record: logging.LogRecord):
        """로그 레코드를 CloudWatch로 전송"""
        if not self.enabled or self._logs_client is None:
            return

        try:
            # 로그 메시지 포맷팅
            message = self.format(record)
            timestamp = int(record.created * 1000)  # CloudWatch는 밀리초 단위

            # 로그 이벤트 생성
            log_event = {"timestamp": timestamp, "message": message}

            # CloudWatch에 전송
            kwargs = {
                "logGroupName": self.log_group_name,
                "logStreamName": self.log_stream_name,
                "logEvents": [log_event],
            }

            if self._sequence_token:
                kwargs["sequenceToken"] = self._sequence_token

            response = self._logs_client.put_log_events(**kwargs)
            self._sequence_token = response.get("nextSequenceToken")
        except ClientError as e:
            # sequence token 오류 시 재시도
            if e.response.get("Error", {}).get("Code") == "InvalidSequenceTokenException":
                try:
                    self._sequence_token = e.response["Error"]["Message"].split()[-1]
                    self.emit(record)  # 재시도
                except Exception:
                    pass
        except Exception:
            pass  # 에러 발생 시 무시 (로컬 로그는 계속 작동)


def setup_cloudwatch_logger(
    logger_name: str = "BTCTrendFollower",
    log_group_name: Optional[str] = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """
    CloudWatch 로그가 설정된 Logger 생성
    
    Args:
        logger_name: Logger 이름
        log_group_name: CloudWatch Log Group 이름 (환경변수 CLOUDWATCH_LOG_GROUP에서도 읽음)
        level: 로그 레벨
    
    Returns:
        설정된 Logger
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    # 기존 핸들러 제거 (중복 방지)
    if logger.handlers:
        return logger

    # 기본 포맷터
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 콘솔 핸들러 (항상 활성화)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # CloudWatch 핸들러 (설정되어 있으면)
    log_group = log_group_name or os.getenv("CLOUDWATCH_LOG_GROUP")
    if log_group:
        cloudwatch_handler = CloudWatchHandler(log_group_name=log_group)
        cloudwatch_handler.setFormatter(formatter)
        logger.addHandler(cloudwatch_handler)
        logger.info(f"CloudWatch 로그가 활성화되었습니다. Log Group: {log_group}")
    else:
        logger.info("CloudWatch 로그가 비활성화되었습니다. CLOUDWATCH_LOG_GROUP을 설정하세요.")

    logger.propagate = False
    return logger

