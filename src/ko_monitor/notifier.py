from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from pywebpush import WebPushException, webpush

from ko_monitor.messages import render
from ko_monitor.models import Event

log = logging.getLogger(__name__)


class Notifier(Protocol):
    def send(self, event: Event) -> bool: ...


class PrintNotifier:
    """Used by --replay: logs instead of pushing to the phone."""

    def send(self, event: Event) -> bool:
        message = render(event)
        log.info("[bildirim] %s — %s", message["title"], message["body"])
        return False


class WebPushNotifier:
    def __init__(
        self,
        storage,
        vapid_key_path: Path,
        contact: str,
        max_age_s: float = 300.0,
        send: Callable[..., object] = webpush,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.time,
    ):
        self._storage = storage
        self._key_path = vapid_key_path
        self._contact = contact
        self._max_age_s = max_age_s
        self._send = send
        self._sleep = sleep
        self._now = now

    def send(self, event: Event) -> bool:
        if self._now() - event.ts > self._max_age_s:
            log.warning("dropping stale notification %s", event.kind)
            return False
        payload = json.dumps(render(event), ensure_ascii=False)
        delivered = False
        for subscription in self._storage.subscriptions():
            delivered = self._deliver(subscription, payload) or delivered
        return delivered

    def _deliver(self, subscription: dict, payload: str) -> bool:
        for attempt in range(3):
            try:
                self._send(
                    subscription_info=subscription,
                    data=payload,
                    vapid_private_key=str(self._key_path),
                    vapid_claims={"sub": self._contact},
                    ttl=int(self._max_age_s),
                )
                return True
            except WebPushException as exc:
                if getattr(exc, "status_code", None) in (404, 410):
                    log.info("push subscription gone, removing %s", subscription["endpoint"])
                    self._storage.delete_subscription(subscription["endpoint"])
                    return False
                log.warning("push failed (attempt %d): %s", attempt + 1, exc)
            except Exception:
                log.exception("push failed (attempt %d)", attempt + 1)
            if attempt < 2:
                self._sleep(2**attempt)
        return False
