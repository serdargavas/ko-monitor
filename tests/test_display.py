from ko_monitor.display import has_active_display

ACTIVE = 0x1
MIRRORING = 0x8


def test_active_display_detected():
    assert has_active_display(lambda: [0, ACTIVE, 0]) is True


def test_no_active_display_when_every_adapter_is_off():
    # Every monitor physically off: Windows stops composing and capture repeats its last frame.
    assert has_active_display(lambda: [0, 0, 0, 0]) is False


def test_no_adapters_at_all():
    assert has_active_display(lambda: []) is False


def test_mirroring_driver_does_not_count_as_a_display():
    assert has_active_display(lambda: [ACTIVE | MIRRORING]) is False


def test_fails_open_when_the_display_list_cannot_be_read():
    def boom():
        raise OSError("EnumDisplayDevices failed")

    # A helper fault must never suppress genuine frozen detection.
    assert has_active_display(boom) is True
