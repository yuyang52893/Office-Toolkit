import json
import logging
import threading
import time
import urllib.request
from collections.abc import Callable
from urllib.parse import urlparse

from app.config import Settings

logger = logging.getLogger(__name__)
WebhookSender = Callable[[str, bytes], None]


class WebhookAlerter:
    def __init__(
        self,
        settings: Settings,
        *,
        sender: WebhookSender | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.url = settings.alert_webhook_url.strip()
        self.service = settings.app_name
        self.timeout_seconds = settings.alert_webhook_timeout_seconds
        self.cooldown_seconds = settings.alert_cooldown_seconds
        self.sender = sender or self._default_sender
        self.clock = clock
        self._last_sent: dict[str, float] = {}
        self._lock = threading.Lock()

        if self.url:
            parsed = urlparse(self.url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("ALERT_WEBHOOK_URL 必须是有效的 HTTP(S) 地址")

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def send_server_error(self, *, request_id: str, path: str) -> bool:
        if not self.enabled:
            return False

        now = self.clock()
        cooldown_key = f"server_error:{path}"
        with self._lock:
            last_sent = self._last_sent.get(cooldown_key)
            if last_sent is not None and now - last_sent < self.cooldown_seconds:
                return False
            self._last_sent[cooldown_key] = now

        payload = {
            "event": "server_error",
            "service": self.service,
            "request_id": request_id,
            "path": path,
            "message": "服务处理失败，请稍后重试",
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.sender(self.url, body)
        except Exception:
            with self._lock:
                self._last_sent.pop(cooldown_key, None)
            logger.warning(
                "Webhook alert delivery failed",
                extra={"event": "alert_failed", "path": path},
            )
            return False
        return True

    def _default_sender(self, url: str, body: bytes) -> None:
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            if response.status >= 400:
                raise OSError(f"Webhook returned HTTP {response.status}")
