import dataclasses

import cv2
import pytest

from helpers import SAMPLES
from ko_monitor.detectors.chat import ChatTracker, classify, normalize, read_chat


def test_normalize():
    assert normalize("  Picked  up 13468 Coins. ") == "picked up 13468 coins."


def test_first_read_is_history():
    assert ChatTracker().new_lines(["a", "b"]) == []


def test_scrolled_chat_returns_only_appended_lines():
    t = ChatTracker()
    t.new_lines(["a", "b", "c", "d"])
    assert t.new_lines(["c", "d", "e", "f"]) == ["e", "f"]


def test_unchanged_chat_returns_nothing():
    t = ChatTracker()
    t.new_lines(["a", "b"])
    assert t.new_lines(["a", "b"]) == []


def test_repeated_identical_message_counts_once_per_new_line():
    t = ChatTracker()
    t.new_lines(["x", "y", "350 SP Used"])
    assert t.new_lines(["y", "350 SP Used", "350 SP Used"]) == ["350 sp used"]


def test_no_overlap_falls_back_to_lines_not_seen_before():
    t = ChatTracker()
    t.new_lines(["a", "b"])
    assert t.new_lines(["b2", "a", "c"]) == ["b2", "c"]


def test_empty_chat_then_message():
    t = ChatTracker()
    t.new_lines([])
    assert t.new_lines(["Your inventory is full"]) == ["your inventory is full"]


def test_classify():
    phrases = {"inventory_full": ["inventory is full"], "coins": ["picked up"]}
    lines = ["picked up 5 coins.", "your inventory is full", "picked up 7 coins."]
    assert classify(lines, phrases) == ["coins", "inventory_full"]
    assert classify(["350 sp used"], phrases) == []


@pytest.mark.ocr
def test_read_chat_on_real_frames(calib, ocr):
    calib = dataclasses.replace(calib, chat_phrases={"coins": ["picked up"]})
    tracker = ChatTracker()
    first = cv2.imread(str(SAMPLES / "normal" / "spike-desktop.png"))
    second = cv2.imread(str(SAMPLES / "normal" / "spike-wgc-visible.png"))
    assert read_chat(first, calib, ocr, tracker) == []
    assert read_chat(second, calib, ocr, tracker) == ["coins"]
