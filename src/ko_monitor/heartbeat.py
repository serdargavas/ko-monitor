from __future__ import annotations

import logging

import httpx

log = logging.getLogger(__name__)


class Heartbeat:
    """healthchecks.io: ping while the game is monitored, pause when it closes normally."""

    def __init__(self, ping_url: str, api_key: str, client: httpx.Client | None = None):
        self._ping_url = ping_url.rstrip("/")
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=10.0)

    @property
    def enabled(self) -> bool:
        return bool(self._ping_url)

    def ping(self) -> bool:
        if not self.enabled:
            return False
        try:
            self._client.get(self._ping_url).raise_for_status()
            return True
        except httpx.HTTPError as exc:
            log.warning("heartbeat ping failed: %s", exc)
            return False

    def pause(self) -> bool:
        if not (self.enabled and self._api_key):
            return False
        check_uuid = self._ping_url.rsplit("/", 1)[-1]
        try:
            self._client.post(
                f"https://healthchecks.io/api/v3/checks/{check_uuid}/pause",
                headers={"X-Api-Key": self._api_key},
            ).raise_for_status()
            return True
        except httpx.HTTPError as exc:
            log.warning("heartbeat pause failed: %s", exc)
            return False
