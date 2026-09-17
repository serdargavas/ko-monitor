"""Single process: the agent loop runs in a background thread, the API server in the main thread."""

import logging
import socket
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


class ApiPortInUse(RuntimeError):
    """The API port could not be bound (usually another KO Monitor is already running)."""


def bind_api_socket(port: int) -> socket.socket:
    """Binds and listens on (API_HOST, port) before any monitoring work starts.

    Raises ApiPortInUse, after logging, when the port is taken. Holding the socket from here on
    means a second copy fails before its agent loop could tick even once.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            # Windows: without it another process could bind the same port with SO_REUSEADDR.
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((API_HOST, port))
        sock.listen()
    except OSError as exc:
        sock.close()
        log.error("port %d kullanımda — başka bir KO Monitor çalışıyor olabilir (%s)", port, exc)
        raise ApiPortInUse(f"port {port} is in use") from exc
    return sock


def make_server(app, port: int) -> uvicorn.Server:
    # log_config=None keeps our rotating log setup; access logs would flood it (status polling every 5 s).
    config = uvicorn.Config(app, host=API_HOST, port=port, log_config=None, access_log=False)
    return uvicorn.Server(config)


def run_with_api(
    loop: Callable[[threading.Event], None],
    server,
    stop: threading.Event,
    join_timeout_s: float = LOOP_JOIN_TIMEOUT_S,
    *,
    sockets: list[socket.socket] | None = None,
) -> None:
    """Runs server.run() in the calling thread; stops and joins the loop however the server ends.

    sockets: already bound listening sockets handed to uvicorn.Server.run(sockets=...).
    """
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
        if sockets is None:
            server.run()
        else:
            server.run(sockets=sockets)
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
    sock: socket.socket | None = None,
    bind: Callable[[int], socket.socket] = bind_api_socket,
) -> None:
    """sock: the API socket if the caller already bound it; otherwise it is bound here, first.

    Raises ApiPortInUse without starting the agent loop when the port is taken.
    """
    try:
        if sock is None:
            sock = bind(cfg.api.port)
        app = create_app(
            storage, board, source, notifier, vapid_public_key,
            stream_quality=cfg.api.stream_quality, web_dir=web_dir,
            income_max_jump=cfg.thresholds.income_max_jump,
            scroll_price=cfg.items.scroll_price,
        )
        server = server_factory(app, cfg.api.port)
        log.info("API on http://%s:%d (publish with: tailscale serve --bg %d)", API_HOST, cfg.api.port, cfg.api.port)
        run_with_api(agent.run, server, threading.Event(), sockets=[sock])
    finally:
        if sock is not None:
            sock.close()  # uvicorn closes it on a normal shutdown; closing twice is harmless
        # Only after the loop has stopped: it writes to storage and reads from the capture.
        source.close()
        storage.close()
