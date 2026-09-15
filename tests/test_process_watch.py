from types import SimpleNamespace

import psutil

from ko_monitor.process_watch import is_process_running


class Denied:
    @property
    def info(self):
        raise psutil.AccessDenied(pid=1)


def procs(*names):
    return [SimpleNamespace(info={"name": n}) for n in names]


def test_finds_process_case_insensitively():
    assert is_process_running("Client.acme", procs("explorer.exe", "client.ACME"))


def test_missing_process():
    assert not is_process_running("Client.acme", procs("explorer.exe", None))


def test_skips_processes_it_cannot_read():
    assert is_process_running("Client.acme", [Denied(), *procs("Client.acme")])
