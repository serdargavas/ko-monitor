"""Single process: the agent loop runs in a background thread, the API server in the main thread."""

import logging
import threading
from collections.abc import Callable
from pathlib import Path

import uvicorn

from ko_monitor.api import WEB_DIR, create_app
from ko_monitor.config import Config

log = logging.getLogger(__name__)

API_HOST = "127.0.0.1"  # never reachable from the LAN; `tailscale serve` publishes it
LOOP_JOIN_TIMEOUT_S = 15.0


class AgentLoopStopped(RuntimeError):
    """The agent loop ended while the server was still supposed to run."""


def make_server(app, port: int) -> uvicorn.Server:
    # log_config=None keeps our rotating log setup; access logs would flood it (status polling every 5 s).
    config = uvicorn.Config(app, host=API_HOST, port=port, log_config=None, access_log=False)
    return uvicorn.Server(config)


def run_with_api(
    loop: Callable[[threading.Event], None],
    server,
    stop: threading.Event,
    join_timeout_s: float = LOOP_JOIN_TIMEOUT_S,
) -> None:
    """Runs server.run() in the calling thread; stops and joins the loop however the server ends."""
    loop_failed = threading.Event()

    def guarded_loop() -> None:
        try:
            loop(stop)
        except BaseException:
            log.exception("agent loop crashed")
        finally:
            if not stop.is_set():
                loop_failed.set()
                log.error("agent loop ended unexpectedly; stopping the API server")
                server.should_exit = True

    thread = threading.Thread(target=guarded_loop, name="agent-loop", daemon=True)
    thread.start()
    try:
        server.run()
    finally:
        stop.set()
        thread.join(join_timeout_s)
        if thread.is_alive():
            log.warning("agent loop did not stop within %.0f s", join_timeout_s)
    if loop_failed.is_set():
        # Non-zero exit, so Task Scheduler restarts the whole process.
        raise AgentLoopStopped("agent loop stopped unexpectedly")


def serve(
    agent,
    storage,
    source,
    notifier,
    board,
    cfg: Config,
    vapid_public_key: str,
    *,
    server_factory: Callable = make_server,
    web_dir: Path = WEB_DIR,
) -> None:
    app = create_app(
        storage, board, source, notifier, vapid_public_key,
        stream_quality=cfg.api.stream_quality, web_dir=web_dir,
    )
    server = server_factory(app, cfg.api.port)
    log.info("API on http://%s:%d (publish with: tailscale serve --bg %d)", API_HOST, cfg.api.port, cfg.api.port)
    try:
        run_with_api(agent.run, server, threading.Event())
    finally:
        # Only after the loop has stopped: it writes to storage and reads from the capture.
        source.close()
        storage.close()
