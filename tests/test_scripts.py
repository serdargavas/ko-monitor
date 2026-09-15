import re
import shutil
import subprocess

import pytest

from helpers import ROOT

SCRIPT = ROOT / "scripts" / "install-autostart.ps1"
SETUP = ROOT / "docs" / "setup.md"


def test_autostart_script_is_ascii():
    # Windows PowerShell 5.1 reads BOM-less files with the ANSI code page; ASCII avoids mangled text.
    assert SCRIPT.read_bytes().isascii()


@pytest.mark.skipif(shutil.which("powershell") is None, reason="Windows PowerShell not available")
def test_autostart_script_parses_without_running_it():
    command = (
        "$errors = $null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile('{SCRIPT}', [ref]$null, [ref]$errors) | Out-Null; "
        "$errors.Count"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0"


def test_autostart_script_registers_a_logon_task_that_restarts_in_the_project_root():
    text = SCRIPT.read_text(encoding="utf-8")
    for needle in (
        "New-ScheduledTaskTrigger -AtLogOn",
        "-RestartCount",
        "-RestartInterval",
        "-WorkingDirectory $projectRoot",
        '"-m ko_monitor run"',
        "pythonw.exe",
        "Register-ScheduledTask",
    ):
        assert needle in text, needle


def test_autostart_script_adds_a_watchdog_trigger_every_minute():
    # RestartCount only covers launch failures; a process that exits non-zero is started
    # again by a trigger repeating every minute, and IgnoreNew keeps it to one instance.
    text = SCRIPT.read_text(encoding="utf-8")
    assert re.search(
        r"New-ScheduledTaskTrigger -Once -At \(Get-Date\)\s+`?\s*-RepetitionInterval \(New-TimeSpan -Minutes 1\)", text
    )
    assert re.search(r"-RepetitionDuration \(New-TimeSpan -Days \d{4,}\)", text)
    assert re.search(r"-Trigger @\(\$logonTrigger, \$watchdogTrigger\)", text)
    assert "-MultipleInstances IgnoreNew" in text


def test_setup_guide_covers_every_step():
    text = SETUP.read_text(encoding="utf-8")
    for needle in (
        "config.example.toml",
        "healthchecks.io",
        "ntfy",
        "tailscale serve --bg 8765",
        "Ana Ekrana Ekle",
        "Bildirimleri aç",
        "Test bildirimi gönder",
        "iOS 16.4",
        "install-autostart.ps1",
        "Unregister-ScheduledTask",
    ):
        assert needle in text, needle
