from __future__ import annotations

from abc import ABC, abstractmethod
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.config import Settings
from core.logger import get_logger
from core.schemas import CollectedItem


class BaseCollector(ABC):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.logger = get_logger(self.__class__.__name__)
        self.client = httpx.Client(
            timeout=self.settings.request_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": self.settings.user_agent},
        )

    @abstractmethod
    def collect(self, source) -> list[CollectedItem]:
        raise NotImplementedError

    def fetch_text(self, url: str) -> str:
        if not self._allowed_by_robots(url):
            raise PermissionError(f"robots.txt 정책으로 접근이 차단된 URL입니다: {url}")
        response = self.client.get(url)
        response.raise_for_status()
        return response.text

    def fetch_json(self, url: str) -> dict:
        if not self._allowed_by_robots(url):
            raise PermissionError(f"robots.txt 정책으로 접근이 차단된 URL입니다: {url}")
        response = self.client.get(url)
        response.raise_for_status()
        return response.json()

    def _allowed_by_robots(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False

        robots_url = urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")
        parser = RobotFileParser()
        try:
            robots_text = self.client.get(robots_url).text
            parser.parse(robots_text.splitlines())
            return parser.can_fetch(self.settings.user_agent, url)
        except Exception as exc:  # pragma: no cover
            self.logger.warning("robots.txt 확인 실패: %s", exc)
            return not self.settings.strict_robots_policy
