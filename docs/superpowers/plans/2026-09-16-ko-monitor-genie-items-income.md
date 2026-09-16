# Genie durumu, ok/pot takibi ve kazanç grafiği — Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ok/mana potu tükenmeden uyarmak, bildirimleri yalnızca Genie çalışırken göndermek ve saatlik kazancı grafikle göstermek.

**Architecture:** İki yeni saf detektör (`genie.py`, `items.py`) mevcut `Detector` zincirine eklenir ve sonuçları `Readings`'e yazılır. `Monitor` bu okumalardan yeni olaylar üretir ve Genie kapalıyken belirli olayların bildirimini kapatır. Kazanç, hâlihazırda dakikada bir kaydedilen `money_last` anlık kayıtlarından saf bir fonksiyonla hesaplanır ve yeni bir API ucundan sunulur; PWA bunu SVG çubuk grafikle çizer.

**Tech Stack:** Python 3.12, OpenCV, RapidOCR, FastAPI, SQLite; React 19 + TypeScript + Vite, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-16-ko-monitor-genie-items-income-design.md`

## Global Constraints

- Yeni bağımlılık **yok** — ne Python ne npm tarafında. Mevcut paketlerle çözülür.
- Mevcut testlerin tamamı geçmeye devam eder: `304 passed, 2 skipped` taban çizgisidir.
- Kullanıcıya görünen bütün metinler **Türkçe**; bildirim başlıkları `messages.py` ile `labels.ts` arasında **birebir aynı** olmalı.
- Eşik değerleri: `arrow_low = 1000`, `mana_low = 200`, `item_low_repeat_s = 600.0`, `income_max_jump = 50000000`.
- Genie ayrım payı: `margin = 60` (ölçülen fark açıkken +132, kapalıyken −105).
- Şablon eşleşme eşikleri: Genie başlığı `0.8`, eşya ikonu `0.85`.
- Genie durumu **bilinmiyor** (None) iken hiçbir bildirim susturulmaz.
- Test sabitleri: `samples/genie_on/20260916-153935.png` (Genie açık, envanter açık, ok 6380, pot 4150), `samples/genie_off/20260916-154450.png` (Genie kapalı, envanter açık).
- Kare çözünürlüğü 2560x1440; kalibrasyon koordinatları mutlaktır.
- Her commit `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` satırıyla biter.
- `web/` klasörü derlenmiş çıktıdır; elle düzenlenmez, yalnızca `npm run build` ile üretilip commit edilir.

---

## Dosya yapısı

| Dosya | Sorumluluk |
|---|---|
| `src/ko_monitor/detectors/genie.py` (yeni) | Bir kareden Genie'nin çalışıp çalışmadığını söyler |
| `src/ko_monitor/detectors/items.py` (yeni) | Envanterde ok ve pot ikonunu bulur, adetlerini okur |
| `src/ko_monitor/income.py` (yeni) | Anlık kayıtlardan saatlik kazanç hesaplar (saf fonksiyon) |
| `src/ko_monitor/calibration.py` | `GenieSpec`, `ItemsSpec` ve bunların yüklenmesi |
| `src/ko_monitor/models.py` | Yeni `Readings` alanları ve iki yeni `EventKind` |
| `src/ko_monitor/config.py` | Dört yeni eşik |
| `src/ko_monitor/detectors/__init__.py` | Yeni detektörlerin zincire bağlanması |
| `src/ko_monitor/monitor.py` | Ok/pot uyarıları, tekrar bastırma, Genie susturması |
| `src/ko_monitor/messages.py` | İki yeni bildirim başlığı |
| `src/ko_monitor/status.py` | Son bilinen ok/pot ve Genie durumunun API'de görünmesi |
| `src/ko_monitor/api.py` | `GET /api/income` |
| `frontend/src/components/IncomeChart.tsx` (yeni) | Saatlik çubuk grafik (saf SVG) |
| `frontend/src/{types,labels,api}.ts`, `screens/{Events,Status}.tsx` | Tipler, etiketler, istemci ve ekran bağlantıları |
| `scripts/cut_templates.py` (yeni) | Şablonları örnek karelerden kesen tek seferlik betik |

---

### Task 1: Kalibrasyon, yapılandırma ve şablonlar

**Files:**
- Create: `scripts/cut_templates.py`
- Create: `templates/genie_header.png`, `templates/item_arrow.png`, `templates/item_mana.png` (betik üretir)
- Modify: `src/ko_monitor/calibration.py`, `src/ko_monitor/config.py`, `calibration.json`
- Test: `tests/test_calibration.py`, `tests/test_config.py`

**Interfaces:**
- Produces: `GenieSpec(header: TemplateSpec, header_at: tuple[int, int], stop_box: Roi, play_box: Roi, margin: float)`, `ItemsSpec(arrow_file: Path, mana_file: Path, match_threshold: float, count_box: Roi, template_height: int)`, `Calibration.genie: GenieSpec | None`, `Calibration.items: ItemsSpec | None`, `Thresholds.arrow_low: int`, `Thresholds.mana_low: int`, `Thresholds.item_low_repeat_s: float`, `Thresholds.income_max_jump: int`.

- [ ] **Step 1: Şablonları kesen betiği yaz**

`scripts/cut_templates.py`:

```python
"""Cuts the Genie header and item icon templates out of the committed sample frames.

Run once; the templates are committed. Re-run only if the server changes its icons.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
GENIE_HEADER = (2330, 0, 230, 60)  # roi the header template is cut from
ARROW_COL, MANA_COL, ITEM_ROW = 6, 5, 3
TEMPLATE_HEIGHT = 27  # top strip of a slot: excludes the stack count, which changes


def main() -> int:
    on = cv2.imread(str(ROOT / "samples/genie_on/20260916-153935.png"))
    if on is None:
        print("samples/genie_on frame missing", file=sys.stderr)
        return 1
    out = ROOT / "templates"
    x, y, w, h = GENIE_HEADER
    cv2.imwrite(str(out / "genie_header.png"), on[y : y + h, x : x + w])

    inv = json.loads((ROOT / "calibration.json").read_text(encoding="utf-8"))["inventory"]
    ox, oy = inv["slot_origin"]
    sx, sy = inv["slot_step"]
    sw, _ = inv["slot_size"]
    for name, col in (("item_arrow", ARROW_COL), ("item_mana", MANA_COL)):
        cx, cy = ox + col * sx, oy + ITEM_ROW * sy
        cv2.imwrite(str(out / f"{name}.png"), on[cy : cy + TEMPLATE_HEIGHT, cx : cx + sw])
    print("templates written to", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Betiği çalıştır ve şablonların doğru kesildiğini gözle doğrula**

```bash
.venv/Scripts/python.exe scripts/cut_templates.py
```

Beklenen: `templates/` altında üç yeni PNG. `genie_header.png` 230x60, `item_arrow.png` ve `item_mana.png` 45x27 olmalı:

```bash
.venv/Scripts/python.exe -c "import cv2,glob; [print(f, cv2.imread(f).shape) for f in ['templates/genie_header.png','templates/item_arrow.png','templates/item_mana.png']]"
```

- [ ] **Step 3: Kalibrasyon testlerini yaz (başarısız olacak)**

`tests/test_calibration.py` sonuna ekle:

```python
def test_genie_spec_is_loaded(tmp_path):
    calib = load_calibration(Path("calibration.json"))
    assert calib.genie is not None
    assert calib.genie.stop_box == (2511, 9, 12, 13)
    assert calib.genie.play_box == (2482, 9, 14, 14)
    assert calib.genie.margin == 60.0
    assert calib.genie.header_at == (2330, 0)
    assert calib.genie.header.file.name == "genie_header.png"


def test_items_spec_is_loaded():
    calib = load_calibration(Path("calibration.json"))
    assert calib.items is not None
    assert calib.items.match_threshold == 0.85
    assert calib.items.count_box == (1, 28, 30, 16)
    assert calib.items.template_height == 27
    assert calib.items.arrow_file.name == "item_arrow.png"
    assert calib.items.mana_file.name == "item_mana.png"


def test_genie_and_items_are_optional(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({
        "resolution": [2560, 1440], "hp_roi": [0, 0, 1, 1],
        "zone_roi": [0, 0, 1, 1], "chat_roi": [0, 0, 1, 1],
    }), encoding="utf-8")
    calib = load_calibration(path)
    assert calib.genie is None and calib.items is None
```

`tests/test_config.py` sonuna ekle:

```python
def test_item_thresholds_have_defaults():
    t = Config().thresholds
    assert (t.arrow_low, t.mana_low) == (1000, 200)
    assert t.item_low_repeat_s == 600.0
    assert t.income_max_jump == 50_000_000
```

- [ ] **Step 4: Testlerin başarısız olduğunu gör**

```bash
.venv/Scripts/python.exe -m pytest tests/test_calibration.py tests/test_config.py -q
```

Beklenen: FAIL — `Calibration` nesnesinin `genie` özniteliği yok.

- [ ] **Step 5: `calibration.py` içine iki dataclass ve yükleyicilerini ekle**

`DialogSpec` tanımından sonra:

```python
@dataclass(frozen=True)
class GenieSpec:
    """Knight Genie panel: the stop button is gold while it runs and grey while it is stopped."""

    header: TemplateSpec
    header_at: tuple[int, int]  # where the header template was cut from; boxes are relative to it
    stop_box: Roi
    play_box: Roi
    margin: float


@dataclass(frozen=True)
class ItemsSpec:
    arrow_file: Path
    mana_file: Path
    match_threshold: float
    count_box: Roi  # stack count, relative to the slot's top-left corner
    template_height: int
```

`Calibration` dataclass'ına iki alan ekle (`dialog`'dan sonra, varsayılanı None):

```python
    genie: GenieSpec | None = None
    items: ItemsSpec | None = None
```

`load_calibration` içinde `dialog` bloğundan sonra:

```python
    gen = raw.get("genie")
    genie = None
    if gen is not None:
        genie = GenieSpec(
            header=template(gen["header"]),
            header_at=tuple(gen["header"]["roi"][:2]),
            stop_box=tuple(gen["stop_box"]),
            play_box=tuple(gen["play_box"]),
            margin=float(gen.get("margin", 60.0)),
        )

    itm = raw.get("items")
    items = None
    if itm is not None:
        items = ItemsSpec(
            arrow_file=base / itm["arrow_file"],
            mana_file=base / itm["mana_file"],
            match_threshold=float(itm.get("match_threshold", 0.85)),
            count_box=tuple(itm["count_box"]),
            template_height=int(itm.get("template_height", 27)),
        )
```

ve `return Calibration(...)` çağrısına `genie=genie, items=items` ekle.

- [ ] **Step 6: `config.py` içindeki `Thresholds`'a dört alan ekle**

`inventory_full_repeat_s` satırından sonra:

```python
    arrow_low: int = 1000
    mana_low: int = 200
    item_low_repeat_s: float = 600.0
    income_max_jump: int = 50_000_000
```

- [ ] **Step 7: `calibration.json` içine iki blok ekle**

`dialog` bloğunun yanına (dosyanın en üst seviyesine):

```json
  "genie": {
    "header": {"roi": [2330, 0, 230, 60], "file": "templates/genie_header.png", "threshold": 0.8},
    "stop_box": [2511, 9, 12, 13],
    "play_box": [2482, 9, 14, 14],
    "margin": 60
  },
  "items": {
    "arrow_file": "templates/item_arrow.png",
    "mana_file": "templates/item_mana.png",
    "match_threshold": 0.85,
    "count_box": [1, 28, 30, 16],
    "template_height": 27
  }
```

- [ ] **Step 8: Testlerin geçtiğini doğrula**

```bash
.venv/Scripts/python.exe -m pytest tests/test_calibration.py tests/test_config.py -q
```

Beklenen: PASS.

- [ ] **Step 9: Commit**

```bash
git add scripts/cut_templates.py templates/genie_header.png templates/item_arrow.png templates/item_mana.png src/ko_monitor/calibration.py src/ko_monitor/config.py calibration.json tests/test_calibration.py tests/test_config.py
git commit -m "feat: calibrate the genie panel and the arrow/mana item templates

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Genie detektörü

**Files:**
- Create: `src/ko_monitor/detectors/genie.py`
- Test: `tests/test_genie.py`

**Interfaces:**
- Consumes: `GenieSpec` (Task 1), `load_template(path: str) -> np.ndarray | None` ve `crop(frame, roi)` (mevcut).
- Produces: `read_genie(frame: np.ndarray, spec: GenieSpec | None) -> bool | None` — True çalışıyor, False durmuş, None bilinmiyor.

- [ ] **Step 1: Testi yaz (başarısız olacak)**

`tests/test_genie.py`:

```python
from pathlib import Path

import cv2
import numpy as np
import pytest

from ko_monitor.calibration import GenieSpec, TemplateSpec, load_calibration
from ko_monitor.detectors.genie import read_genie

CALIB = load_calibration(Path("calibration.json"))
ON = cv2.imread("samples/genie_on/20260916-153935.png")
OFF = cv2.imread("samples/genie_off/20260916-154450.png")


def test_running_genie_is_detected():
    assert read_genie(ON, CALIB.genie) is True


def test_stopped_genie_is_detected():
    assert read_genie(OFF, CALIB.genie) is False


def test_no_spec_is_unknown():
    assert read_genie(ON, None) is None


def test_missing_panel_is_unknown():
    # A frame with no Genie panel at all: the header template cannot be found.
    blank = np.zeros_like(ON)
    assert read_genie(blank, CALIB.genie) is None


def test_moved_panel_is_still_read(tmp_path):
    # The user dragged the panel 40 px left and 12 px down; the boxes must follow the header.
    moved = np.zeros_like(ON)
    src = ON[0:200, 2300:2560]
    moved[12:212, 2260:2520] = src
    assert read_genie(moved, CALIB.genie) is True


def test_unclear_buttons_are_unknown():
    # Both boxes equally saturated (panel found, buttons washed out) -> no verdict.
    flat = ON.copy()
    spec = CALIB.genie
    for box in (spec.stop_box, spec.play_box):
        x, y, w, h = box
        flat[y : y + h, x : x + w] = (40, 40, 40)
    assert read_genie(flat, spec) is None
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

```bash
.venv/Scripts/python.exe -m pytest tests/test_genie.py -q
```

Beklenen: FAIL — `ko_monitor.detectors.genie` modülü yok.

- [ ] **Step 3: Detektörü yaz**

`src/ko_monitor/detectors/genie.py`:

```python
"""Is Knight Genie running?

The panel's stop button is gold while the genie farms and grey while it is stopped; the play
button mirrors it. Measured on live frames: stop saturation 194-234 running / 66 stopped, play
76 running / 171 stopped. Comparing the two boxes instead of using an absolute threshold keeps
the verdict stable if the screen's brightness or gamma changes.
"""

from __future__ import annotations

import cv2
import numpy as np

from ko_monitor.calibration import GenieSpec, Roi, crop
from ko_monitor.detectors.templates import load_template


def _saturation(frame: np.ndarray, roi: Roi) -> float | None:
    x, y, w, h = roi
    if x < 0 or y < 0 or y + h > frame.shape[0] or x + w > frame.shape[1]:
        return None
    patch = frame[y : y + h, x : x + w]
    if patch.size == 0:
        return None
    return float(cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)[:, :, 1].mean())


def _shift(roi: Roi, dx: int, dy: int) -> Roi:
    x, y, w, h = roi
    return (x + dx, y + dy, w, h)


def read_genie(frame: np.ndarray, spec: GenieSpec | None) -> bool | None:
    """True = running, False = stopped, None = cannot tell (no panel, no template, unclear)."""
    if spec is None:
        return None
    template = load_template(str(spec.header.file))
    if template is None:
        return None
    region = crop(frame, spec.header.roi)
    if region.shape[0] < template.shape[0] or region.shape[1] < template.shape[1]:
        return None
    scores = np.nan_to_num(cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED))
    _, best, _, loc = cv2.minMaxLoc(scores)
    if float(best) < spec.header.threshold:
        return None
    # Where the header sits now versus where it sat when the template was cut.
    dx = spec.header.roi[0] + loc[0] - spec.header_at[0]
    dy = spec.header.roi[1] + loc[1] - spec.header_at[1]
    stop = _saturation(frame, _shift(spec.stop_box, dx, dy))
    play = _saturation(frame, _shift(spec.play_box, dx, dy))
    if stop is None or play is None:
        return None
    if stop - play >= spec.margin:
        return True
    if play - stop >= spec.margin:
        return False
    return None
```

- [ ] **Step 4: Testlerin geçtiğini doğrula**

```bash
.venv/Scripts/python.exe -m pytest tests/test_genie.py -q
```

Beklenen: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ko_monitor/detectors/genie.py tests/test_genie.py
git commit -m "feat: read the genie state from the stop button saturation

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Ok ve pot detektörü

**Files:**
- Create: `src/ko_monitor/detectors/items.py`
- Test: `tests/test_items.py`

**Interfaces:**
- Consumes: `ItemsSpec`, `InventorySpec` (Task 1 ve mevcut), `Ocr.read_line(image) -> tuple[str, float] | None`, `parse_money(text) -> int | None` (mevcut `detectors/inventory.py`).
- Produces: `read_items(frame, inventory_open: bool | None, inv: InventorySpec | None, spec: ItemsSpec | None, ocr) -> tuple[int | None, int | None]` — (ok adedi, pot adedi).

- [ ] **Step 1: Testi yaz (başarısız olacak)**

`tests/test_items.py`:

```python
from pathlib import Path

import cv2
import numpy as np
import pytest

from ko_monitor.calibration import load_calibration
from ko_monitor.detectors.items import read_items
from ko_monitor.ocr import Ocr

CALIB = load_calibration(Path("calibration.json"))
ON = cv2.imread("samples/genie_on/20260916-153935.png")


@pytest.fixture(scope="module")
def ocr():
    return Ocr(min_score=CALIB.ocr_min_score)


def test_reads_arrow_and_mana_counts(ocr):
    arrow, mana = read_items(ON, True, CALIB.inventory, CALIB.items, ocr)
    assert arrow == 6380
    assert mana == 4150


def test_closed_inventory_reads_nothing(ocr):
    assert read_items(ON, False, CALIB.inventory, CALIB.items, ocr) == (None, None)


def test_missing_spec_reads_nothing(ocr):
    assert read_items(ON, True, CALIB.inventory, None, ocr) == (None, None)


def test_item_absent_from_every_slot_counts_as_zero(ocr):
    # No icon matches anywhere -> the stack is gone -> zero, which is what "bitti" means.
    blank = np.zeros_like(ON)
    assert read_items(blank, True, CALIB.inventory, CALIB.items, ocr) == (0, 0)


def test_slot_grid_off_frame_reads_nothing(ocr):
    small = ON[0:400, 0:400].copy()
    assert read_items(small, True, CALIB.inventory, CALIB.items, ocr) == (None, None)
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

```bash
.venv/Scripts/python.exe -m pytest tests/test_items.py -q
```

Beklenen: FAIL — `ko_monitor.detectors.items` modülü yok.

- [ ] **Step 3: Detektörü yaz**

`src/ko_monitor/detectors/items.py`:

```python
"""How many arrows and mana potions are left.

Arrows and potions are found by their icon, not by a fixed slot, so moving them in the bag does
not break the count. The template is cut from the slot's top strip only: the stack count printed
across the bottom changes constantly and would ruin the match. The count itself is read from that
bottom strip with the same recognition-only OCR that reads HP and money.
"""

from __future__ import annotations

import cv2
import numpy as np

from ko_monitor.calibration import InventorySpec, ItemsSpec
from ko_monitor.detectors.inventory import parse_money
from ko_monitor.detectors.templates import load_template

_COUNT_SCALE = 4  # the digits are ~14 px tall; OCR reads them reliably enlarged


def _slot_positions(frame: np.ndarray, inv: InventorySpec) -> list[tuple[int, int]] | None:
    """Every slot's top-left corner, or None when the grid does not fit the frame."""
    width = inv.slot_size[0]
    frame_h, frame_w = frame.shape[:2]
    cells = []
    for row in range(inv.rows):
        for col in range(inv.cols):
            x = inv.slot_origin[0] + col * inv.slot_step[0]
            y = inv.slot_origin[1] + row * inv.slot_step[1]
            if x < 0 or y < 0 or x + width > frame_w or y + inv.slot_size[1] > frame_h:
                return None
            cells.append((x, y))
    return cells


def _count_of(
    frame: np.ndarray, cells: list[tuple[int, int]], template: np.ndarray, spec: ItemsSpec, ocr
) -> int | None:
    best_score, best_cell = -1.0, None
    t_h, t_w = template.shape[:2]
    for x, y in cells:
        patch = frame[y : y + t_h, x : x + t_w]
        if patch.shape[:2] != (t_h, t_w):
            continue
        score = float(np.nan_to_num(cv2.matchTemplate(patch, template, cv2.TM_CCOEFF_NORMED)).max())
        if score > best_score:
            best_score, best_cell = score, (x, y)
    if best_cell is None or best_score < spec.match_threshold:
        return 0  # the stack is gone from the bag: nothing left
    cx, cy, cw, ch = spec.count_box
    x, y = best_cell
    patch = frame[y + cy : y + cy + ch, x + cx : x + cx + cw]
    if patch.size == 0:
        return None
    big = cv2.resize(patch, (cw * _COUNT_SCALE, ch * _COUNT_SCALE), interpolation=cv2.INTER_CUBIC)
    line = ocr.read_line(big)
    return parse_money(line[0]) if line else None


def read_items(
    frame: np.ndarray,
    inventory_open: bool | None,
    inv: InventorySpec | None,
    spec: ItemsSpec | None,
    ocr,
) -> tuple[int | None, int | None]:
    """(arrows, mana potions); both None while the bag is closed or nothing is calibrated."""
    if not inventory_open or inv is None or spec is None:
        return None, None
    arrow_t = load_template(str(spec.arrow_file))
    mana_t = load_template(str(spec.mana_file))
    if arrow_t is None or mana_t is None:
        return None, None
    cells = _slot_positions(frame, inv)
    if cells is None:
        return None, None
    return (
        _count_of(frame, cells, arrow_t, spec, ocr),
        _count_of(frame, cells, mana_t, spec, ocr),
    )
```

- [ ] **Step 4: Testlerin geçtiğini doğrula**

```bash
.venv/Scripts/python.exe -m pytest tests/test_items.py -q
```

Beklenen: 5 passed. `test_reads_arrow_and_mana_counts` gerçek kareden 6380 ve 4150 okumalı.

- [ ] **Step 5: Commit**

```bash
git add src/ko_monitor/detectors/items.py tests/test_items.py
git commit -m "feat: count arrows and mana potions by their inventory icon

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Okumaları zincire bağla

**Files:**
- Modify: `src/ko_monitor/models.py`, `src/ko_monitor/detectors/__init__.py`, `src/ko_monitor/status.py`
- Test: `tests/test_detector.py`, `tests/test_status.py`

**Interfaces:**
- Consumes: `read_genie` (Task 2), `read_items` (Task 3).
- Produces: `Readings.genie_active: bool | None`, `Readings.arrow_count: int | None`, `Readings.mana_count: int | None`; `AgentStatus.genie_active: bool | None`, `AgentStatus.arrow_last: int | None`, `AgentStatus.mana_last: int | None`; `Monitor.arrow_last`, `Monitor.mana_last`, `Monitor.genie_active` (Task 5'te doldurulur, burada yalnızca okunur).

- [ ] **Step 1: Testleri yaz (başarısız olacak)**

`tests/test_detector.py` sonuna:

```python
def test_detector_reports_genie_and_item_counts():
    calib = load_calibration(Path("calibration.json"))
    detector = Detector(calib, Ocr(min_score=calib.ocr_min_score))
    readings = detector.detect(cv2.imread("samples/genie_on/20260916-153935.png"))
    assert readings.genie_active is True
    assert readings.arrow_count == 6380
    assert readings.mana_count == 4150


def test_detector_reports_stopped_genie():
    calib = load_calibration(Path("calibration.json"))
    detector = Detector(calib, Ocr(min_score=calib.ocr_min_score))
    readings = detector.detect(cv2.imread("samples/genie_off/20260916-154450.png"))
    assert readings.genie_active is False
```

`tests/test_status.py` sonuna:

```python
def test_status_exposes_genie_and_item_counts():
    monitor = Monitor(Thresholds())
    monitor.observe(Observation(1.0, True, CaptureStatus.OK, Readings(
        hud_visible=True, hp=100, hp_max=100, zone="Ronark Land",
        inventory_open=True, arrow_count=1200, mana_count=250, genie_active=True,
    )))
    status = status_from(monitor, 2.0, True, CaptureStatus.OK).to_dict()
    assert status["arrow_last"] == 1200
    assert status["mana_last"] == 250
    assert status["genie_active"] is True
```

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

```bash
.venv/Scripts/python.exe -m pytest tests/test_detector.py tests/test_status.py -q
```

Beklenen: FAIL — `Readings` nesnesinin `genie_active` alanı yok.

- [ ] **Step 3: `Readings`'e üç alan ekle**

`src/ko_monitor/models.py`, `Readings` içinde `slots_total` satırından sonra:

```python
    arrow_count: int | None = None
    mana_count: int | None = None
    genie_active: bool | None = None  # None = the Genie panel could not be read
```

- [ ] **Step 4: `Detector.detect` içinde yeni detektörleri çağır**

`src/ko_monitor/detectors/__init__.py` importlarına ekle:

```python
from ko_monitor.detectors.genie import read_genie
from ko_monitor.detectors.items import read_items
```

`detect` içinde `read_inventory` çağrısından hemen sonra:

```python
        arrow_count, mana_count = read_items(
            frame, inventory_open, self._calib.inventory, self._calib.items, self._ocr
        )
```

ve `Readings(...)` çağrısına `frame_diff`'ten önce ekle:

```python
            arrow_count=arrow_count,
            mana_count=mana_count,
            genie_active=read_genie(frame, self._calib.genie),
```

- [ ] **Step 5: `status.py` içine üç alan ekle**

`AgentStatus` dataclass'ına `inventory_seen_at` satırından önce:

```python
    arrow_last: int | None = None
    mana_last: int | None = None
    genie_active: bool | None = None
```

`status_from` içindeki `AgentStatus(...)` çağrısına:

```python
        arrow_last=monitor.arrow_last,
        mana_last=monitor.mana_last,
        genie_active=monitor.genie_active,
```

- [ ] **Step 6: `Monitor`'a üç alanı ekle ve doldur**

`src/ko_monitor/monitor.py`, `__init__` içinde `self.slots_total_last` satırından sonra:

```python
        self.arrow_last: int | None = None
        self.mana_last: int | None = None
        self.genie_active: bool | None = None
```

`__init__` içine, kararlılık sayacı (spec §3: durum değişimi 2 ardışık okuma ile onaylanır):

```python
        self._genie_pending: bool | None = None
        self._genie_reads = 0
```

`_update` içinde, `if r.inventory_open:` bloğunun **hemen üstüne**:

```python
        # A single misread must not silence the death alert, nor un-silence it: the genie state
        # changes only after confirm_reads identical readings.
        if r.genie_active is None:
            self._genie_pending, self._genie_reads = None, 0
        else:
            if r.genie_active == self._genie_pending:
                self._genie_reads += 1
            else:
                self._genie_pending, self._genie_reads = r.genie_active, 1
            if self._genie_reads >= self._t.confirm_reads:
                self.genie_active = r.genie_active
        if r.arrow_count is not None:
            self.arrow_last = r.arrow_count
        if r.mana_count is not None:
            self.mana_last = r.mana_count
```

Bu yüzden Task 5'teki susturma testleri Genie durumunu **iki kez** okutur; tek okumadan sonra
`genie_active` hâlâ `None`'dır ve hiçbir şey susturulmaz.

- [ ] **Step 7: Testlerin geçtiğini doğrula**

```bash
.venv/Scripts/python.exe -m pytest tests/test_detector.py tests/test_status.py tests/test_monitor.py -q
```

Beklenen: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/ko_monitor/models.py src/ko_monitor/detectors/__init__.py src/ko_monitor/status.py src/ko_monitor/monitor.py tests/test_detector.py tests/test_status.py
git commit -m "feat: publish genie state and item counts in readings and status

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Uyarılar ve Genie susturması

**Files:**
- Modify: `src/ko_monitor/models.py`, `src/ko_monitor/monitor.py`, `src/ko_monitor/messages.py`
- Test: `tests/test_monitor.py`, `tests/test_messages.py`

**Interfaces:**
- Consumes: `Monitor.genie_active`, `Readings.arrow_count`, `Readings.mana_count` (Task 4).
- Produces: `EventKind.ARROW_LOW`, `EventKind.MANA_LOW`; susturma kuralı — `genie_active is False` iken `DEAD`, `INVENTORY_FULL`, `ARROW_LOW`, `MANA_LOW` olayları `notify=False` ile üretilir.

- [ ] **Step 1: Testleri yaz (başarısız olacak)**

`tests/test_monitor.py` sonuna:

```python
def low(**overrides):
    base = dict(inventory_open=True, arrow_count=5000, mana_count=5000, genie_active=True)
    base.update(overrides)
    return readings(**base)


def test_low_arrows_alert_once(m):
    events = m.observe(ok(10.0, **dict(inventory_open=True, arrow_count=900, genie_active=True)))
    assert (EventKind.ARROW_LOW, True) in kinds(events)
    # Same tick conditions a second later: no repeat inside item_low_repeat_s.
    again = m.observe(ok(12.0, **dict(inventory_open=True, arrow_count=880, genie_active=True)))
    assert EventKind.ARROW_LOW not in [e.kind for e in again]


def test_low_arrows_alert_again_after_refill(m):
    m.observe(ok(10.0, **dict(inventory_open=True, arrow_count=900, genie_active=True)))
    m.observe(ok(20.0, **dict(inventory_open=True, arrow_count=9000, genie_active=True)))
    events = m.observe(ok(30.0, **dict(inventory_open=True, arrow_count=800, genie_active=True)))
    assert (EventKind.ARROW_LOW, True) in kinds(events)


def test_low_mana_alert(m):
    events = m.observe(ok(10.0, **dict(inventory_open=True, mana_count=150, genie_active=True)))
    assert (EventKind.MANA_LOW, True) in kinds(events)


def test_item_alerts_need_a_reading(m):
    events = m.observe(ok(10.0, **dict(inventory_open=False, arrow_count=None, genie_active=True)))
    assert [e.kind for e in events if e.kind in (EventKind.ARROW_LOW, EventKind.MANA_LOW)] == []


def test_death_is_recorded_but_not_notified_while_genie_is_off():
    monitor = Monitor(T)
    monitor.observe(ok(0.0, genie_active=False))
    monitor.observe(ok(2.0, hp=0, genie_active=False))
    events = monitor.observe(ok(4.0, hp=0, genie_active=False))
    dead = [e for e in events if e.kind == EventKind.DEAD]
    assert dead and dead[0].notify is False


def test_disconnect_is_notified_even_while_genie_is_off():
    monitor = Monitor(T)
    monitor.observe(ok(0.0, genie_active=False))
    monitor.observe(ok(2.0, login_screen=True, genie_active=False, **NO_HUD))
    events = monitor.observe(ok(4.0, login_screen=True, genie_active=False, **NO_HUD))
    disconnected = [e for e in events if e.kind == EventKind.DISCONNECTED]
    assert disconnected and disconnected[0].notify is True


def test_unknown_genie_state_silences_nothing():
    monitor = Monitor(T)
    monitor.observe(ok(0.0, genie_active=None))
    monitor.observe(ok(2.0, hp=0, genie_active=None))
    events = monitor.observe(ok(4.0, hp=0, genie_active=None))
    dead = [e for e in events if e.kind == EventKind.DEAD]
    assert dead and dead[0].notify is True


def test_low_arrow_alert_is_silent_while_genie_is_off():
    monitor = Monitor(T)
    monitor.observe(ok(0.0, genie_active=False))
    events = monitor.observe(ok(10.0, **dict(inventory_open=True, arrow_count=900, genie_active=False)))
    low_events = [e for e in events if e.kind == EventKind.ARROW_LOW]
    assert low_events and low_events[0].notify is False
```

`tests/test_messages.py` sonuna:

```python
def test_item_titles():
    assert render(Event(EventKind.ARROW_LOW, 0.0, "1200"))["title"] == "🏹 Ok azaldı"
    assert render(Event(EventKind.MANA_LOW, 0.0, "180"))["title"] == "🧪 Mana potu azaldı"
```

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

```bash
.venv/Scripts/python.exe -m pytest tests/test_monitor.py tests/test_messages.py -q
```

Beklenen: FAIL — `EventKind.ARROW_LOW` yok.

- [ ] **Step 3: İki yeni olay türü ekle**

`src/ko_monitor/models.py`, `EventKind` içinde `INVENTORY_FULL` satırından sonra:

```python
    ARROW_LOW = "arrow_low"
    MANA_LOW = "mana_low"
```

- [ ] **Step 4: `monitor.py` içine susturma kuralını ve ok/pot olaylarını ekle**

Dosyanın üst kısmına, `_DETAIL_MAX` satırından sonra:

```python
# Alerts that only matter while the genie farms: when the user plays in person they see these
# themselves, and a phone that keeps buzzing during manual play gets ignored.
_SILENCED_WHEN_GENIE_OFF = {
    EventKind.DEAD,
    EventKind.INVENTORY_FULL,
    EventKind.ARROW_LOW,
    EventKind.MANA_LOW,
}
```

`__init__` içinde `self._last_inventory_alert` satırından sonra:

```python
        self._last_item_alert: dict[EventKind, float] = {}
```

`Monitor` sınıfına iki metot ekle (`_inventory_events`'in hemen üstüne):

```python
    def _notify(self, kind: EventKind) -> bool:
        """Genie off silences farm alerts; 'unknown' never silences anything."""
        return not (self.genie_active is False and kind in _SILENCED_WHEN_GENIE_OFF)

    def _item_events(self, ts: float, r: Readings) -> list[Event]:
        events = []
        for kind, count, limit in (
            (EventKind.ARROW_LOW, r.arrow_count, self._t.arrow_low),
            (EventKind.MANA_LOW, r.mana_count, self._t.mana_low),
        ):
            if count is None:
                continue
            if count >= limit:
                self._last_item_alert.pop(kind, None)  # refilled: the next drop alerts again
                continue
            last = self._last_item_alert.get(kind)
            if last is not None and ts - last < self._t.item_low_repeat_s:
                continue
            self._last_item_alert[kind] = ts
            events.append(Event(kind, ts, str(count), notify=self._notify(kind)))
        return events
```

`observe` içinde `events.extend(self._inventory_events(obs.ts, obs.readings))` satırının hemen altına:

```python
            events.extend(self._item_events(obs.ts, obs.readings))
```

`_inventory_events` içindeki son satırı susturmadan geçir:

```python
        return [Event(EventKind.INVENTORY_FULL, ts, self.zone_last or "", notify=self._notify(EventKind.INVENTORY_FULL))]
```

Ve durum geçişindeki kötü olay satırını da:

```python
                events.append(Event(_BAD_EVENTS[target], obs.ts, detail, notify=self._notify(_BAD_EVENTS[target])))
```

- [ ] **Step 5: `messages.py` içine iki başlık ekle**

`TITLES` içinde `INVENTORY_FULL` satırından sonra:

```python
    EventKind.ARROW_LOW: "🏹 Ok azaldı",
    EventKind.MANA_LOW: "🧪 Mana potu azaldı",
```

- [ ] **Step 6: Testlerin geçtiğini doğrula**

```bash
.venv/Scripts/python.exe -m pytest tests/test_monitor.py tests/test_messages.py tests/test_agent.py -q
```

Beklenen: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/ko_monitor/models.py src/ko_monitor/monitor.py src/ko_monitor/messages.py tests/test_monitor.py tests/test_messages.py
git commit -m "feat: alert on low arrows and mana, silence farm alerts while genie is off

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Kazanç hesabı ve API ucu

**Files:**
- Create: `src/ko_monitor/income.py`
- Modify: `src/ko_monitor/api.py`
- Test: `tests/test_income.py`, `tests/test_api.py`

**Interfaces:**
- Consumes: `Storage.snapshots_since(ts) -> list[Snapshot]` (mevcut), `Snapshot.money_last: int | None`.
- Produces: `hourly_income(snapshots, now, hours=24, max_jump=50_000_000) -> dict` — `{"hours": [{"start": float, "delta": int | None, "samples": int}], "avg_1h": float | None, "avg_6h": float | None, "avg_24h": float | None}`; `GET /api/income?hours=24`.

- [ ] **Step 1: Testi yaz (başarısız olacak)**

`tests/test_income.py`:

```python
from ko_monitor.income import hourly_income
from ko_monitor.models import Snapshot, State

HOUR = 3600.0


def snap(ts: float, money: int | None) -> Snapshot:
    return Snapshot(ts, State.ALIVE, 100, 100, "Ronark Land", money, 10, 28, ts)


def test_empty_history():
    out = hourly_income([], now=HOUR * 10, hours=3)
    assert [h["delta"] for h in out["hours"]] == [None, None, None]
    assert out["avg_1h"] is None and out["avg_24h"] is None


def test_one_hour_delta_is_last_minus_first():
    snaps = [snap(HOUR * 9 + 60, 1000), snap(HOUR * 9 + 1800, 1500), snap(HOUR * 9 + 3000, 2200)]
    out = hourly_income(snaps, now=HOUR * 9 + 3500, hours=1)
    assert out["hours"][0]["delta"] == 1200
    assert out["hours"][0]["samples"] == 3
    assert out["hours"][0]["start"] == HOUR * 9


def test_hours_without_data_are_null_and_excluded_from_the_average():
    snaps = [snap(HOUR * 10 + 60, 1000), snap(HOUR * 10 + 3000, 3000)]
    out = hourly_income(snaps, now=HOUR * 12 + 10, hours=3)
    deltas = [h["delta"] for h in out["hours"]]
    assert deltas == [2000, None, None]
    assert out["avg_24h"] == 2000  # the two empty hours do not drag the average down


def test_a_single_ocr_glitch_is_skipped():
    # 1000 -> 999999999 -> 2000: the middle reading is impossible, so both steps around it drop.
    snaps = [snap(HOUR * 9 + 10, 1000), snap(HOUR * 9 + 20, 999_999_999), snap(HOUR * 9 + 30, 2000)]
    out = hourly_income(snaps, now=HOUR * 9 + 40, hours=1, max_jump=50_000_000)
    assert out["hours"][0]["delta"] == 0


def test_spending_shows_as_negative():
    snaps = [snap(HOUR * 9 + 10, 5000), snap(HOUR * 9 + 20, 3000)]
    out = hourly_income(snaps, now=HOUR * 9 + 40, hours=1)
    assert out["hours"][0]["delta"] == -2000


def test_null_money_readings_are_ignored():
    snaps = [snap(HOUR * 9 + 10, None), snap(HOUR * 9 + 20, 1000), snap(HOUR * 9 + 30, 1400)]
    out = hourly_income(snaps, now=HOUR * 9 + 40, hours=1)
    assert out["hours"][0]["delta"] == 400
    assert out["hours"][0]["samples"] == 2
```

`tests/test_api.py` sonuna:

```python
def test_income_endpoint(client):
    body = client.get("/api/income?hours=3").json()
    assert len(body["hours"]) == 3
    assert {"start", "delta", "samples"} <= set(body["hours"][0])
    assert "avg_24h" in body


def test_income_hours_is_bounded(client):
    assert client.get("/api/income?hours=0").status_code == 422
    assert client.get("/api/income?hours=721").status_code == 422
```

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

```bash
.venv/Scripts/python.exe -m pytest tests/test_income.py tests/test_api.py -q
```

Beklenen: FAIL — `ko_monitor.income` modülü yok.

- [ ] **Step 3: Hesabı yaz**

`src/ko_monitor/income.py`:

```python
"""Hourly coin income, derived from the snapshots the agent already writes every minute.

An hour's income is the sum of the rises between consecutive money readings inside it. Steps
larger than max_jump are dropped: a single OCR misread of the money line would otherwise show as
a billion-coin hour. Real large purchases are dropped by the same rule - this measures farm rate,
not bookkeeping.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from ko_monitor.models import Snapshot

HOUR_S = 3600.0


def _bucket(ts: float) -> float:
    return float(int(ts // HOUR_S) * HOUR_S)


def _delta_of(values: Sequence[int], max_jump: int) -> int:
    total = 0
    for previous, current in zip(values, values[1:]):
        step = current - previous
        if abs(step) <= max_jump:
            total += step
    return total


def _average(deltas: Iterable[int | None]) -> float | None:
    known = [d for d in deltas if d is not None]
    return sum(known) / len(known) if known else None


def hourly_income(
    snapshots: Iterable[Snapshot],
    now: float,
    hours: int = 24,
    max_jump: int = 50_000_000,
) -> dict:
    """Oldest hour first. delta is None for an hour with no readings (game or bag closed)."""
    newest = _bucket(now)
    starts = [newest - HOUR_S * i for i in range(hours - 1, -1, -1)]
    grouped: dict[float, list[int]] = {start: [] for start in starts}
    for snap in snapshots:
        if snap.money_last is None:
            continue
        bucket = _bucket(snap.ts)
        if bucket in grouped:
            grouped[bucket].append(int(snap.money_last))

    rows = []
    for start in starts:
        values = grouped[start]
        rows.append({
            "start": start,
            "delta": _delta_of(values, max_jump) if len(values) >= 2 else None,
            "samples": len(values),
        })
    deltas = [row["delta"] for row in rows]
    return {
        "hours": rows,
        "avg_1h": _average(deltas[-1:]),
        "avg_6h": _average(deltas[-6:]),
        "avg_24h": _average(deltas[-24:]),
    }
```

- [ ] **Step 4: API ucunu ekle**

`src/ko_monitor/api.py` importlarına:

```python
from ko_monitor.income import HOUR_S, hourly_income
```

`get_events` ucundan sonra:

```python
    @app.get("/api/income")
    def get_income(hours: int = Query(24, ge=1, le=720)):
        current = now()
        start = (current // HOUR_S) * HOUR_S - HOUR_S * (hours - 1)
        return hourly_income(
            storage.snapshots_since(start), current, hours, cfg.thresholds.income_max_jump
        )
```

`create_app` bir `Config` almıyor, yalnızca anahtar kelimeli parametreler alıyor. `extra_hosts` satırından sonra bir parametre ekle:

```python
    extra_hosts: Sequence[str] = (),
    income_max_jump: int = 50_000_000,
```

ve uç bu parametreyi kullanır:

```python
        return hourly_income(storage.snapshots_since(start), current, hours, income_max_jump)
```

`src/ko_monitor/runtime.py:119` içindeki çağrıyı da güncelle:

```python
        app = create_app(
            storage, board, source, notifier, vapid_public_key,
            stream_quality=cfg.api.stream_quality, web_dir=web_dir,
            income_max_jump=cfg.thresholds.income_max_jump,
        )
```

- [ ] **Step 5: Testlerin geçtiğini doğrula**

```bash
.venv/Scripts/python.exe -m pytest tests/test_income.py tests/test_api.py tests/test_runtime.py -q
```

Beklenen: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ko_monitor/income.py src/ko_monitor/api.py tests/test_income.py tests/test_api.py
git commit -m "feat: serve hourly income computed from the money snapshots

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: Grafik bileşeni ve istemci tipleri

**Files:**
- Create: `frontend/src/components/IncomeChart.tsx`
- Modify: `frontend/src/types.ts`, `frontend/src/api.ts`, `frontend/src/labels.ts`, `frontend/src/styles.css`
- Test: `frontend/test/IncomeChart.test.tsx`

**Interfaces:**
- Consumes: `GET /api/income` (Task 6), `numberText` (mevcut `format.ts`), `clockText` (mevcut).
- Produces: `IncomeHour`, `Income` tipleri; `getIncome(hours?: number): Promise<Income>`; `<IncomeChart income={...} />`.

- [ ] **Step 1: Testi yaz (başarısız olacak)**

`frontend/test/IncomeChart.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { IncomeChart } from "../src/components/IncomeChart";
import type { Income } from "../src/types";

const HOUR = 3600;

function income(overrides: Partial<Income> = {}): Income {
  return {
    hours: [
      { start: HOUR * 10, delta: 12_000_000, samples: 60 },
      { start: HOUR * 11, delta: null, samples: 0 },
      { start: HOUR * 12, delta: -2_000_000, samples: 30 },
    ],
    avg_1h: -2_000_000,
    avg_6h: 5_000_000,
    avg_24h: 5_000_000,
    ...overrides,
  };
}

describe("IncomeChart", () => {
  it("draws one bar per hour", () => {
    render(<IncomeChart income={income()} />);
    expect(screen.getAllByRole("presentation")).toHaveLength(3);
  });

  it("shows the averages in tr-TR", () => {
    render(<IncomeChart income={income()} />);
    expect(screen.getByText(/5\.000\.000/)).toBeInTheDocument();
  });

  it("marks hours without data", () => {
    render(<IncomeChart income={income()} />);
    expect(screen.getByTitle(/veri yok/i)).toBeInTheDocument();
  });

  it("renders an empty history without crashing", () => {
    render(<IncomeChart income={income({ hours: [], avg_1h: null, avg_6h: null, avg_24h: null })} />);
    expect(screen.getByText(/Kazanç/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

```bash
cd frontend && npx vitest run IncomeChart
```

Beklenen: FAIL — bileşen yok.

- [ ] **Step 3: Tipleri ve istemciyi ekle**

`frontend/src/types.ts` sonuna:

```ts
/** One hour of GET /api/income; delta null = no reading in that hour. */
export interface IncomeHour {
  start: number;
  delta: number | null;
  samples: number;
}

/** GET /api/income?hours=N (oldest hour first). */
export interface Income {
  hours: IncomeHour[];
  avg_1h: number | null;
  avg_6h: number | null;
  avg_24h: number | null;
}
```

Aynı dosyadaki `EventKind` birleşimine iki değer ekle: `| "arrow_low" | "mana_low"`.

`AgentStatus` arayüzüne üç alan ekle:

```ts
  arrow_last: number | null;
  mana_last: number | null;
  genie_active: boolean | null;
```

Bu alanlar zorunlu olduğu için `frontend/test/fakes.ts` içindeki `agentStatus()` üreticisi
tip denetiminden geçmez hale gelir. Aynı adımda oradaki varsayılan nesneye ekle:

```ts
    arrow_last: null,
    mana_last: null,
    genie_active: null,
```

`frontend/src/api.ts` sonuna:

```ts
export const getIncome = (hours = 24) => request<Income>(`/api/income?hours=${hours}`);
```

(`Income` tipini dosyanın başındaki import listesine ekle.)

`frontend/src/labels.ts` içindeki `EVENT_LABELS`'a — `messages.py` ile birebir aynı:

```ts
  arrow_low: "🏹 Ok azaldı",
  mana_low: "🧪 Mana potu azaldı",
```

- [ ] **Step 4: Bileşeni yaz**

`frontend/src/components/IncomeChart.tsx`:

```tsx
import { clockText, numberText } from "../format";
import type { Income } from "../types";

const HEIGHT = 90;
const GAP = 2;

/** Hourly coin income. Bars are drawn against the largest absolute hour so a quiet day still reads. */
export function IncomeChart({ income }: { income: Income }) {
  const { hours } = income;
  const scale = Math.max(1, ...hours.map((h) => Math.abs(h.delta ?? 0)));
  const width = 100 / Math.max(1, hours.length);
  return (
    <section className="card">
      <h2>Kazanç (son {hours.length} saat)</h2>
      <div className="income" style={{ height: HEIGHT }}>
        {hours.map((hour) => {
          const value = hour.delta;
          const ratio = value === null ? 1 : Math.abs(value) / scale;
          const tone = value === null ? "none" : value >= 0 ? "pos" : "neg";
          const title =
            value === null
              ? `${clockText(hour.start)}: veri yok`
              : `${clockText(hour.start)}: ${numberText(value)}`;
          return (
            <span
              key={hour.start}
              role="presentation"
              className={`bar bar-${tone}`}
              title={title}
              style={{
                width: `calc(${width}% - ${GAP}px)`,
                height: `${Math.max(2, ratio * HEIGHT)}px`,
              }}
            />
          );
        })}
      </div>
      <p className="meta">
        Saatlik ortalama — 1 sa: {numberText(income.avg_1h && Math.round(income.avg_1h))} · 6 sa:{" "}
        {numberText(income.avg_6h && Math.round(income.avg_6h))} · 24 sa:{" "}
        {numberText(income.avg_24h && Math.round(income.avg_24h))}
      </p>
    </section>
  );
}
```

- [ ] **Step 5: Stilleri ekle**

`frontend/src/styles.css` sonuna:

```css
.income { display: flex; align-items: flex-end; gap: 2px; margin: 10px 0 4px; }
.income .bar { display: block; border-radius: 3px 3px 0 0; }
.income .bar-pos { background: #3fb950; }
.income .bar-neg { background: #f85149; }
.income .bar-none { background: var(--line); opacity: 0.5; }
```

- [ ] **Step 6: Testlerin geçtiğini doğrula**

```bash
cd frontend && npx vitest run
```

Beklenen: Tüm testler geçer (70 mevcut + 4 yeni).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/IncomeChart.tsx frontend/src/types.ts frontend/src/api.ts frontend/src/labels.ts frontend/src/styles.css frontend/test/IncomeChart.test.tsx
git commit -m "feat: add the hourly income chart component

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: Ekran bağlantıları ve derleme

**Files:**
- Modify: `frontend/src/screens/Events.tsx`, `frontend/src/screens/Status.tsx`, `frontend/src/components/InventoryCard.tsx`
- Test: `frontend/test/Events.test.tsx`, `frontend/test/Status.test.tsx`, `tests/test_web.py`
- Modify: `web/` (derleme çıktısı)

**Interfaces:**
- Consumes: `getIncome` ve `<IncomeChart />` (Task 7), `AgentStatus.arrow_last/mana_last/genie_active` (Task 4).

- [ ] **Step 1: Testleri yaz (başarısız olacak)**

`frontend/test/Events.test.tsx` içine, mevcut fake API'ye `getIncome` ekleyerek:

```tsx
it("shows the income chart above the event list", async () => {
  render(<Events />);
  expect(await screen.findByText(/Kazanç/)).toBeInTheDocument();
});
```

`frontend/test/Status.test.tsx` içine:

```tsx
it("shows arrow and mana counts and the genie state", async () => {
  render(<Status />);
  expect(await screen.findByText(/6\.380/)).toBeInTheDocument();
  expect(screen.getByText(/4\.150/)).toBeInTheDocument();
  expect(screen.getByText(/Genie çalışıyor/)).toBeInTheDocument();
});
```

Ekranlar `fetch`'i `stubFetch(routes)` ile sahteler, yani yeni uç de route tablosuna girer.
`frontend/test/fakes.ts` içine bir üretici ekle:

```ts
export function income(overrides: Partial<Income> = {}): Income {
  return { hours: [{ start: 3600, delta: 1000, samples: 60 }], avg_1h: 1000, avg_6h: 1000, avg_24h: 1000, ...overrides };
}
```

Events testinde route tablosuna `"/api/income?hours=24": income()`, Status testinde ise
`agentStatus({ arrow_last: 6380, mana_last: 4150, genie_active: true })` kullanılır.

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

```bash
cd frontend && npx vitest run Events Status
```

Beklenen: FAIL.

- [ ] **Step 3: Olaylar ekranına grafiği ekle**

`frontend/src/screens/Events.tsx`:

```tsx
import { getEvents, getIncome, getSnapshots } from "../api";
import { IncomeChart } from "../components/IncomeChart";
```

`loadEvents` içinde:

```tsx
  const [events, snapshots, income] = await Promise.all([
    getEvents(100),
    getSnapshots(clientNow - DAY_S),
    getIncome(24),
  ]);
  return { events, snapshots, income, ...timelineWindow(snapshots, clientNow) };
```

ve `Timeline`'ın **üstüne**:

```tsx
          <IncomeChart income={data.income} />
```

- [ ] **Step 4: Durum ekranına ok/pot ve Genie satırını ekle**

`frontend/src/components/InventoryCard.tsx` içine, mevcut slot satırının altına (bileşenin aldığı `status` nesnesinden):

```tsx
      <p className="meta">
        Ok: {numberText(status.arrow_last)} · Pot: {numberText(status.mana_last)}
      </p>
      <p className="meta">
        {status.genie_active === null
          ? "Genie durumu bilinmiyor"
          : status.genie_active
            ? "Genie çalışıyor"
            : "Genie durdu — bildirimler susturuldu"}
      </p>
```

`InventoryCard` zaten `{ status }: { status: AgentStatus }` alıyor ve `Status.tsx` ona tam
durumu geçiyor; imza değişmez, yalnızca `</dl>` ile `</section>` arasına bu iki satır girer.

- [ ] **Step 5: Testlerin geçtiğini doğrula**

```bash
cd frontend && npx vitest run && npx tsc -p tsconfig.json --noEmit && npx tsc -p tsconfig.sw.json --noEmit
```

Beklenen: tüm testler geçer, iki tip denetimi de temiz.

- [ ] **Step 6: PWA'yı derle ve Python tarafını doğrula**

```bash
cd frontend && npm run build
```

```bash
.venv/Scripts/python.exe -m pytest -q
```

Beklenen: `web/` yeniden üretilir; Python testlerinin tamamı geçer (304 + bu planın eklediği testler).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/screens/Events.tsx frontend/src/screens/Status.tsx frontend/src/components/InventoryCard.tsx frontend/test web
git commit -m "feat: show income, arrow and mana counts in the phone app

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Uygulama sonrası canlı doğrulama (kullanıcıyla)

Kod tamamlandıktan sonra, ajan yeniden başlatılıp şunlar gerçek oyunla doğrulanır:

1. `/api/status` içinde `arrow_last`, `mana_last` ve `genie_active` gerçek değerleri gösteriyor.
2. Kullanıcı Genie'yi durdurduğunda `genie_active` iki tick içinde `false` oluyor.
3. `/api/income` son saatler için makul kazanç veriyor (ölçülen ~12 milyon/saat).
4. Telefonda Olaylar ekranının üstünde grafik çiziliyor.
5. Eşikler gerçek tüketimle tutuyor mu: ok ~1790/saat, pot ~311/saat.
