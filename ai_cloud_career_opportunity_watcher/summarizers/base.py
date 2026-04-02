from __future__ import annotations

from abc import ABC, abstractmethod


class BaseSummarizer(ABC):
    @abstractmethod
    def summarize(self, opportunity) -> dict[str, str]:
        raise NotImplementedError
