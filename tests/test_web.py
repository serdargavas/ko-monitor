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

FRONTEND = ROOT / "frontend"
# web/ is `npm run build` output; hashed file names are read from index.html, never hard-coded.
BUNDLE = re.compile(r'<script type="module"[^>]*\ssrc="(/assets/[^"]+\.js)"')
STYLESHEET = re.compile(r'<link rel="stylesheet"[^>]*\shref="(/assets/[^"]+\.css)"')
QUOTE = "[\"'`]"  # the minifier may emit any string quote
# Workbox's own manifest formatting (quote style, whitespace, quoted-vs-bare "url" key) is an
# implementation detail of the minifier, not something this test should pin down: tolerate any
# of them while still requiring a "url" key mapped to a quoted string value.
PRECACHE_URL = re.compile(rf"{QUOTE}?url{QUOTE}?\s*:\s*({QUOTE})((?:(?!\1).)+)\1")


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


def asset(pattern: re.Pattern) -> str:
    match = pattern.search(read("index.html"))
    assert match, f"index.html has no built asset matching {pattern.pattern}"
    return match.group(1)


def handler_registered(text: str, event: str) -> bool:
    return re.search(rf"addEventListener\(\s*{QUOTE}{event}{QUOTE}", text) is not None


@pytest.mark.parametrize(
    "path, content_type",
    [
        ("/", "text/html"),
        ("/manifest.webmanifest", "application/manifest+json"),
        ("/sw.js", "text/javascript"),
        ("/icons/icon-180.png", "image/png"),
    ],
)
def test_built_files_are_served(client, path, content_type):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(content_type)


def test_bundle_and_stylesheet_are_served(client):
    for path, content_type in ((asset(BUNDLE), "text/javascript"), (asset(STYLESHEET), "text/css")):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.headers["content-type"].startswith(content_type), path


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


def test_index_links_manifest_apple_icon_and_built_bundle():
    html = read("index.html")
    assert '<html lang="tr">' in html
    assert '<link rel="manifest" href="/manifest.webmanifest">' in html
    assert '<link rel="apple-touch-icon" href="/icons/icon-180.png">' in html
    assert '<div id="root"></div>' in html
    assert "/src/main.tsx" not in html
    assert not re.search(r"https?://", html)  # nothing from a CDN
    assert (WEB_DIR / asset(BUNDLE).lstrip("/")).is_file()
    assert (WEB_DIR / asset(STYLESHEET).lstrip("/")).is_file()


def test_old_hand_written_files_are_gone():
    assert not (WEB_DIR / "js").exists()
    assert not (WEB_DIR / "styles.css").exists()


def test_service_worker_handles_push_and_notification_clicks():
    text = read("sw.js")
    for event in ("install", "activate", "fetch", "push", "notificationclick"):
        assert handler_registered(text, event), event
    assert "showNotification(" in text
    assert "openWindow(" in text


def test_service_worker_precaches_every_built_file():
    text = read("sw.js")
    assert "__WB_MANIFEST" not in text
    precached = {match.group(2) for match in PRECACHE_URL.finditer(text)}
    built = {p.relative_to(WEB_DIR).as_posix() for p in WEB_DIR.rglob("*") if p.is_file()} - {"sw.js"}
    assert precached == built


def test_service_worker_skips_the_api_and_times_out():
    text = read("sw.js")
    assert "/api/" in text
    assert "/index.html" in text
    assert re.search(r"\b(3e3|3000)\b", text)


def test_bundle_has_every_screen_in_tab_order():
    text = (WEB_DIR / asset(BUNDLE).lstrip("/")).read_text(encoding="utf-8")
    assert re.search(rf"\[{QUOTE}status{QUOTE},\s*{QUOTE}live{QUOTE},\s*{QUOTE}events{QUOTE},\s*{QUOTE}settings{QUOTE}\]", text)
    for title in ("Durum", "Canlı", "Olaylar", "Ayarlar"):
        assert title in text, title


def test_labels_cover_every_state_and_event_kind():
    text = (FRONTEND / "src" / "labels.ts").read_text(encoding="utf-8")
    for value in [s.value for s in State] + [k.value for k in EventKind]:
        assert re.search(rf"\b{value}:", text), value


def test_frontend_sources_never_render_raw_html():
    # Only our sources: the React runtime inside the bundle legitimately contains the word.
    sources = [p for p in (FRONTEND / "src").rglob("*") if p.suffix in {".ts", ".tsx"}]
    assert len(sources) > 10
    for path in sources:
        assert "dangerouslySetInnerHTML" not in path.read_text(encoding="utf-8"), path


def test_build_copies_the_public_folder_unchanged():
    public = FRONTEND / "public"
    for source in public.rglob("*"):
        if source.is_file():
            built = WEB_DIR / source.relative_to(public)
            assert built.read_bytes() == source.read_bytes(), source.name


def test_icon_script_draws_opaque_square_icons(tmp_path):
    spec = importlib.util.spec_from_file_location("make_icons", ROOT / "scripts" / "make_icons.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.ICON_DIR == ROOT / "frontend" / "public" / "icons"
    icon = module.render_icon(64)
    assert icon.shape == (64, 64, 3)
    assert tuple(int(v) for v in icon[0, 0]) == module.BACKGROUND
    written = module.main(tmp_path)
    assert [p.name for p in written] == ["icon-180.png", "icon-192.png", "icon-512.png"]
    assert cv2.imread(str(written[2])).shape == (512, 512, 3)
