import inspect
import logging
import threading
import time

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ko_monitor.config import ApiConfig, Config
from ko_monitor.runtime import (
    API_HOST,
    AgentLoopStopped,
    ApiPortInUse,
    bind_api_socket,
    make_server,
    run_with_api,
    serve,
)
from ko_monitor.status import AgentStatus, StatusBoard


class FakeAgent:
    def __init__(self, board):
        self.board = board
        self.started = threading.Event()
        self.stopped = threading.Event()
        self.thread_name = None

    def run(self, stop):
        self.thread_name = threading.current_thread().name
        self.board.publish(AgentStatus(updated_at=1.0, state="alive", process_running=True, capture="ok"))
        self.started.set()
        stop.wait()
        self.stopped.set()


class Closable:
    """Stands in for Storage and WgcCapture; records whether the loop had stopped before close()."""

    def __init__(self, agent):
        self.agent = agent
        self.closed = False
        self.loop_stopped_at_close = None

    def close(self):
        self.loop_stopped_at_close = self.agent.stopped.is_set()
        self.closed = True


class FakeNotifier:
    def send(self, event):
        return False


class FakeServer:
    def __init__(self, app, port, action):
        self.app = app
        self.port = port
        self.action = action
        self.should_exit = False
        self.result = None
        self.sockets = None

    def run(self, sockets=None):
        self.sockets = sockets
        self.result = self.action(self)


class FakeSocket:
    def __init__(self, agent=None):
        self.closed = False
        # The port must be held before the agent loop may tick even once.
        self.loop_started_at_bind = None if agent is None else agent.started.is_set()

    def close(self):
        self.closed = True


def run_serve(tmp_path, action, port=9123):
    board = StatusBoard()
    agent = FakeAgent(board)
    storage, source = Closable(agent), Closable(agent)
    servers, sockets = [], []

    def factory(app, port):
        servers.append(FakeServer(app, port, action(agent)))
        return servers[-1]

    def bind(port):
        sockets.append((port, FakeSocket(agent)))
        return sockets[-1][1]

    cfg = Config(api=ApiConfig(port=port))
    serve(agent, storage, source, FakeNotifier(), board, cfg, "KEY", server_factory=factory, web_dir=tmp_path, bind=bind)
    return dict(agent=agent, storage=storage, source=source, servers=servers, sockets=sockets)


def test_api_reads_the_status_published_by_the_loop_thread(tmp_path):
    def action(agent):
        def run(server):
            assert agent.started.wait(5)
            with TestClient(server.app, base_url="http://127.0.0.1") as client:
                body = client.get("/api/status").json()
            assert not agent.stopped.is_set()  # the loop keeps running while the server serves
            return body
        return run

    parts = run_serve(tmp_path, action)
    [server] = parts["servers"]
    assert server.port == 9123
    assert (server.result["state"], server.result["updated_at"]) == ("alive", 1.0)
    assert parts["agent"].thread_name == "agent-loop"
    assert parts["agent"].stopped.is_set()
    for resource in (parts["storage"], parts["source"]):
        assert resource.closed and resource.loop_stopped_at_close


def test_ctrl_c_stops_the_loop_and_closes_resources(tmp_path):
    board = StatusBoard()
    agent = FakeAgent(board)
    storage, source = Closable(agent), Closable(agent)

    def factory(app, port):
        def interrupted(server):
            assert agent.started.wait(5)
            raise KeyboardInterrupt
        return FakeServer(app, port, interrupted)

    with pytest.raises(KeyboardInterrupt):
        serve(
            agent, storage, source, FakeNotifier(), board, Config(), "KEY",
            server_factory=factory, web_dir=tmp_path, bind=lambda port: FakeSocket(),
        )
    assert agent.stopped.is_set()
    assert storage.closed and source.closed and storage.loop_stopped_at_close


def test_server_runs_on_the_socket_bound_before_the_loop_started(tmp_path):
    parts = run_serve(tmp_path, lambda agent: lambda server: agent.started.wait(5))
    [(port, sock)] = parts["sockets"]
    [server] = parts["servers"]
    assert port == 9123
    assert sock.loop_started_at_bind is False
    assert server.sockets == [sock]
    assert sock.closed


def test_busy_port_never_starts_the_loop(tmp_path, caplog):
    board = StatusBoard()
    agent = FakeAgent(board)
    storage, source = Closable(agent), Closable(agent)
    servers = []

    def busy(port):
        raise ApiPortInUse(port)

    with caplog.at_level(logging.INFO, logger="ko_monitor.runtime"):
        with pytest.raises(ApiPortInUse):
            serve(
                agent, storage, source, FakeNotifier(), board, Config(), "KEY",
                server_factory=lambda app, port: servers.append(port), web_dir=tmp_path, bind=busy,
            )
    assert agent.thread_name is None and not agent.started.is_set()
    assert servers == []
    assert "API on" not in caplog.text
    assert storage.closed and source.closed


def test_bind_api_socket_holds_the_port_and_reports_a_busy_one(caplog):
    sock = bind_api_socket(0)  # ephemeral port, 127.0.0.1 only
    try:
        host, port = sock.getsockname()
        assert host == API_HOST
        with caplog.at_level(logging.ERROR, logger="ko_monitor.runtime"):
            with pytest.raises(ApiPortInUse):
                bind_api_socket(port)
        assert f"port {port} kullanımda" in caplog.text
    finally:
        sock.close()


def test_uvicorn_server_accepts_pre_bound_sockets():
    assert "sockets" in inspect.signature(uvicorn.Server.run).parameters


def test_normal_server_exit_does_not_raise():
    stopped = threading.Event()

    def loop(stop):
        stop.wait()
        stopped.set()

    class QuickServer:
        should_exit = False

        def run(self):
            time.sleep(0.05)

    stop = threading.Event()
    run_with_api(loop, QuickServer(), stop)
    assert stop.is_set() and stopped.is_set()


def test_loop_crash_stops_the_server_and_raises():
    class WaitingServer:
        should_exit = False

        def run(self):
            deadline = time.monotonic() + 5
            while not self.should_exit and time.monotonic() < deadline:
                time.sleep(0.01)

    def crashing_loop(stop):
        raise RuntimeError("boom")

    server = WaitingServer()
    with pytest.raises(AgentLoopStopped):
        run_with_api(crashing_loop, server, threading.Event())
    assert server.should_exit is True


def test_make_server_binds_localhost_only():
    server = make_server(FastAPI(), 8765)
    assert API_HOST == "127.0.0.1"
    assert (server.config.host, server.config.port, server.config.access_log) == ("127.0.0.1", 8765, False)
