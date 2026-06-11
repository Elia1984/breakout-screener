from __future__ import annotations

import logging

import requests


class TelegramClient:
    """Small Telegram sender that keeps tokens out of logs and source code."""

    def __init__(
        self,
        token: str,
        chat_id: str,
        *,
        logger: logging.Logger | None = None,
        timeout: int = 10,
    ) -> None:
        self.token = token or ""
        self.chat_id = chat_id or ""
        self.timeout = timeout
        self.logger = logger or logging.getLogger(__name__)

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def _redact(self, text: str) -> str:
        safe = str(text)
        for value in (self.token, self.chat_id):
            if value:
                safe = safe.replace(value, "***")
        return safe

    def send(self, message: str) -> bool:
        if not self.configured:
            self.logger.warning("Telegram is not configured.")
            return False

        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                },
                timeout=self.timeout,
            )
            if response.status_code != 200:
                self.logger.warning(
                    "Telegram failed: %s %s",
                    response.status_code,
                    self._redact(response.text[:300]),
                )
                return False
            return True
        except Exception as exc:
            self.logger.warning("Telegram request failed: %s", self._redact(str(exc)))
            return False

