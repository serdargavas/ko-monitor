import threading
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ko_monitor.config import ApiConfig, Config
from ko_monitor.runtime import API_HOST, AgentLoopStopped, make_server, run_with_api, serve
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

    def run(self):
        self.result = self.action(self)


def run_serve(tmp_path, action, port=9123):
    board = StatusBoard()
    agent = FakeAgent(board)
    storage, source = Closable(agent), Closable(agent)
    servers = []

    def factory(app, port):
        servers.append(FakeServer(app, port, action(agent)))
        return servers[-1]

    cfg = Config(api=ApiConfig(port=port))
    serve(agent, storage, source, FakeNotifier(), board, cfg, "KEY", server_factory=factory, web_dir=tmp_path)
    return dict(agent=agent, storage=storage, source=source, servers=servers)


def test_api_reads_the_status_published_by_the_loop_thread(tmp_path):
    def action(agent):
        def run(server):
            assert agent.started.wait(5)
            with TestClient(server.app) as client:
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
        serve(agent, storage, source, FakeNotifier(), board, Config(), "KEY", server_factory=factory, web_dir=tmp_path)
    assert agent.stopped.is_set()
    assert storage.closed and source.closed and storage.loop_stopped_at_close


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
