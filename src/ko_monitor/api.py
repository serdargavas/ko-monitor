"""HTTP API and static PWA files. Listens on 127.0.0.1 only; Tailscale is the access control."""

import dataclasses
import logging
import mimetypes
import time
from collections.abc import Callable, Sequence
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from ko_monitor.capture import FrameSource
from ko_monitor.config import PROJECT_ROOT
from ko_monitor.models import Event, EventKind
from ko_monitor.notifier import Notifier
from ko_monitor.origin import origin_allowed
from ko_monitor.status import StatusBoard
from ko_monitor.storage import Storage
from ko_monitor.stream import stream_router

log = logging.getLogger(__name__)

WEB_DIR = PROJECT_ROOT / "web"
DAY_S = 86400.0
# Host headers the server answers to; anything else (e.g. a DNS-rebinding page) gets 400.
TRUSTED_HOSTS = ["127.0.0.1", "localhost", "*.ts.net"]

# The Windows registry can map .js to text/plain, which browsers refuse for ES modules,
# and .webmanifest is unknown to Python's defaults.
for _content_type, _extension in (
    ("text/html", ".html"),
    ("text/css", ".css"),
    ("text/javascript", ".js"),
    ("application/manifest+json", ".webmanifest"),
    ("image/png", ".png"),
):
    mimetypes.add_type(_content_type, _extension)


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=1)
    auth: str = Field(min_length=1)


class SubscriptionIn(BaseModel):
    """PushSubscription.toJSON() from the browser; extra fields (expirationTime) are ignored."""

    endpoint: str = Field(pattern=r"^https://")
    keys: SubscriptionKeys


def require_same_origin(request: Request) -> None:
    if not origin_allowed(request.headers):
        raise HTTPException(status_code=403, detail="origin not allowed")


def create_app(
    storage: Storage,
    board: StatusBoard,
    source: FrameSource,
    notifier: Notifier,
    vapid_public_key: str,
    *,
    stream_quality: str = "medium",
    web_dir: Path = WEB_DIR,
    now: Callable[[], float] = time.time,
    extra_hosts: Sequence[str] = (),
) -> FastAPI:
    """source and stream_quality feed the live stream route added in stream.py (Task 3)."""
    app = FastAPI(title="KO Monitor", docs_url=None, redoc_url=None, openapi_url=None)
    # Covers HTTP and WebSocket scopes; www_redirect=False: never redirect to another host.
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=[*TRUSTED_HOSTS, *extra_hosts], www_redirect=False
    )

    @app.middleware("http")
    async def cache_headers(request: Request, call_next):
        response = await call_next(request)
        # API data must always be fresh; static files may be cached but are revalidated.
        is_api = request.url.path.startswith("/api/")
        response.headers["Cache-Control"] = "no-store" if is_api else "no-cache"
        return response

    @app.get("/api/status")
    def get_status():
        return {"server_time": now(), **board.current().to_dict()}

    @app.get("/api/snapshots")
    def get_snapshots(since: float | None = None):
        start = now() - DAY_S if since is None else since
        return [
            {**dataclasses.asdict(s), "state": s.state.value}
            for s in storage.snapshots_since(start)
        ]

    @app.get("/api/events")
    def get_events(limit: int = Query(50, ge=1, le=500)):
        return storage.recent_events(limit=limit)

    @app.get("/api/push/vapid-key")
    def get_vapid_key():
        return {"key": vapid_public_key}

    @app.post("/api/push/subscribe", status_code=201, dependencies=[Depends(require_same_origin)])
    def subscribe(subscription: SubscriptionIn):
        storage.add_subscription(subscription.endpoint, subscription.keys.model_dump(), now())
        log.info("push subscription saved")
        return {"ok": True}

    @app.post("/api/push/test", dependencies=[Depends(require_same_origin)])
    def push_test():
        # Sync endpoint: FastAPI runs it in a worker thread, so push retries do not block the event loop.
        count = len(storage.subscriptions())
        delivered = notifier.send(Event(EventKind.TEST, now(), "Bildirimler çalışıyor", notify=True))
        return {"delivered": delivered, "subscriptions": count}

    app.include_router(stream_router(source, stream_quality))

    # Keep the static mount last: routes registered before it take precedence.
    # check_dir=False lets the API start before web/ exists (Task 5 creates it).
    app.mount("/", StaticFiles(directory=web_dir, html=True, check_dir=False), name="web")
    return app
