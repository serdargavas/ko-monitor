import dataclasses
import json
import threading

import numpy as np

from ko_monitor.config import Thresholds
from ko_monitor.models import CaptureStatus, Readings
from ko_monitor.monitor import Monitor, Observation
from ko_monitor.status import AgentStatus, StatusBoard, status_from


def observed_monitor(readings: Readings) -> Monitor:
    monitor = Monitor(Thresholds())
    monitor.observe(Observation(100.0, True, CaptureStatus.OK, readings))
    return monitor


def test_board_starts_empty():
    status = StatusBoard().current()
    assert status == AgentStatus()
    assert status.updated_at is None and status.state is None and status.readings is None


def test_status_from_monitor_is_plain_json_data():
    readings = Readings(
        hud_visible=True, hp=np.int64(9000), hp_max=9996, zone="Ronark Land",
        chat_events=["inventory_full"], frame_diff=np.float32(5.0),
    )
    status = status_from(observed_monitor(readings), 101.0, True, CaptureStatus.OK)
    assert (status.updated_at, status.state, status.process_running, status.capture) == (101.0, "alive", True, "ok")
    assert status.zone_last == "Ronark Land"
    assert status.readings["hp"] == 9000 and type(status.readings["hp"]) is int
    assert type(status.readings["frame_diff"]) is float
    assert status.readings["chat_events"] == ["inventory_full"]
    json.dumps(status.to_dict())


def test_published_status_does_not_change_when_the_monitor_does():
    readings = Readings(hud_visible=True, hp=9000, hp_max=9996, chat_events=["inventory_full"])
    monitor = observed_monitor(readings)
    status = status_from(monitor, 101.0, True, CaptureStatus.OK)
    readings.hp = 1
    readings.chat_events.append("something_else")
    monitor.zone_last = "Moradon"
    assert status.readings["hp"] == 9000
    assert status.readings["chat_events"] == ["inventory_full"]
    assert status.zone_last is None


def test_new_readings_fields_flow_through():
    @dataclasses.dataclass
    class ExtendedReadings(Readings):
        dialog_text: str | None = None

    monitor = Monitor(Thresholds())
    monitor.state = None
    monitor.last_readings = ExtendedReadings(hud_visible=False, dialog_text="Bağlantı koptu")
    status = status_from(monitor, 5.0, True, CaptureStatus.OK)
    assert status.readings["dialog_text"] == "Bağlantı koptu"
    assert status.state is None


def test_closed_game_has_no_capture_or_readings():
    monitor = Monitor(Thresholds())
    monitor.observe(Observation(1.0, False))
    status = status_from(monitor, 1.0, False, None)
    assert (status.state, status.capture, status.readings, status.process_running) == ("closed", None, None, False)


def test_concurrent_publish_and_read_always_sees_whole_statuses():
    board = StatusBoard()
    errors = []

    def writer():
        for i in range(20_000):
            board.publish(AgentStatus(updated_at=float(i), readings={"hp": i}))

    def reader():
        for _ in range(20_000):
            status = board.current()
            if status.updated_at is not None and status.readings["hp"] != status.updated_at:
                errors.append(status)

    threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert board.current().updated_at == 19_999.0


def test_status_exposes_genie_and_item_counts():
    monitor = Monitor(Thresholds())
    reading = Readings(
        hud_visible=True, hp=100, hp_max=100, zone="Ronark Land",
        inventory_open=True, arrow_count=1200, mana_count=250, genie_active=True,
    )
    # The Genie state is debounced (confirm_reads identical readings): a single misread must
    # not silence the death alert, nor un-silence it. Observe the same reading twice.
    monitor.observe(Observation(1.0, True, CaptureStatus.OK, reading))
    monitor.observe(Observation(2.0, True, CaptureStatus.OK, reading))
    status = status_from(monitor, 2.0, True, CaptureStatus.OK).to_dict()
    assert status["arrow_last"] == 1200
    assert status["mana_last"] == 250
    assert status["genie_active"] is True
