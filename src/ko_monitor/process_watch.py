from __future__ import annotations

from collections.abc import Iterable

import psutil


def is_process_running(name: str, processes: Iterable | None = None) -> bool:
    target = name.lower()
    for proc in processes if processes is not None else psutil.process_iter(["name"]):
        try:
            if (proc.info.get("name") or "").lower() == target:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False
