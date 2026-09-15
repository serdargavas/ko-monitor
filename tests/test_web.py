import importlib.util
import json
import re

import cv2
import pytest
from fastapi.testclient import TestClient

from helpers import ROOT
from ko_monitor.api import WEB_DIR, create_app
from ko_monitor.models import EventKind, State
from ko_monitor.status import StatusBoard

JS_FILES = sorted((WEB_DIR / "js").rglob("*.js"))
IMPORT = re.compile(r"""(?:import|export)\s[^'"]*?from\s+["']([^"']+)["']|import\(\s*["']([^"']+)["']\s*\)""")


class NullSource:
    def latest(self):
        raise AssertionError("not used")

    def close(self):
        pass


class NullNotifier:
    def send(self, event):
        return False


@pytest.fixture(scope="module")
def client():
    app = create_app(object(), StatusBoard(), NullSource(), NullNotifier(), "KEY", extra_hosts=["testserver"])
    with TestClient(app) as c:
        yield c


def read(relative: str) -> str:
    return (WEB_DIR / relative).read_text(encoding="utf-8")


def sw_shell() -> list[str]:
    block = re.search(r"const SHELL = \[(.*?)\];", read("sw.js"), re.S).group(1)
    return re.findall(r'"([^"]+)"', block)


def registered_screens() -> list[str]:
    block = re.search(r"const SCREENS = \{([^}]*)\};", read("js/app.js")).group(1)
    return [name.strip() for name in block.split(",") if name.strip()]


def tab_routes() -> list[str]:
    return re.findall(r'data-route="([a-z]+)"', read("index.html"))


@pytest.mark.parametrize(
    "path, content_type",
    [
        ("/", "text/html"),
        ("/manifest.webmanifest", "application/manifest+json"),
        ("/sw.js", "text/javascript"),
        ("/styles.css", "text/css"),
        ("/js/app.js", "text/javascript"),
        ("/icons/icon-180.png", "image/png"),
    ],
)
def test_real_web_files_are_served(client, path, content_type):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)


def test_manifest_is_installable():
    manifest = json.loads(read("manifest.webmanifest"))
    assert manifest["display"] == "standalone"
    assert manifest["scope"] == "/"
    assert manifest["start_url"].startswith("/")
    assert {"192x192", "512x512"} <= {icon["sizes"] for icon in manifest["icons"]}
    for icon in manifest["icons"]:
        width, height = map(int, icon["sizes"].split("x"))
        image = cv2.imread(str(WEB_DIR / icon["src"].lstrip("/")))
        assert image is not None and image.shape[:2] == (height, width), icon["src"]


def test_index_links_manifest_apple_icon_and_app_module():
    html = read("index.html")
    assert '<html lang="tr">' in html
    assert '<link rel="manifest" href="/manifest.webmanifest">' in html
    assert '<link rel="apple-touch-icon" href="/icons/icon-180.png">' in html
    assert '<script type="module" src="/js/app.js"></script>' in html
    assert tab_routes() == ["status", "live", "events", "settings"]
    assert cv2.imread(str(WEB_DIR / "icons" / "icon-180.png")).shape[:2] == (180, 180)


@pytest.mark.parametrize("js_file", JS_FILES, ids=lambda p: p.relative_to(WEB_DIR).as_posix())
def test_relative_imports_resolve(js_file):
    for match in IMPORT.finditer(js_file.read_text(encoding="utf-8")):
        target = match.group(1) or match.group(2)
        assert target.startswith("."), f"{target}: no bundler, only relative imports work"
        assert (js_file.parent / target).resolve().is_file(), f"{js_file.name} imports missing {target}"


def test_service_worker_shell_lists_existing_files_and_every_module():
    shell = sw_shell()
    for entry in shell:
        assert (WEB_DIR / ("index.html" if entry == "/" else entry.lstrip("/"))).is_file(), entry
    for js_file in JS_FILES:
        assert "/" + js_file.relative_to(WEB_DIR).as_posix() in shell


def test_service_worker_shows_the_render_payload_and_opens_its_url():
    text = read("sw.js")
    for needle in (
        'addEventListener("push"', 'addEventListener("notificationclick"', "showNotification(",
        "message.title", "message.body", "message.url", "message.kind", "message.ts",
    ):
        assert needle in text, needle


def test_every_registered_screen_has_a_tab_and_a_module():
    screens = registered_screens()
    assert "settings" in screens
    assert set(screens) <= set(tab_routes())
    for name in screens:
        assert (WEB_DIR / "js" / "screens" / f"{name}.js").is_file()


def test_ui_labels_cover_every_state_and_event_kind():
    text = read("js/ui.js")
    for value in [s.value for s in State] + [k.value for k in EventKind]:
        assert re.search(rf"\b{value}:", text), value


def test_icon_script_draws_opaque_square_icons(tmp_path):
    spec = importlib.util.spec_from_file_location("make_icons", ROOT / "scripts" / "make_icons.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    icon = module.render_icon(64)
    assert icon.shape == (64, 64, 3)
    assert tuple(int(v) for v in icon[0, 0]) == module.BACKGROUND
    written = module.main(tmp_path)
    assert [p.name for p in written] == ["icon-180.png", "icon-192.png", "icon-512.png"]
    assert cv2.imread(str(written[2])).shape == (512, 512, 3)


def test_status_and_events_screens_are_registered_first_status():
    screens = registered_screens()
    assert screens[0] == "status"
    assert {"status", "events", "settings"} <= set(screens)


def test_events_screen_clamps_the_timeline_end_to_the_newest_snapshot():
    text = read("js/screens/events.js")
    # Old bug: `const end = Date.now() / 1000;` used the phone's clock verbatim as the
    # boundary, so a phone clock lagging the PC's could place the newest snapshot after
    # `end` and buildSegments would drop its (still current) segment.
    assert not re.search(r"const end = Date\.now\(\) / 1000;", text)
    assert "Math.max(" in text and "Date.now()" in text
    assert "snapshots.length - 1" in text or "snapshots[snapshots.length" in text
    assert "start = end - DAY_S" in text


def test_status_screen_guards_missing_slot_total():
    text = read("js/screens/status.js")
    assert re.search(r"total === null \|\| total === undefined", text)


def test_every_tab_has_a_screen_in_tab_order():
    assert registered_screens() == tab_routes() == ["status", "live", "events", "settings"]
