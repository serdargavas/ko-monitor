"""Tells whether Windows still has an active display.

With every monitor physically off (and no remote session providing a virtual one), Windows stops
composing the desktop: Windows Graphics Capture keeps handing out the LAST frame it composed. The
game itself keeps running — a night of AFK farming proved it, money kept rising — but every frame
looks identical, which the monitor would otherwise confirm as FROZEN and push as a false alarm.
Asking the display list separates "the picture stopped" from "the game stopped".
"""

from __future__ import annotations

import ctypes
import logging

log = logging.getLogger(__name__)

_DISPLAY_DEVICE_ACTIVE = 0x1
_DISPLAY_DEVICE_MIRRORING_DRIVER = 0x8


class _DisplayDevice(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("DeviceName", ctypes.c_wchar * 32),
        ("DeviceString", ctypes.c_wchar * 128),
        ("StateFlags", ctypes.c_ulong),
        ("DeviceID", ctypes.c_wchar * 128),
        ("DeviceKey", ctypes.c_wchar * 128),
    ]


def _enumerate_windows() -> list[int]:
    """StateFlags of every display adapter Windows knows about."""
    user32 = ctypes.windll.user32
    flags: list[int] = []
    index = 0
    while True:
        device = _DisplayDevice()
        device.cb = ctypes.sizeof(device)
        if not user32.EnumDisplayDevicesW(None, index, ctypes.byref(device), 0):
            return flags
        flags.append(int(device.StateFlags))
        index += 1


def has_active_display(enumerate_flags=_enumerate_windows) -> bool:
    """True while at least one real display is attached (a virtual one from a remote session counts).

    Fails open: if the display list cannot be read, says True so that a helper fault can never
    silence genuine frozen detection.
    """
    try:
        flags = enumerate_flags()
    except Exception:
        log.exception("could not read the display list; assuming a display is attached")
        return True
    return any(
        f & _DISPLAY_DEVICE_ACTIVE and not f & _DISPLAY_DEVICE_MIRRORING_DRIVER for f in flags
    )
