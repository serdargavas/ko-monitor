# KO Monitor – PWA'nın React + Vite + TypeScript'e taşınması Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `web/` altındaki elle yazılmış vanilla JS PWA'yı (Durum · Canlı · Olaylar · Ayarlar), kullanıcı açısından hiçbir şey değiştirmeden, `frontend/` altında React 19 + Vite 8 + TypeScript kaynağına taşımak; `npm run build` çıktısı `web/`'e yazılır ve commit edilir.

**Architecture:** Kaynak `frontend/` (yaklaşım A). Vite `build.outDir = "../web"` + `emptyOutDir`; FastAPI `web/`'i değişmeden sunar, oyun PC'sinde çalışmak için Node gerekmez. Yönlendirme `useHashRoute` (router kütüphanesi yok), durum yönetimi React state + küçük hook'lar (`usePolling`, `useStream`, `useVisibility`). Service worker `src/sw.ts` bizim kodumuz; `vite-plugin-pwa` `injectManifest` modu yalnızca derleme dosya listesini (`self.__WB_MANIFEST`) enjekte eder ve `/sw.js` olarak kök dizine yazar; `workbox-precaching` önbelleği sürümler, ağ-öncelikli/zaman aşımı/push/notificationclick mantığı bizde kalır.

**Tech Stack:** Node.js 24.19.0 / npm 11.17.0; react 19.3.0, react-dom 19.3.0, workbox-core 7.4.1, workbox-precaching 7.4.1; geliştirme: vite 8.3.0, @vitejs/plugin-react 6.1.1, vite-plugin-pwa 1.3.0, typescript 7.0.2, @types/react 19.3.0, @types/react-dom 19.3.0, vitest 5.0.1, jsdom 30.0.1, @testing-library/react 16.3.3, @testing-library/dom 10.4.2. Python tarafı değişmez (pytest + FastAPI `TestClient`).

**Spec:** `docs/superpowers/specs/2026-09-15-ko-monitor-react-pwa-design.md` (üst spec: `docs/superpowers/specs/2026-09-15-ko-monitor-design.md` §7)

**Uyumluluk doğrulaması (plan yazılırken, 2026-09-15):** `npm view` peer aralıkları: vite-plugin-pwa 1.3.0 → `vite ^3 … ^8.0.0`; @vitejs/plugin-react 6.1.1 → `vite ^8.0.0`; vitest 5.0.1 → `vite ^6.4.0 || ^7 || ^8`, node `^22.12 || ^24`; jsdom 30.0.1 → node `^24.15.0`; @testing-library/react 16.3.3 → react/@types ^19. Geçici bir projede bu planın **tam kodu** (Task 1–8'deki tüm dosyalar) kuruldu: `npm install` peer uyarısız, `npm run build` (iki `tsc` + `vite build`) başarılı, çıktı kökünde `sw.js` + precache listesi (7 giriş) oluştu, iki ardışık derleme bayt bayt aynı, `npm test` 13 dosya / 61 test geçti, Task 8'deki `tests/test_web.py` bu çıktıya karşı geçti, dev proxy'nin HTTP ve WebSocket upgrade isteklerinde `Host` ve `Origin` başlıklarını hedefe çevirdiği sahte bir sunucuyla doğrulandı. Spec'teki "vite-plugin-pwa uyumsuzsa derleme sonrası betik" yedeğine **gerek yok**.

## Global Constraints

- Salt okuma projesi: oyuna tuş/tıklama, bellek okuma, paket dinleme YASAK. Bu plan yalnızca telefon arayüzünü taşır; API/sunucu kodu (`src/ko_monitor/*`) değişmez.
- Kullanıcı açısından davranış değişmez: aynı dört ekran, aynı Türkçe metinler (bu plandaki kodlarda birebir), aynı API, aynı push payload'u (`messages.render()`: `title`, `body`, `url`, `kind`, `ts`), `url: "/#/events"` hash rotası.
- Kod ve kod yorumları İngilizce; kullanıcıya görünen metinler (arayüz, `docs/setup.md`) Türkçe. iPhone öncelikli (mevcut `styles.css` birebir taşınır).
- Komutlar PowerShell'de proje kökünden (`C:\Users\Serdar\Desktop\ko-monitor`) çalışır; `cd frontend` diyen adımlar `frontend\` içinde çalışır. Node yeni kurulduğu için yeni bir PowerShell'de `npm` bulunamazsa önce: `$env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [System.Environment]::GetEnvironmentVariable('Path','User')`
- Python: `.venv\Scripts\python.exe -m pytest -q` (başlangıç: 306 passed, 2 skipped). `tests/test_api.py` ve `tests/test_stream.py` değiştirilmez ve geçmeye devam eder.
- Tüm npm sürümleri `package.json`'da **tam** (^/~ yok) sabitlenir; `frontend/package-lock.json` commit edilir; `frontend/node_modules/` `.gitignore`'a eklenir.
- `web/` yalnızca `npm run build` ile üretilir, elle düzenlenmez; derlenmiş `web/` commit edilir. Service worker `/sw.js` (kapsam `/`), manifest `/manifest.webmanifest`, ikonlar `/icons/icon-{180,192,512}.png`, `index.html`'de `apple-touch-icon` bağlantısı korunur.
- Yasaklar: router/state/UI kütüphanesi; `dangerouslySetInnerHTML` ve `innerHTML` (test ile denetlenir); çalışma zamanında CDN ya da başka bir host'tan kaynak (`vite.config.ts` dahil).
- `npm test` = `vitest run` (etkileşimsiz). Testler Vitest + @testing-library/react + jsdom; zamanlayıcılar `vi.useFakeTimers()`, WebSocket `FakeWebSocket`, ağ `stubFetch` ile sahtelenir.
- Canlı süreç: `python -m ko_monitor run` 127.0.0.1:8765'te çalışıyor olabilir — durdurma, 8765'i bağlama, `snap`/`record`/`run` çalıştırma. (Task 8'deki derleme `web/`'i değiştirir; çalışan sunucu yeni dosyaları hemen sunar — beklenen durumdur.)
- Yerel dosyalar git'e girmez: `config.toml`, `data/`, `logs/`, `.venv/`, `.superpowers/`, `samples/_auto/`, `samples/_review/`, `frontend/node_modules/`. `git add` her zaman açık yollarla yapılır (`git add .` / `git add -A` YASAK).
- Git kimliği: `git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "<subject>" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"`. Çalışma dalı `feat/react-pwa`.

## File Structure

```
ko-monitor/
  .gitignore                          # + frontend/node_modules/
  scripts/make_icons.py               # ICON_DIR → frontend/public/icons
  docs/setup.md                       # + "Arayüzü değiştirmek (geliştirici)" bölümü
  docs/superpowers/specs/2026-09-15-ko-monitor-design.md   # §2/§3 vanilla JS notu → React taşıma spec'ine işaret
  tests/test_web.py                   # derlenmiş web/ çıktısını doğrular (yeniden yazılır)
  frontend/
    package.json package-lock.json    # exact pins; scripts dev/typecheck/build/test
    tsconfig.json                     # app + tests (DOM lib), excludes src/sw.ts
    tsconfig.sw.json                  # src/sw.ts + src/swHelpers.ts (WebWorker lib)
    vite.config.ts                    # react + VitePWA(injectManifest), outDir ../web, dev proxy /api (+ws)
    vitest.config.ts                  # jsdom, test/setup.ts; no PWA plugin
    index.html                        # same head as web/index.html, <div id="root">, /src/main.tsx
    public/manifest.webmanifest       # copied verbatim from web/
    public/icons/icon-180.png icon-192.png icon-512.png
    src/
      main.tsx                        # createRoot, /sw.js registration (prod), sw "navigate" messages
      App.tsx                         # hash route → screen, document.title, TabBar
      types.ts                        # AgentStatus, Readings, Snapshot, EventItem, PushTestResult, StreamStatus, Quality, State, EventKind
      labels.ts                       # STATE_LABELS, EVENT_LABELS (= messages.TITLES), stateLabel, eventLabel
      format.ts                       # agoText, clockText, dateTimeText, numberText, unreachableText
      api.ts                          # ApiError, getStatus, getSnapshots, getEvents, getVapidKey, subscribe, sendTest, streamUrl
      timeline.ts                     # DAY_S, MAX_GAP_S, buildSegments, timelineWindow
      quality.ts                      # QUALITIES, QUALITY_STORAGE_KEY, loadQuality, saveQuality
      push.ts                         # SW_READY_TIMEOUT_MS, base64UrlToBytes, isStandalone, pushSupported, serviceWorkerReady, enableNotifications
      swHelpers.ts                    # pure sw helpers: classifyRequest, parsePushPayload, notificationOptions, notificationTarget, staleCaches
      sw.ts                           # service worker (precache, network-first 3 s, push, notificationclick, cache cleanup)
      styles.css                      # copied verbatim from web/styles.css
      hooks/useVisibility.ts usePolling.ts useStream.ts useHashRoute.ts
      components/StateBadge.tsx HpBar.tsx InventoryCard.tsx EventList.tsx Timeline.tsx TabBar.tsx
      screens/Status.tsx Live.tsx Events.tsx Settings.tsx
    test/
      setup.ts fakes.ts
      format.test.ts api.test.ts timeline.test.ts usePolling.test.tsx useStream.test.tsx
      Status.test.tsx Events.test.tsx push.test.ts Settings.test.tsx Live.test.tsx
      App.test.tsx security.test.ts swHelpers.test.ts
  web/                                # npm run build output (committed; old js/, styles.css, hand-written sw.js removed)
```

---

### Task 1: `frontend/` iskeleti, tipler, etiketler, biçimlendirme, API istemcisi ve zaman çizelgesi

**Files:**
- Create: `frontend/package.json`, `frontend/package-lock.json` (npm üretir), `frontend/tsconfig.json`, `frontend/tsconfig.sw.json`, `frontend/vite.config.ts`, `frontend/vitest.config.ts`, `frontend/index.html`, `frontend/public/manifest.webmanifest`, `frontend/public/icons/*.png`, `frontend/src/styles.css`, `frontend/src/types.ts`, `frontend/src/labels.ts`, `frontend/src/format.ts`, `frontend/src/api.ts`, `frontend/src/timeline.ts`
- Modify: `.gitignore`, `scripts/make_icons.py:1,14`, `tests/test_web.py` (ikon betiği testi)
- Test: `frontend/test/setup.ts`, `frontend/test/fakes.ts`, `frontend/test/format.test.ts`, `frontend/test/api.test.ts`, `frontend/test/timeline.test.ts`

**Interfaces:**
- Consumes: sunucu yanıtları — `GET /api/status` = `{"server_time", **AgentStatus.to_dict()}` (`status.py`), `GET /api/snapshots` satırları (`models.Snapshot`, `state` string), `GET /api/events` satırları `{id, ts, kind, detail, notified, notified_at}` (`storage.recent_events`), `POST /api/push/test` → `{delivered, subscriptions}`, `GET /api/push/vapid-key` → `{key}`; `messages.TITLES`.
- Produces:
  - `types.ts`: `State`, `EventKind`, `Readings {hp, hp_max, …}`, `AgentStatus`, `Snapshot`, `EventItem`, `PushTestResult`, `StreamStatus`, `Quality = "low" | "medium" | "high"`.
  - `labels.ts`: `Tone`, `StateLabel {text, tone}`, `STATE_LABELS`, `EVENT_LABELS`, `stateLabel(state: string | null | undefined): StateLabel`, `eventLabel(kind: string): string`.
  - `format.ts`: `agoText(seconds: number | null | undefined): string`, `clockText(ts: number): string`, `dateTimeText(ts: number): string`, `unreachableText(error: Error): string`, `numberText(value: number | null | undefined): string`.
  - `api.ts`: `class ApiError(status, message)`, `getStatus(): Promise<AgentStatus>`, `getEvents(limit = 50): Promise<EventItem[]>`, `getSnapshots(since: number): Promise<Snapshot[]>`, `getVapidKey(): Promise<{key: string}>`, `sendTest(): Promise<PushTestResult>`, `subscribe(subscription: PushSubscriptionJSON): Promise<{ok: boolean}>`, `streamUrl(quality: Quality | null): string`.
  - `timeline.ts`: `DAY_S = 86400`, `MAX_GAP_S = 90`, `Segment {from, to, state}`, `buildSegments(snapshots, start, end, maxGapS = MAX_GAP_S): Segment[]`, `timelineWindow(snapshots, clientNow): {start, end}`.
  - `test/fakes.ts` (sonraki tüm görevler kullanır): `FakeWebSocket` (static `instances`, `last()`, `url`, `binaryType`, `closed`, `close()`, `receive(data)`, `serverClose(code = 1006, reason = "")`), `installStreamFakes(): {createObjectURL, revokeObjectURL}` (URL'ler `blob:frame-1`, `blob:frame-2`, …), `setHidden(hidden: boolean)`, `stubFetch(routes: Record<string, unknown>)` (önek eşleşmesi, `Error` değeri → fetch reddeder, bilinmeyen yol → 404), `snapshot(ts, state)`, `agentStatus(overrides?)`, `eventItem(id, kind, ts, detail = "")`.
  - `package.json` script'leri: `dev`, `typecheck` (`tsc -p tsconfig.json && tsc -p tsconfig.sw.json`), `build` (`npm run typecheck && vite build`), `test` (`vitest run`).

- [ ] **Step 1: `.gitignore` ve npm projesi**

`.gitignore` sonuna ekle:
```
frontend/node_modules/
```

`frontend/package.json`:
```json
{
  "name": "ko-monitor-frontend",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "typecheck": "tsc -p tsconfig.json && tsc -p tsconfig.sw.json",
    "build": "npm run typecheck && vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "19.3.0",
    "react-dom": "19.3.0",
    "workbox-core": "7.4.1",
    "workbox-precaching": "7.4.1"
  },
  "devDependencies": {
    "@testing-library/dom": "10.4.2",
    "@testing-library/react": "16.3.3",
    "@types/react": "19.3.0",
    "@types/react-dom": "19.3.0",
    "@vitejs/plugin-react": "6.1.1",
    "jsdom": "30.0.1",
    "typescript": "7.0.2",
    "vite": "8.3.0",
    "vite-plugin-pwa": "1.3.0",
    "vitest": "5.0.1"
  }
}
```

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true,
    "isolatedModules": true,
    "skipLibCheck": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "types": ["vite/client"]
  },
  "include": ["src", "test"],
  "exclude": ["src/sw.ts"]
}
```

`frontend/tsconfig.sw.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "WebWorker"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "noEmit": true,
    "isolatedModules": true,
    "skipLibCheck": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "types": []
  },
  "include": ["src/sw.ts", "src/swHelpers.ts"]
}
```

`frontend/vite.config.ts`:
```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// The FastAPI server started with `python -m ko_monitor run`.
const API_TARGET = "http://127.0.0.1:8765";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      // Our own service worker (src/sw.ts); the plugin only injects the precache file list.
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw.ts",
      injectRegister: false, // src/main.tsx registers /sw.js itself
      manifest: false, // public/manifest.webmanifest is copied as is
      injectManifest: {
        globPatterns: ["**/*.{html,js,css,png,webmanifest}"],
      },
      devOptions: { enabled: false },
    }),
  ],
  build: {
    // FastAPI serves web/ unchanged; the build output is committed.
    outDir: "../web",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": {
        target: API_TARGET,
        ws: true, // WS /api/stream
        // The server checks Host (TrustedHostMiddleware) and Origin == Host (POSTs, WebSocket).
        changeOrigin: true,
        headers: { origin: API_TARGET },
      },
    },
  },
});
```

`frontend/vitest.config.ts`:
```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Separate from vite.config.ts so tests never run the PWA plugin or touch ../web.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    include: ["test/**/*.test.{ts,tsx}"],
    setupFiles: ["test/setup.ts"],
    restoreMocks: true,
    unstubGlobals: true,
  },
});
```

`frontend/index.html` (baş kısmı `web/index.html` ile aynı; stil `main.tsx` içinden gelir, `src/main.tsx` Task 7'de yazılır):
```html
<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#0f1115">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="KO Monitor">
  <title>KO Monitor</title>
  <link rel="manifest" href="/manifest.webmanifest">
  <link rel="apple-touch-icon" href="/icons/icon-180.png">
  <link rel="icon" type="image/png" href="/icons/icon-192.png">
  <script type="module" src="/src/main.tsx"></script>
</head>
<body>
  <div id="root"></div>
</body>
</html>
```

- [ ] **Step 2: Statik dosyaları kopyala, ikon betiğini `frontend/public/icons`'a yönlendir, paketleri kur**

`web/` bu görevde değişmez (Task 8'e kadar eski uygulama çalışmaya devam eder):
```powershell
New-Item -ItemType Directory -Force frontend\public\icons, frontend\src, frontend\test | Out-Null
Copy-Item web\icons\icon-180.png, web\icons\icon-192.png, web\icons\icon-512.png frontend\public\icons\
Copy-Item web\manifest.webmanifest frontend\public\manifest.webmanifest
Copy-Item web\styles.css frontend\src\styles.css
```

`scripts/make_icons.py` içinde:
```python
"""Generates the PWA icons in web/icons with OpenCV, so the repo needs no external image assets.
```
yerine:
```python
"""Generates the PWA icons in frontend/public/icons with OpenCV (npm run build copies them to web/icons).
```
ve:
```python
ICON_DIR = ROOT / "web" / "icons"
```
yerine:
```python
ICON_DIR = ROOT / "frontend" / "public" / "icons"
```

`tests/test_web.py` içindeki `test_icon_script_draws_opaque_square_icons` fonksiyonunda:
```python
    icon = module.render_icon(64)
```
yerine:
```python
    assert module.ICON_DIR == ROOT / "frontend" / "public" / "icons"
    icon = module.render_icon(64)
```

```powershell
cd frontend
npm install --no-audit --no-fund
npm ls --depth=0
```
Expected: `added 412 packages` (sayı küçük farklılık gösterebilir; tek uyarı `npm warn deprecated glob@11.1.0`, peer hatası yok). `npm ls` çıktısında tam olarak: `@testing-library/dom@10.4.2`, `@testing-library/react@16.3.3`, `@types/react-dom@19.3.0`, `@types/react@19.3.0`, `@vitejs/plugin-react@6.1.1`, `jsdom@30.0.1`, `react-dom@19.3.0`, `react@19.3.0`, `typescript@7.0.2`, `vite-plugin-pwa@1.3.0`, `vite@8.3.0`, `vitest@5.0.1`, `workbox-core@7.4.1`, `workbox-precaching@7.4.1`. `frontend/package-lock.json` oluşur.

Run (kökten): `.venv\Scripts\python.exe -m pytest tests/test_web.py -q`
Expected: `26 passed`

- [ ] **Step 3: Tipler ve test altyapısı**

`frontend/src/types.ts`:
```ts
// Response shapes of the FastAPI server (src/ko_monitor/api.py, status.py, storage.py, stream.py).

export type State = "closed" | "alive" | "dead" | "disconnected" | "frozen" | "blind";

export type EventKind =
  | "game_started"
  | "game_closed"
  | "dead"
  | "disconnected"
  | "frozen"
  | "blind"
  | "recovered"
  | "inventory_full"
  | "test";

/** dataclasses.asdict(Readings); only the fields the PWA shows are typed. */
export interface Readings {
  hp: number | null;
  hp_max: number | null;
  [field: string]: unknown;
}

/** GET /api/status: {"server_time": now(), **AgentStatus.to_dict()} */
export interface AgentStatus {
  server_time: number;
  updated_at: number | null;
  state: State | null;
  process_running: boolean;
  capture: string | null;
  readings: Readings | null;
  zone_last: string | null;
  money_last: number | null;
  slots_used_last: number | null;
  slots_total_last: number | null;
  inventory_seen_at: number | null;
}

/** One row of GET /api/snapshots (oldest first). */
export interface Snapshot {
  ts: number;
  state: State;
  hp: number | null;
  hp_max: number | null;
  zone: string | null;
  money_last: number | null;
  slots_used_last: number | null;
  slots_total_last: number | null;
  inventory_seen_at: number | null;
}

/** One row of GET /api/events (newest first). */
export interface EventItem {
  id: number;
  ts: number;
  kind: EventKind | string;
  detail: string;
  notified: boolean;
  notified_at: number | null;
}

/** POST /api/push/test */
export interface PushTestResult {
  delivered: boolean;
  subscriptions: number;
}

/** Text message of WS /api/stream; binary messages are JPEG frames. */
export type StreamStatus = "ok" | "minimized" | "not_found" | "black";

export type Quality = "low" | "medium" | "high";
```

`frontend/test/setup.ts`:
```ts
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  // setHidden() shadows Document.prototype.hidden on the instance; drop it again.
  Reflect.deleteProperty(document, "hidden");
  Reflect.deleteProperty(navigator, "serviceWorker");
  localStorage.clear();
  window.location.hash = "";
});
```

`frontend/test/fakes.ts`:
```ts
import { vi } from "vitest";
import type { AgentStatus, EventItem, Snapshot, State } from "../src/types";

/** Stands in for the browser WebSocket; tests drive it with receive() and serverClose(). */
export class FakeWebSocket {
  static instances: FakeWebSocket[] = [];

  readonly url: string;
  binaryType = "blob";
  closed = false;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  onclose: ((event: { code: number; reason: string }) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  static last(): FakeWebSocket {
    return FakeWebSocket.instances[FakeWebSocket.instances.length - 1];
  }

  /** Client-side close; like a real socket, onclose still fires later (see serverClose). */
  close(): void {
    this.closed = true;
  }

  receive(data: unknown): void {
    this.onmessage?.({ data });
  }

  serverClose(code = 1006, reason = ""): void {
    this.onclose?.({ code, reason });
  }
}

/** Installs FakeWebSocket and counting URL.createObjectURL / revokeObjectURL stubs. */
export function installStreamFakes() {
  FakeWebSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket);
  let next = 0;
  const createObjectURL = vi.fn(() => `blob:frame-${++next}`);
  const revokeObjectURL = vi.fn();
  Object.defineProperty(URL, "createObjectURL", { configurable: true, writable: true, value: createObjectURL });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, writable: true, value: revokeObjectURL });
  return { createObjectURL, revokeObjectURL };
}

/** Sets document.hidden and fires visibilitychange (wrap in act() while something is rendered). */
export function setHidden(hidden: boolean): void {
  Object.defineProperty(document, "hidden", { configurable: true, get: () => hidden });
  document.dispatchEvent(new Event("visibilitychange"));
}

/**
 * Replaces fetch: the first route whose key is a prefix of the requested path answers with its
 * value as JSON; an Error value makes fetch reject; unknown paths get 404. Routes are read on
 * every call, so tests may change them between calls.
 */
export function stubFetch(routes: Record<string, unknown>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
    const path = String(input);
    const key = Object.keys(routes).find((prefix) => path.startsWith(prefix));
    if (key === undefined) return new Response("not found", { status: 404 });
    const body = routes[key];
    if (body instanceof Error) throw body;
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export function snapshot(ts: number, state: State): Snapshot {
  return {
    ts,
    state,
    hp: null,
    hp_max: null,
    zone: null,
    money_last: null,
    slots_used_last: null,
    slots_total_last: null,
    inventory_seen_at: null,
  };
}

export function agentStatus(overrides: Partial<AgentStatus> = {}): AgentStatus {
  return {
    server_time: 1_000_000,
    updated_at: 999_990,
    state: "alive",
    process_running: true,
    capture: "ok",
    readings: { hp: 9718, hp_max: 9996 },
    zone_last: "Moradon",
    money_last: 1234567,
    slots_used_last: 20,
    slots_total_last: 28,
    inventory_seen_at: 999_700,
    ...overrides,
  };
}

export function eventItem(id: number, kind: string, ts: number, detail = ""): EventItem {
  return { id, ts, kind, detail, notified: true, notified_at: ts };
}
```

- [ ] **Step 4: Failing testleri yaz**

`frontend/test/format.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { agoText, clockText, dateTimeText, numberText, unreachableText } from "../src/format";
import { EVENT_LABELS, eventLabel, STATE_LABELS, stateLabel } from "../src/labels";

describe("format", () => {
  it("groups money with dots like tr-TR", () => {
    expect(numberText(1234567)).toBe("1.234.567");
    expect(numberText(0)).toBe("0");
  });

  it("shows missing numbers as —", () => {
    expect(numberText(null)).toBe("—");
    expect(numberText(undefined)).toBe("—");
  });

  it("says how long ago in seconds, minutes, hours and days", () => {
    expect(agoText(0)).toBe("0 sn önce");
    expect(agoText(59.4)).toBe("59 sn önce");
    expect(agoText(-5)).toBe("0 sn önce");
    expect(agoText(125)).toBe("2 dk önce");
    expect(agoText(7200)).toBe("2 sa önce");
    expect(agoText(90000)).toBe("1 gün önce");
    expect(agoText(null)).toBe("hiç");
  });

  it("formats clock and date times with two digits", () => {
    expect(clockText(1_700_000_000)).toMatch(/^\d{2}:\d{2}$/);
    expect(dateTimeText(1_700_000_000)).toMatch(/^\d{2}[./]\d{2} \d{2}:\d{2}$/);
  });

  it("names the unreachable PC in Turkish", () => {
    expect(unreachableText(new Error("Failed to fetch"))).toBe(
      "Bilgisayara ulaşılamıyor (Tailscale açık mı?): Failed to fetch",
    );
  });
});

describe("labels", () => {
  it("covers every state and event kind of the server", () => {
    expect(Object.keys(STATE_LABELS).sort()).toEqual(["alive", "blind", "closed", "dead", "disconnected", "frozen"]);
    expect(Object.keys(EVENT_LABELS).sort()).toEqual([
      "blind",
      "dead",
      "disconnected",
      "frozen",
      "game_closed",
      "game_started",
      "inventory_full",
      "recovered",
      "test",
    ]);
  });

  it("falls back for unknown values", () => {
    expect(stateLabel(null)).toEqual({ text: "Bilinmiyor", tone: "off" });
    expect(stateLabel("dead")).toEqual({ text: "Ölü", tone: "bad" });
    expect(eventLabel("test")).toBe("🔔 Test bildirimi");
    expect(eventLabel("something_new")).toBe("something_new");
  });
});
```

`frontend/test/api.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { ApiError, getEvents, getSnapshots, sendTest, streamUrl, subscribe } from "../src/api";
import { stubFetch } from "./fakes";

describe("api", () => {
  it("asks for fresh JSON", async () => {
    const fetchMock = stubFetch({ "/api/events": [] });
    await expect(getEvents(5)).resolves.toEqual([]);
    expect(fetchMock).toHaveBeenCalledWith("/api/events?limit=5", { cache: "no-store" });
  });

  it("passes the snapshot start as since", async () => {
    const fetchMock = stubFetch({ "/api/snapshots": [] });
    await getSnapshots(1234.5);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/snapshots?since=1234.5");
  });

  it("throws ApiError with the HTTP status", async () => {
    stubFetch({});
    const error = await getEvents().catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(404);
    expect((error as ApiError).message).toBe("/api/events?limit=50: HTTP 404");
  });

  it("posts the subscription as JSON and the test push without a body", async () => {
    const fetchMock = stubFetch({ "/api/push/subscribe": { ok: true }, "/api/push/test": { delivered: true, subscriptions: 1 } });
    const subscription = { endpoint: "https://web.push.apple.com/x", keys: { p256dh: "p", auth: "a" } };
    await subscribe(subscription);
    expect(fetchMock).toHaveBeenCalledWith("/api/push/subscribe", {
      cache: "no-store",
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(subscription),
    });
    await expect(sendTest()).resolves.toEqual({ delivered: true, subscriptions: 1 });
    expect(fetchMock).toHaveBeenLastCalledWith("/api/push/test", { cache: "no-store", method: "POST" });
  });

  it("builds the stream URL from the page address", () => {
    expect(streamUrl(null)).toBe(`ws://${location.host}/api/stream`);
    expect(streamUrl("high")).toBe(`ws://${location.host}/api/stream?quality=high`);
  });
});
```

`frontend/test/timeline.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import { buildSegments, DAY_S, timelineWindow } from "../src/timeline";
import { snapshot } from "./fakes";

describe("buildSegments", () => {
  it("returns no segments for no snapshots", () => {
    expect(buildSegments([], 0, 1000)).toEqual([]);
  });

  it("merges consecutive snapshots of the same state", () => {
    const snapshots = [snapshot(100, "alive"), snapshot(160, "alive"), snapshot(220, "dead")];
    expect(buildSegments(snapshots, 0, 1000)).toEqual([
      { from: 100, to: 220, state: "alive" },
      { from: 220, to: 310, state: "dead" },
    ]);
  });

  it("leaves a gap longer than 90 s as no data", () => {
    const snapshots = [snapshot(100, "alive"), snapshot(400, "alive")];
    expect(buildSegments(snapshots, 0, 1000)).toEqual([
      { from: 100, to: 190, state: "alive" },
      { from: 400, to: 490, state: "alive" },
    ]);
  });

  it("covers a single snapshot for 90 s, clipped to the window", () => {
    expect(buildSegments([snapshot(950, "frozen")], 0, 1000)).toEqual([{ from: 950, to: 1000, state: "frozen" }]);
    expect(buildSegments([snapshot(-50, "blind")], 0, 1000)).toEqual([{ from: 0, to: 40, state: "blind" }]);
  });
});

describe("timelineWindow", () => {
  it("ends at the phone's clock when it is ahead of the newest snapshot", () => {
    expect(timelineWindow([snapshot(1900, "alive")], 2000)).toEqual({ start: 2000 - DAY_S, end: 2000 });
    expect(timelineWindow([], 2000)).toEqual({ start: 2000 - DAY_S, end: 2000 });
  });

  it("keeps the current segment when the phone's clock lags the PC's", () => {
    const snapshots = [snapshot(10_000, "alive"), snapshot(10_060, "dead")];
    const clientNow = 10_000; // phone 60 s behind the PC
    const { start, end } = timelineWindow(snapshots, clientNow);
    expect(end).toBe(10_060);
    expect(start).toBe(10_060 - DAY_S);
    expect(buildSegments(snapshots, start, end)).toEqual([{ from: 10_000, to: 10_060, state: "alive" }]);
    // Ending at the phone's clock would have dropped it:
    expect(buildSegments(snapshots, clientNow - DAY_S, clientNow)).toEqual([]);
  });
});
```

- [ ] **Step 5: Testlerin başarısız olduğunu gör**

Run: `cd frontend; npm test`
Expected: FAIL — 3 test dosyası, `Error: Failed to resolve import "../src/format" from "test/format.test.ts". Does the file exist?` (ve `../src/api`, `../src/timeline` için aynısı).

- [ ] **Step 6: `labels.ts`, `format.ts`, `api.ts`, `timeline.ts`**

`frontend/src/labels.ts`:
```ts
export type Tone = "ok" | "warn" | "bad" | "off";

export interface StateLabel {
  text: string;
  tone: Tone;
}

export const STATE_LABELS: Record<string, StateLabel> = {
  alive: { text: "Canlı", tone: "ok" },
  dead: { text: "Ölü", tone: "bad" },
  disconnected: { text: "Bağlantı koptu", tone: "bad" },
  frozen: { text: "Donmuş", tone: "warn" },
  blind: { text: "Kör (izlenemiyor)", tone: "warn" },
  closed: { text: "Oyun kapalı", tone: "off" },
};

// Same titles as src/ko_monitor/messages.py TITLES.
export const EVENT_LABELS: Record<string, string> = {
  game_started: "▶️ Oyun açıldı",
  game_closed: "❌ Oyun kapandı",
  dead: "💀 Karakter öldü",
  disconnected: "🔌 Sunucudan düştün",
  frozen: "🧊 Oyun ekranı dondu",
  blind: "🙈 İzleme yapılamıyor",
  recovered: "✅ Düzeldi",
  inventory_full: "🎒 Envanter dolu",
  test: "🔔 Test bildirimi",
};

export function stateLabel(state: string | null | undefined): StateLabel {
  return (state && STATE_LABELS[state]) || { text: "Bilinmiyor", tone: "off" };
}

export function eventLabel(kind: string): string {
  return EVENT_LABELS[kind] || kind;
}
```

`frontend/src/format.ts`:
```ts
/** Seconds → "12 sn önce" / "3 dk önce" / "2 sa önce" / "1 gün önce"; null → "hiç". */
export function agoText(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "hiç";
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s} sn önce`;
  if (s < 3600) return `${Math.floor(s / 60)} dk önce`;
  if (s < 86400) return `${Math.floor(s / 3600)} sa önce`;
  return `${Math.floor(s / 86400)} gün önce`;
}

/** Unix seconds → "14:05" in the phone's time zone. */
export function clockText(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
}

/** Unix seconds → day, month, hour and minute in tr-TR. */
export function dateTimeText(ts: number): string {
  return new Date(ts * 1000).toLocaleString("tr-TR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Error line of screens that could not reach the PC; the last good data stays on screen. */
export function unreachableText(error: Error): string {
  return `Bilgisayara ulaşılamıyor (Tailscale açık mı?): ${error.message}`;
}

/** 1234567 → "1.234.567"; null → "—". */
export function numberText(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : Number(value).toLocaleString("tr-TR");
}
```

`frontend/src/api.ts`:
```ts
import type { AgentStatus, EventItem, PushTestResult, Quality, Snapshot } from "./types";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { cache: "no-store", ...options });
  if (!response.ok) {
    throw new ApiError(response.status, `${path}: HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export const getStatus = () => request<AgentStatus>("/api/status");
export const getEvents = (limit = 50) => request<EventItem[]>(`/api/events?limit=${limit}`);
export const getSnapshots = (since: number) => request<Snapshot[]>(`/api/snapshots?since=${since}`);
export const getVapidKey = () => request<{ key: string }>("/api/push/vapid-key");
export const sendTest = () => request<PushTestResult>("/api/push/test", { method: "POST" });

/** PushSubscription.toJSON() → POST /api/push/subscribe */
export function subscribe(subscription: PushSubscriptionJSON) {
  return request<{ ok: boolean }>("/api/push/subscribe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(subscription),
  });
}

/** quality null → the server's configured default ([api] stream_quality). */
export function streamUrl(quality: Quality | null): string {
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  const query = quality ? `?quality=${encodeURIComponent(quality)}` : "";
  return `${scheme}://${location.host}/api/stream${query}`;
}
```

`frontend/src/timeline.ts`:
```ts
import type { Snapshot, State } from "./types";

export const DAY_S = 86400;
// Snapshots arrive every 60 s while the game is open; a longer gap means "no data".
export const MAX_GAP_S = 90;

export interface Segment {
  from: number;
  to: number;
  state: State;
}

/** Snapshots (oldest first) → merged [from, to) pieces of one state, clipped to [start, end]. */
export function buildSegments(
  snapshots: readonly Snapshot[],
  start: number,
  end: number,
  maxGapS: number = MAX_GAP_S,
): Segment[] {
  const segments: Segment[] = [];
  snapshots.forEach((snapshot, index) => {
    const next = snapshots[index + 1];
    const covered = next ? Math.min(next.ts, snapshot.ts + maxGapS) : snapshot.ts + maxGapS;
    const from = Math.max(snapshot.ts, start);
    const to = Math.min(covered, end);
    if (to <= from) return;
    const last = segments[segments.length - 1];
    if (last && last.state === snapshot.state && Math.abs(last.to - from) < 1) {
      last.to = to;
    } else {
      segments.push({ from, to, state: snapshot.state });
    }
  });
  return segments;
}

/**
 * The 24 h window shown by the timeline. Snapshot timestamps come from the PC's clock and
 * clientNow from the phone's: if the phone lags, ending at clientNow would place the newest
 * snapshot after `end` and drop its (still current) segment, so the end is clamped forward.
 */
export function timelineWindow(snapshots: readonly Snapshot[], clientNow: number): { start: number; end: number } {
  const newestTs = snapshots.length ? snapshots[snapshots.length - 1].ts : clientNow;
  const end = Math.max(clientNow, newestTs);
  return { start: end - DAY_S, end };
}
```

- [ ] **Step 7: Testlerin ve tip denetiminin geçtiğini gör**

Run: `cd frontend; npm test`
Expected: `Test Files  3 passed (3)` / `Tests  18 passed (18)`

Run: `cd frontend; npx tsc -p tsconfig.json`
Expected: çıktı yok, çıkış kodu 0. (`tsconfig.sw.json` Task 8'de `src/sw.ts` yazılınca denetlenir; şimdi çalıştırılırsa "No inputs were found" hatası beklenir.)

- [ ] **Step 8: Commit**

```powershell
git add .gitignore scripts/make_icons.py tests/test_web.py frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/tsconfig.sw.json frontend/vite.config.ts frontend/vitest.config.ts frontend/index.html frontend/public/manifest.webmanifest frontend/public/icons/icon-180.png frontend/public/icons/icon-192.png frontend/public/icons/icon-512.png frontend/src/styles.css frontend/src/types.ts frontend/src/labels.ts frontend/src/format.ts frontend/src/api.ts frontend/src/timeline.ts frontend/test/setup.ts frontend/test/fakes.ts frontend/test/format.test.ts frontend/test/api.test.ts frontend/test/timeline.test.ts
git status --short
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: scaffold react frontend with typed api client, labels, formatting and timeline" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```
Expected: `git status --short` staged listesinde `frontend/node_modules` yok.

---

### Task 2: Görünürlük ve yoklama hook'ları — `useVisibility`, `usePolling`

**Files:**
- Create: `frontend/src/hooks/useVisibility.ts`, `frontend/src/hooks/usePolling.ts`
- Test: `frontend/test/usePolling.test.tsx`

**Interfaces:**
- Consumes: `setHidden(hidden)` (`test/fakes.ts`, Task 1).
- Produces:
  - `useVisibility(): boolean` — `!document.hidden`, `visibilitychange` ile güncellenir.
  - `interface Polling<T> { data: T | null; error: Error | null; loading: boolean; refresh: () => Promise<void> }`
  - `usePolling<T>(fn: () => Promise<T>, intervalMs: number | null): Polling<T>` — görünürken mount'ta ve görünür olunca hemen çağırır; `intervalMs` sayıysa görünürken bu aralıkla tekrarlar (`null`: zamanlayıcı yok); gizliyken ve unmount sonrası çağırmaz; hata olursa son `data` korunur, `error` dolar; başarıda `error = null`; uçuşta bir çağrı varken `refresh()` yeni çağrı başlatmaz.

- [ ] **Step 1: Failing test yaz**

`frontend/test/usePolling.test.tsx`:
```tsx
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { usePolling } from "../src/hooks/usePolling";
import { setHidden } from "./fakes";

async function flush(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("usePolling", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("calls at once and then every interval while visible", async () => {
    const fn = vi.fn().mockResolvedValue("data");
    const { result } = renderHook(() => usePolling(fn, 5000));
    await flush();
    expect(fn).toHaveBeenCalledTimes(1);
    expect(result.current.data).toBe("data");
    await flush(5000);
    expect(fn).toHaveBeenCalledTimes(2);
    await flush(10000);
    expect(fn).toHaveBeenCalledTimes(4);
  });

  it("stops while hidden and refreshes at once when visible again", async () => {
    const fn = vi.fn().mockResolvedValue(1);
    renderHook(() => usePolling(fn, 5000));
    await flush();
    act(() => setHidden(true));
    await flush(30000);
    expect(fn).toHaveBeenCalledTimes(1);
    act(() => setHidden(false));
    await flush();
    expect(fn).toHaveBeenCalledTimes(2);
    await flush(5000);
    expect(fn).toHaveBeenCalledTimes(3);
  });

  it("stops calling after unmount", async () => {
    const fn = vi.fn().mockResolvedValue(1);
    const { unmount } = renderHook(() => usePolling(fn, 5000));
    await flush();
    unmount();
    await flush(30000);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("keeps the last data and sets the error on failure, clears it on success", async () => {
    const fn = vi.fn().mockResolvedValueOnce("first").mockRejectedValueOnce(new Error("offline")).mockResolvedValue("again");
    const { result } = renderHook(() => usePolling(fn, 5000));
    await flush();
    await flush(5000);
    expect(result.current.data).toBe("first");
    expect(result.current.error?.message).toBe("offline");
    await flush(5000);
    expect(result.current.data).toBe("again");
    expect(result.current.error).toBeNull();
  });

  it("without an interval loads on mount, on refresh() and when visible again", async () => {
    const fn = vi.fn().mockResolvedValue(1);
    const { result } = renderHook(() => usePolling(fn, null));
    await flush(60000);
    expect(fn).toHaveBeenCalledTimes(1);
    await act(async () => {
      await result.current.refresh();
    });
    expect(fn).toHaveBeenCalledTimes(2);
    act(() => setHidden(true));
    act(() => setHidden(false));
    await flush();
    expect(fn).toHaveBeenCalledTimes(3);
  });
});
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `cd frontend; npx vitest run test/usePolling.test.tsx`
Expected: FAIL — `Failed to resolve import "../src/hooks/usePolling"`

- [ ] **Step 3: Hook'ları yaz**

`frontend/src/hooks/useVisibility.ts`:
```ts
import { useSyncExternalStore } from "react";

function subscribe(onChange: () => void): () => void {
  document.addEventListener("visibilitychange", onChange);
  return () => document.removeEventListener("visibilitychange", onChange);
}

/** False while the app is in the background (document.hidden). */
export function useVisibility(): boolean {
  return useSyncExternalStore(subscribe, () => !document.hidden, () => true);
}
```

`frontend/src/hooks/usePolling.ts`:
```ts
import { useCallback, useEffect, useRef, useState } from "react";
import { useVisibility } from "./useVisibility";

export interface Polling<T> {
  /** Last successful result; kept when a later call fails. */
  data: T | null;
  /** Error of the last call, null after a success. */
  error: Error | null;
  /** A call is in flight. */
  loading: boolean;
  /** Calls fn now unless a call is already in flight. */
  refresh: () => Promise<void>;
}

/**
 * Calls fn when the screen mounts, again every intervalMs while the page is visible (null: no
 * timer), and at once when the page becomes visible again. Nothing runs while hidden or after unmount.
 */
export function usePolling<T>(fn: () => Promise<T>, intervalMs: number | null): Polling<T> {
  const visible = useVisibility();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(false);
  const fnRef = useRef(fn);
  const mounted = useRef(false);
  const inFlight = useRef(false);

  useEffect(() => {
    fnRef.current = fn;
  }, [fn]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const refresh = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    try {
      const value = await fnRef.current();
      if (mounted.current) {
        setData(value);
        setError(null);
      }
    } catch (caught) {
      if (mounted.current) setError(caught instanceof Error ? caught : new Error(String(caught)));
    } finally {
      inFlight.current = false;
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!visible) return undefined;
    void refresh();
    if (intervalMs === null) return undefined;
    const timer = setInterval(() => void refresh(), intervalMs);
    return () => clearInterval(timer);
  }, [visible, intervalMs, refresh]);

  return { data, error, loading, refresh };
}
```

- [ ] **Step 4: Testlerin geçtiğini gör**

Run: `cd frontend; npm test`
Expected: `Test Files  4 passed (4)` / `Tests  23 passed (23)`

Run: `cd frontend; npx tsc -p tsconfig.json`
Expected: çıktı yok.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/hooks/useVisibility.ts frontend/src/hooks/usePolling.ts frontend/test/usePolling.test.tsx
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: visibility-aware polling hook for the react pwa" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Canlı yayın hook'u — `useStream` ve kalite tercihi

**Files:**
- Create: `frontend/src/hooks/useStream.ts`, `frontend/src/quality.ts`
- Test: `frontend/test/useStream.test.tsx`

**Interfaces:**
- Consumes: `streamUrl(quality)` (`api.ts`), `useVisibility()` (Task 2), `Quality` (`types.ts`), `FakeWebSocket`, `installStreamFakes`, `setHidden` (`test/fakes.ts`); sunucu: `WS /api/stream?quality=` ikili mesaj = JPEG kare, metin = `{"status": "minimized" | "not_found" | "black" | "ok"}`, 1008 = origin reddi / bilinmeyen kalite (`stream.py`).
- Produces:
  - `quality.ts`: `QUALITIES: ReadonlyArray<readonly [Quality, string]>` (`low` Düşük, `medium` Orta, `high` Yüksek), `QUALITY_STORAGE_KEY = "ko-monitor.quality"`, `loadQuality(): Quality | null`, `saveQuality(quality: Quality): void` (localStorage yoksa sessizce geçer).
  - `useStream.ts`: `RECONNECT_MS = [1000, 2000, 5000, 10000]`, `POLICY_VIOLATION = 1008`, `statusText(message: string): string`, `interface StreamView { frameUrl: string | null; overlay: string }`, `useStream(quality: Quality | null, enabled: boolean): StreamView` (`overlay === ""` → kaplama gizli).

- [ ] **Step 1: Failing test yaz**

`frontend/test/useStream.test.tsx`:
```tsx
import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useStream } from "../src/hooks/useStream";
import type { Quality } from "../src/types";
import { FakeWebSocket, installStreamFakes, setHidden } from "./fakes";

describe("useStream", () => {
  let urls: ReturnType<typeof installStreamFakes>;

  beforeEach(() => {
    vi.useFakeTimers();
    urls = installStreamFakes();
  });

  it("opens exactly one blob socket to the stream URL", () => {
    const { result, rerender } = renderHook(() => useStream("low", true));
    rerender();
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.last().url).toBe(`ws://${location.host}/api/stream?quality=low`);
    expect(FakeWebSocket.last().binaryType).toBe("blob");
    expect(result.current.overlay).toBe("Bağlanıyor…");
  });

  it("shows frames and revokes the previous object URL", () => {
    const { result, unmount } = renderHook(() => useStream(null, true));
    const ws = FakeWebSocket.last();
    act(() => ws.receive(new Blob(["a"])));
    expect(result.current).toEqual({ frameUrl: "blob:frame-1", overlay: "" });
    act(() => ws.receive(new Blob(["b"])));
    expect(result.current.frameUrl).toBe("blob:frame-2");
    expect(urls.revokeObjectURL).toHaveBeenCalledWith("blob:frame-1");
    unmount();
    expect(urls.revokeObjectURL).toHaveBeenLastCalledWith("blob:frame-2");
    expect(ws.closed).toBe(true);
  });

  it("turns status messages into Turkish overlay text", () => {
    const { result } = renderHook(() => useStream(null, true));
    act(() => FakeWebSocket.last().receive('{"status":"minimized"}'));
    expect(result.current.overlay).toBe("Oyun penceresi küçültülmüş, görüntü alınamıyor");
    act(() => FakeWebSocket.last().receive("not json"));
    expect(result.current.overlay).toBe("Görüntü bekleniyor…");
  });

  it("reconnects once when the quality changes", () => {
    const { rerender } = renderHook(({ quality }: { quality: Quality }) => useStream(quality, true), {
      initialProps: { quality: "low" },
    });
    const first = FakeWebSocket.last();
    rerender({ quality: "high" });
    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(first.closed).toBe(true);
    expect(FakeWebSocket.last().url).toBe(`ws://${location.host}/api/stream?quality=high`);
    act(() => first.serverClose(1005)); // the late close event of the old socket is ignored
    rerender({ quality: "high" });
    act(() => vi.advanceTimersByTime(30000));
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it("closes while hidden and reconnects when visible again", () => {
    const { result } = renderHook(() => useStream(null, true));
    act(() => setHidden(true));
    expect(FakeWebSocket.last().closed).toBe(true);
    expect(result.current.overlay).toBe("Duraklatıldı");
    act(() => vi.advanceTimersByTime(30000));
    expect(FakeWebSocket.instances).toHaveLength(1);
    act(() => setHidden(false));
    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(result.current.overlay).toBe("Bağlanıyor…");
  });

  it("backs off 1, 2, 5 and at most 10 seconds", () => {
    const { result } = renderHook(() => useStream(null, true));
    [1000, 2000, 5000, 10000, 10000].forEach((delay, index) => {
      act(() => FakeWebSocket.instances[index].serverClose(1006));
      expect(result.current.overlay).toBe(`Bağlantı koptu, ${delay / 1000} sn içinde yeniden denenecek…`);
      act(() => vi.advanceTimersByTime(delay - 1));
      expect(FakeWebSocket.instances).toHaveLength(index + 1);
      act(() => vi.advanceTimersByTime(1));
      expect(FakeWebSocket.instances).toHaveLength(index + 2);
      expect(result.current.overlay).toBe("Yeniden bağlanıyor…");
    });
  });

  it("does not retry after close code 1008", () => {
    const { result } = renderHook(() => useStream("high", true));
    act(() => FakeWebSocket.last().serverClose(1008, "origin not allowed"));
    expect(result.current.overlay).toBe("Sunucu bağlantıyı reddetti (origin not allowed). Sayfayı yenileyip tekrar dene.");
    act(() => vi.advanceTimersByTime(60000));
    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it("clears a pending retry on unmount", () => {
    const { unmount } = renderHook(() => useStream(null, true));
    act(() => FakeWebSocket.last().serverClose(1006));
    unmount();
    act(() => vi.advanceTimersByTime(30000));
    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it("stays closed while disabled", () => {
    const { result } = renderHook(() => useStream(null, false));
    expect(FakeWebSocket.instances).toHaveLength(0);
    expect(result.current.overlay).toBe("Duraklatıldı");
  });
});
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `cd frontend; npx vitest run test/useStream.test.tsx`
Expected: FAIL — `Failed to resolve import "../src/hooks/useStream"`

- [ ] **Step 3: `quality.ts` ve `useStream.ts`**

`frontend/src/quality.ts`:
```ts
import type { Quality } from "./types";

export const QUALITIES: ReadonlyArray<readonly [Quality, string]> = [
  ["low", "Düşük"],
  ["medium", "Orta"],
  ["high", "Yüksek"],
];
export const QUALITY_STORAGE_KEY = "ko-monitor.quality";

/** The quality chosen earlier on this phone; null → the server's [api] stream_quality. */
export function loadQuality(): Quality | null {
  try {
    const saved = localStorage.getItem(QUALITY_STORAGE_KEY);
    return QUALITIES.find(([key]) => key === saved)?.[0] ?? null;
  } catch {
    return null; // storage unavailable: use the server default
  }
}

export function saveQuality(quality: Quality): void {
  try {
    localStorage.setItem(QUALITY_STORAGE_KEY, quality);
  } catch {
    // storage unavailable: the choice lasts until the screen is left
  }
}
```

`frontend/src/hooks/useStream.ts`:
```ts
import { useEffect, useRef, useState } from "react";
import { streamUrl } from "../api";
import type { Quality } from "../types";
import { useVisibility } from "./useVisibility";

export const RECONNECT_MS = [1000, 2000, 5000, 10000];
// The server closes with 1008 for a foreign Origin or an unknown quality: retrying cannot help.
export const POLICY_VIOLATION = 1008;

const STATUS_TEXT: Record<string, string> = {
  minimized: "Oyun penceresi küçültülmüş, görüntü alınamıyor",
  not_found: "Oyun penceresi bulunamadı",
  black: "Ekran siyah",
};

/** Text message of WS /api/stream ({"status": ...}) → overlay text. */
export function statusText(message: string): string {
  let status = "";
  try {
    status = String((JSON.parse(message) as { status?: unknown }).status ?? "");
  } catch {
    status = "";
  }
  return STATUS_TEXT[status] || "Görüntü bekleniyor…";
}

export interface StreamView {
  /** Object URL of the newest JPEG frame. */
  frameUrl: string | null;
  /** Text over the picture; "" hides the overlay. */
  overlay: string;
}

/**
 * One WebSocket to /api/stream while enabled and visible. Reconnects after a drop with a bounded
 * backoff, reconnects once when quality changes, closes when hidden/disabled/unmounted.
 */
export function useStream(quality: Quality | null, enabled: boolean): StreamView {
  const visible = useVisibility();
  const [frameUrl, setFrameUrl] = useState<string | null>(null);
  const [overlay, setOverlay] = useState("Bağlanıyor…");
  const frameRef = useRef<string | null>(null);

  useEffect(() => {
    if (!enabled || !visible) {
      setOverlay("Duraklatıldı");
      return undefined;
    }
    let socket: WebSocket | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    let stopped = false;

    const showFrame = (blob: Blob) => {
      const previous = frameRef.current;
      const url = URL.createObjectURL(blob);
      frameRef.current = url;
      setFrameUrl(url);
      if (previous) URL.revokeObjectURL(previous);
    };

    const connect = () => {
      retryTimer = undefined;
      if (stopped) return;
      setOverlay(attempts ? "Yeniden bağlanıyor…" : "Bağlanıyor…");
      const ws = new WebSocket(streamUrl(quality));
      ws.binaryType = "blob";
      socket = ws;
      ws.onmessage = (event: MessageEvent) => {
        if (socket !== ws) return;
        if (typeof event.data === "string") {
          setOverlay(statusText(event.data));
          return;
        }
        attempts = 0;
        setOverlay("");
        showFrame(event.data as Blob);
      };
      ws.onclose = (event: CloseEvent) => {
        if (socket !== ws) return; // closed on purpose: quality change, page hidden or screen left
        socket = null;
        if (stopped) return;
        if (event.code === POLICY_VIOLATION) {
          setOverlay(`Sunucu bağlantıyı reddetti (${event.reason || "1008"}). Sayfayı yenileyip tekrar dene.`);
          return;
        }
        const delay = RECONNECT_MS[Math.min(attempts, RECONNECT_MS.length - 1)];
        attempts += 1;
        setOverlay(`Bağlantı koptu, ${Math.round(delay / 1000)} sn içinde yeniden denenecek…`);
        retryTimer = setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      stopped = true;
      clearTimeout(retryTimer);
      const ws = socket;
      socket = null;
      ws?.close(); // the server stops capturing and encoding for this viewer
    };
  }, [quality, enabled, visible]);

  useEffect(
    () => () => {
      if (frameRef.current) URL.revokeObjectURL(frameRef.current);
      frameRef.current = null;
    },
    [],
  );

  return { frameUrl, overlay };
}
```

- [ ] **Step 4: Testlerin geçtiğini gör**

Run: `cd frontend; npm test`
Expected: `Test Files  5 passed (5)` / `Tests  32 passed (32)`

Run: `cd frontend; npx tsc -p tsconfig.json`
Expected: çıktı yok.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/quality.ts frontend/src/hooks/useStream.ts frontend/test/useStream.test.tsx
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: live stream hook with bounded reconnect, pause when hidden and saved quality" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Bileşenler ve Durum/Olaylar ekranları

**Files:**
- Create: `frontend/src/components/StateBadge.tsx`, `frontend/src/components/HpBar.tsx`, `frontend/src/components/InventoryCard.tsx`, `frontend/src/components/EventList.tsx`, `frontend/src/components/Timeline.tsx`, `frontend/src/screens/Status.tsx`, `frontend/src/screens/Events.tsx`
- Test: `frontend/test/Status.test.tsx`, `frontend/test/Events.test.tsx`

**Interfaces:**
- Consumes: `getStatus`, `getEvents`, `getSnapshots` (`api.ts`); `agoText`, `clockText`, `dateTimeText`, `numberText`, `unreachableText` (`format.ts`); `stateLabel`, `eventLabel` (`labels.ts`); `DAY_S`, `buildSegments`, `timelineWindow` (`timeline.ts`); `usePolling` (Task 2); `stubFetch`, `agentStatus`, `eventItem`, `snapshot` (`test/fakes.ts`); CSS sınıfları (`styles.css`): `card row meta note ok warn bad off badge hpbar kv event-list event-kind timeline seg timeline-axis legend dot state-*`.
- Produces:
  - `StateBadge({ state: string | null })`, `HpBar({ readings: Readings | null })`, `slotsText(status: AgentStatus): string`, `InventoryCard({ status: AgentStatus })`, `EventList({ title: string; events: readonly EventItem[] })`, `Timeline({ snapshots: readonly Snapshot[]; start: number; end: number })`.
  - `Status()` — 5 sn'de bir (yalnız görünürken) `getStatus()` + `getEvents(5)`; `Events()` — açılışta, öne gelince ve "Yenile" ile `getEvents(100)` + `getSnapshots(clientNow - DAY_S)`. İkisi de parametresiz ekran bileşenidir (Task 7 `App` kullanır).

- [ ] **Step 1: Failing testleri yaz**

`frontend/test/Status.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Status } from "../src/screens/Status";
import { agentStatus, eventItem, stubFetch } from "./fakes";

describe("Status screen", () => {
  it("shows the badge, HP, inventory and the last five events", async () => {
    const fetchMock = stubFetch({
      "/api/status": agentStatus({ slots_total_last: null }),
      "/api/events": [eventItem(7, "dead", 999_900, "HP 0")],
    });
    render(<Status />);
    const badge = await screen.findByText("Canlı");
    expect(badge.className).toBe("badge ok");
    expect(screen.getByText("Son güncelleme 10 sn önce").className).toBe("meta");
    expect(screen.getByText("Bölge: Moradon")).toBeTruthy();
    expect(screen.getByText("9.718 / 9.996")).toBeTruthy();
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("9718");
    expect(screen.getByText("1.234.567")).toBeTruthy();
    expect(screen.getByText("20")).toBeTruthy(); // slot total unknown: used slots only
    expect(screen.getByText("💀 Karakter öldü")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith("/api/events?limit=5", { cache: "no-store" });
  });

  it("marks stale data and unreadable values", async () => {
    stubFetch({
      "/api/status": agentStatus({
        updated_at: 999_900,
        state: "frozen",
        readings: null,
        zone_last: null,
        money_last: null,
        inventory_seen_at: null,
      }),
      "/api/events": [],
    });
    render(<Status />);
    expect((await screen.findByText("Son güncelleme 1 dk önce")).className).toBe("meta warn");
    expect(screen.getByText("Donmuş").className).toBe("badge warn");
    expect(screen.getByText("HP: okunamadı")).toBeTruthy();
    expect(screen.getByText("Bölge: bilinmiyor")).toBeTruthy();
    expect(screen.getByText("—")).toBeTruthy();
    expect(screen.getByText("hiç (envanter penceresi açılınca okunur)")).toBeTruthy();
    expect(screen.getByText("Henüz olay yok.")).toBeTruthy();
  });

  it("says when the PC cannot be reached", async () => {
    stubFetch({ "/api/status": new TypeError("Failed to fetch"), "/api/events": [] });
    render(<Status />);
    expect(await screen.findByText("Bilgisayara ulaşılamıyor (Tailscale açık mı?): Failed to fetch")).toBeTruthy();
    expect(screen.getByText("Yükleniyor…")).toBeTruthy();
  });
});
```

`frontend/test/Events.test.tsx`:
```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Events } from "../src/screens/Events";
import { DAY_S } from "../src/timeline";
import { eventItem, snapshot, stubFetch } from "./fakes";

describe("Events screen", () => {
  it("lists events and draws the 24 h timeline", async () => {
    const now = Date.now() / 1000;
    const fetchMock = stubFetch({
      "/api/events": [eventItem(2, "game_started", now - 120), eventItem(1, "inventory_full", now - 600, "28/28")],
      "/api/snapshots": [snapshot(now - 600, "alive"), snapshot(now - 540, "dead")],
    });
    render(<Events />);
    expect(await screen.findByText("▶️ Oyun açıldı")).toBeTruthy();
    expect(screen.getByText("🎒 Envanter dolu")).toBeTruthy();
    expect(screen.getByText(/^28\/28 · /)).toBeTruthy();
    expect(screen.getByText("Son 24 saat")).toBeTruthy();
    expect(screen.getByText("Tüm olaylar")).toBeTruthy();
    const bar = screen.getByRole("img", { name: "Son 24 saatin durum çizelgesi" });
    expect([...bar.querySelectorAll(".seg")].map((seg) => seg.className)).toEqual(["seg state-alive", "seg state-dead"]);
    expect(screen.getByText("Veri yok / oyun kapalı")).toBeTruthy();

    expect(fetchMock.mock.calls[0][0]).toBe("/api/events?limit=100");
    const since = Number(new URL(String(fetchMock.mock.calls[1][0]), location.origin).searchParams.get("since"));
    expect(Math.abs(since - (now - DAY_S))).toBeLessThan(5);
  });

  it("reloads on Yenile and shows an empty list", async () => {
    const fetchMock = stubFetch({ "/api/events": [], "/api/snapshots": [] });
    render(<Events />);
    expect(await screen.findByText("Henüz olay yok.")).toBeTruthy();
    const button = screen.getByRole("button", { name: "Yenile" }) as HTMLButtonElement;
    await waitFor(() => expect(button.disabled).toBe(false));
    fireEvent.click(button);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
  });
});
```

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

Run: `cd frontend; npx vitest run test/Status.test.tsx test/Events.test.tsx`
Expected: FAIL — `Failed to resolve import "../src/screens/Status"` ve `"../src/screens/Events"`

- [ ] **Step 3: Bileşenleri yaz**

`frontend/src/components/StateBadge.tsx`:
```tsx
import { stateLabel } from "../labels";

export function StateBadge({ state }: { state: string | null }) {
  const label = stateLabel(state);
  return <span className={`badge ${label.tone}`}>{label.text}</span>;
}
```

`frontend/src/components/HpBar.tsx`:
```tsx
import { numberText } from "../format";
import type { Readings } from "../types";

export function HpBar({ readings }: { readings: Readings | null }) {
  const hp = readings ? readings.hp : null;
  const max = readings ? readings.hp_max : null;
  if (hp === null || hp === undefined || !max) {
    return <p className="meta">HP: okunamadı</p>;
  }
  const percent = Math.max(0, Math.min(100, (hp / max) * 100));
  return (
    <div>
      <div className="row">
        <span>HP</span>
        <span>{`${numberText(hp)} / ${numberText(max)}`}</span>
      </div>
      <div className="hpbar" role="progressbar" aria-valuemin={0} aria-valuemax={max} aria-valuenow={hp}>
        <span style={{ width: `${percent.toFixed(1)}%` }} />
      </div>
    </div>
  );
}
```

`frontend/src/components/InventoryCard.tsx`:
```tsx
import { agoText, clockText, numberText } from "../format";
import type { AgentStatus } from "../types";

export function slotsText(status: AgentStatus): string {
  const used = status.slots_used_last;
  const total = status.slots_total_last;
  if (used === null || used === undefined) return "—";
  if (total === null || total === undefined) return numberText(used);
  return `${numberText(used)} / ${numberText(total)}`;
}

export function InventoryCard({ status }: { status: AgentStatus }) {
  const seen = status.inventory_seen_at;
  const seenText =
    seen === null || seen === undefined
      ? "hiç (envanter penceresi açılınca okunur)"
      : `${clockText(seen)} (${agoText(status.server_time - seen)})`;
  return (
    <section className="card">
      <h2>Envanter (son görülen)</h2>
      <dl className="kv">
        <dt>Para</dt>
        <dd>{numberText(status.money_last)}</dd>
        <dt>Slotlar</dt>
        <dd>{slotsText(status)}</dd>
        <dt>Görüldü</dt>
        <dd>{seenText}</dd>
      </dl>
    </section>
  );
}
```

`frontend/src/components/EventList.tsx`:
```tsx
import { dateTimeText } from "../format";
import { eventLabel } from "../labels";
import type { EventItem } from "../types";

export function EventList({ title, events }: { title: string; events: readonly EventItem[] }) {
  return (
    <section className="card">
      <h2>{title}</h2>
      {events.length ? (
        <ul className="event-list">
          {events.map((event) => (
            <li key={event.id}>
              <span className="event-kind">{eventLabel(event.kind)}</span>
              <span className="meta">{[event.detail, dateTimeText(event.ts)].filter(Boolean).join(" · ")}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="meta">Henüz olay yok.</p>
      )}
    </section>
  );
}
```

`frontend/src/components/Timeline.tsx`:
```tsx
import { clockText } from "../format";
import { stateLabel } from "../labels";
import { buildSegments } from "../timeline";
import type { Snapshot, State } from "../types";

const LEGEND_STATES: State[] = ["alive", "dead", "disconnected", "frozen", "blind"];

export function Timeline({ snapshots, start, end }: { snapshots: readonly Snapshot[]; start: number; end: number }) {
  const span = end - start;
  return (
    <section className="card">
      <h2>Son 24 saat</h2>
      <div className="timeline" role="img" aria-label="Son 24 saatin durum çizelgesi">
        {buildSegments(snapshots, start, end).map((segment) => {
          const left = ((segment.from - start) / span) * 100;
          const width = Math.max(0.2, ((segment.to - segment.from) / span) * 100);
          return (
            <span
              key={segment.from}
              className={`seg state-${segment.state}`}
              title={`${stateLabel(segment.state).text}: ${clockText(segment.from)}–${clockText(segment.to)}`}
              style={{ left: `${left.toFixed(3)}%`, width: `${width.toFixed(3)}%` }}
            />
          );
        })}
      </div>
      <div className="timeline-axis">
        {[0, 1, 2, 3, 4].map((i) => (
          <span key={i}>{clockText(start + (span * i) / 4)}</span>
        ))}
      </div>
      <div className="legend">
        {LEGEND_STATES.map((state) => (
          <span key={state}>
            <i className={`dot state-${state}`} />
            {stateLabel(state).text}
          </span>
        ))}
        <span>
          <i className="dot state-none" />
          Veri yok / oyun kapalı
        </span>
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Ekranları yaz**

`frontend/src/screens/Status.tsx`:
```tsx
import { getEvents, getStatus } from "../api";
import { EventList } from "../components/EventList";
import { HpBar } from "../components/HpBar";
import { InventoryCard } from "../components/InventoryCard";
import { StateBadge } from "../components/StateBadge";
import { agoText, unreachableText } from "../format";
import { usePolling } from "../hooks/usePolling";
import type { AgentStatus } from "../types";

const POLL_MS = 5000;
const STALE_S = 30; // the agent publishes every 2 s (10 s while the game is closed)

async function loadStatus() {
  const [status, events] = await Promise.all([getStatus(), getEvents(5)]);
  return { status, events };
}

function StateCard({ status }: { status: AgentStatus }) {
  let updated = "Ajan henüz veri göndermedi";
  let stale = true;
  if (status.updated_at !== null && status.updated_at !== undefined) {
    const age = status.server_time - status.updated_at;
    stale = age > STALE_S;
    updated = `Son güncelleme ${agoText(age)}`;
  }
  return (
    <section className="card">
      <div className="row">
        <StateBadge state={status.state} />
        <span className={stale ? "meta warn" : "meta"}>{updated}</span>
      </div>
      <p className="meta">{status.zone_last ? `Bölge: ${status.zone_last}` : "Bölge: bilinmiyor"}</p>
      <HpBar readings={status.readings} />
    </section>
  );
}

export function Status() {
  const { data, error } = usePolling(loadStatus, POLL_MS);
  return (
    <>
      <h1>Durum</h1>
      {/* Keep the last good data on screen; only say that it is not fresh. */}
      {error && <p className="note bad">{unreachableText(error)}</p>}
      {data ? (
        <div>
          <StateCard status={data.status} />
          <InventoryCard status={data.status} />
          <EventList title="Son olaylar" events={data.events} />
        </div>
      ) : (
        <div>
          <p className="meta">Yükleniyor…</p>
        </div>
      )}
    </>
  );
}
```

`frontend/src/screens/Events.tsx`:
```tsx
import { getEvents, getSnapshots } from "../api";
import { EventList } from "../components/EventList";
import { Timeline } from "../components/Timeline";
import { unreachableText } from "../format";
import { usePolling } from "../hooks/usePolling";
import { DAY_S, timelineWindow } from "../timeline";

async function loadEvents() {
  const clientNow = Date.now() / 1000;
  const [events, snapshots] = await Promise.all([getEvents(100), getSnapshots(clientNow - DAY_S)]);
  return { events, snapshots, ...timelineWindow(snapshots, clientNow) };
}

export function Events() {
  // No timer: loads on open, when the app comes back to the foreground and on "Yenile".
  const { data, error, loading, refresh } = usePolling(loadEvents, null);
  return (
    <>
      <div className="row">
        <h1>Olaylar</h1>
        <button type="button" disabled={loading} onClick={() => void refresh()}>
          Yenile
        </button>
      </div>
      {error && <p className="note bad">{unreachableText(error)}</p>}
      {data ? (
        <div>
          <Timeline snapshots={data.snapshots} start={data.start} end={data.end} />
          <EventList title="Tüm olaylar" events={data.events} />
        </div>
      ) : (
        <div>
          <p className="meta">Yükleniyor…</p>
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 5: Testlerin geçtiğini gör**

Run: `cd frontend; npm test`
Expected: `Test Files  7 passed (7)` / `Tests  37 passed (37)`

Run: `cd frontend; npx tsc -p tsconfig.json`
Expected: çıktı yok.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/components/StateBadge.tsx frontend/src/components/HpBar.tsx frontend/src/components/InventoryCard.tsx frontend/src/components/EventList.tsx frontend/src/components/Timeline.tsx frontend/src/screens/Status.tsx frontend/src/screens/Events.tsx frontend/test/Status.test.tsx frontend/test/Events.test.tsx
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: status and events screens in react" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Bildirim akışı ve Ayarlar/Canlı ekranları

**Files:**
- Create: `frontend/src/push.ts`, `frontend/src/screens/Settings.tsx`, `frontend/src/screens/Live.tsx`
- Test: `frontend/test/push.test.ts`, `frontend/test/Settings.test.tsx`, `frontend/test/Live.test.tsx`

**Interfaces:**
- Consumes: `getVapidKey`, `subscribe`, `sendTest` (`api.ts`); `useStream` (Task 3); `QUALITIES`, `QUALITY_STORAGE_KEY`, `loadQuality`, `saveQuality` (`quality.ts`, Task 3); `stubFetch`, `FakeWebSocket`, `installStreamFakes` (`test/fakes.ts`); CSS sınıfları `buttons primary active live-mode live-header quality live-stage live-frame live-overlay`.
- Produces:
  - `push.ts`: `SW_READY_TIMEOUT_MS = 5000`, `base64UrlToBytes(value: string): Uint8Array<ArrayBuffer>`, `isStandalone(): boolean`, `pushSupported(): boolean`, `serviceWorkerReady(timeoutMs = SW_READY_TIMEOUT_MS): Promise<ServiceWorkerRegistration>` (zaman aşımında `"Servis çalışanı hazır değil — sayfayı yenileyip tekrar dene"`), `enableNotifications(): Promise<void>` (izin → hazır SW → VAPID anahtarı → anahtar değiştiyse `unsubscribe` → `subscribe` → `POST /api/push/subscribe`).
  - `Settings()`, `Live()` — parametresiz ekran bileşenleri (Task 7 `App` kullanır). `Live` mount'ta `document.body`'ye `live-mode` ekler, unmount'ta kaldırır.

- [ ] **Step 1: Failing testleri yaz**

`frontend/test/push.test.ts`:
```ts
import { beforeEach, describe, expect, it, vi } from "vitest";
import { base64UrlToBytes, enableNotifications, serviceWorkerReady } from "../src/push";
import { stubFetch } from "./fakes";

function fakeSubscription(keyBytes: number[]) {
  return {
    options: { applicationServerKey: new Uint8Array(keyBytes).buffer },
    unsubscribe: vi.fn().mockResolvedValue(true),
    toJSON: () => ({ endpoint: "https://web.push.apple.com/abc", keys: { p256dh: "p", auth: "a" } }),
  };
}

function installPush(existing: ReturnType<typeof fakeSubscription> | null, ready?: Promise<unknown>) {
  const created = fakeSubscription([1, 2, 3]);
  const pushManager = {
    getSubscription: vi.fn().mockResolvedValue(existing),
    subscribe: vi.fn().mockResolvedValue(created),
  };
  const registration = { pushManager };
  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: { ready: ready ?? Promise.resolve(registration) },
  });
  vi.stubGlobal("Notification", { permission: "default", requestPermission: vi.fn().mockResolvedValue("granted") });
  vi.stubGlobal("PushManager", function PushManager() {});
  return pushManager;
}

describe("push", () => {
  beforeEach(() => {
    stubFetch({ "/api/push/vapid-key": { key: "AQID" }, "/api/push/subscribe": { ok: true } });
  });

  it("decodes base64url VAPID keys", () => {
    expect([...base64UrlToBytes("AQID")]).toEqual([1, 2, 3]);
    expect([...base64UrlToBytes("-_8")]).toEqual([251, 255]);
  });

  it("gives up waiting for the service worker after 5 s with a Turkish hint", async () => {
    vi.useFakeTimers();
    installPush(null, new Promise(() => {}));
    const waiting = serviceWorkerReady().catch((error: Error) => error.message);
    await vi.advanceTimersByTimeAsync(5000);
    await expect(waiting).resolves.toBe("Servis çalışanı hazır değil — sayfayı yenileyip tekrar dene");
  });

  it("refuses without permission", async () => {
    installPush(null);
    vi.stubGlobal("Notification", { permission: "default", requestPermission: vi.fn().mockResolvedValue("denied") });
    await expect(enableNotifications()).rejects.toThrow("Bildirim izni verilmedi.");
  });

  it("subscribes with the VAPID key and posts the subscription", async () => {
    const pushManager = installPush(null);
    await enableNotifications();
    const options = pushManager.subscribe.mock.calls[0][0];
    expect(options.userVisibleOnly).toBe(true);
    expect([...options.applicationServerKey]).toEqual([1, 2, 3]);
    expect(fetch).toHaveBeenLastCalledWith("/api/push/subscribe", expect.objectContaining({ method: "POST" }));
  });

  it("keeps a subscription made with the same key", async () => {
    const existing = fakeSubscription([1, 2, 3]);
    const pushManager = installPush(existing);
    await enableNotifications();
    expect(existing.unsubscribe).not.toHaveBeenCalled();
    expect(pushManager.subscribe).not.toHaveBeenCalled();
  });

  it("resubscribes when the PC's VAPID key changed", async () => {
    const existing = fakeSubscription([9, 9, 9]);
    const pushManager = installPush(existing);
    await enableNotifications();
    expect(existing.unsubscribe).toHaveBeenCalledOnce();
    expect(pushManager.subscribe).toHaveBeenCalledOnce();
  });
});
```

`frontend/test/Settings.test.tsx`:
```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Settings } from "../src/screens/Settings";
import { stubFetch } from "./fakes";

const INSTALL_HINT =
  "iPhone'da bildirim için önce Safari → Paylaş → Ana Ekrana Ekle ile uygulamayı kur ve ana ekrandaki simgeden aç.";

function stubStandalone(standalone: boolean) {
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: standalone })));
}

function stubPushSupport(permission: NotificationPermission, requested: NotificationPermission = permission) {
  Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: { ready: new Promise(() => {}) } });
  vi.stubGlobal("PushManager", function PushManager() {});
  vi.stubGlobal("Notification", { permission, requestPermission: vi.fn().mockResolvedValue(requested) });
}

describe("Settings screen", () => {
  it("explains that this browser has no Web Push and how to install the app", () => {
    stubStandalone(false);
    render(<Settings />);
    expect(screen.getByText("Bu tarayıcı Web Push desteklemiyor (iPhone'da iOS 16.4 veya üstü gerekir).")).toBeTruthy();
    expect(screen.getByText(INSTALL_HINT)).toBeTruthy();
    expect((screen.getByRole("button", { name: "Bildirimleri aç" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("tells how to allow a denied permission", () => {
    stubStandalone(true);
    stubPushSupport("denied");
    render(<Settings />);
    const line = screen.getByText("Bildirim izni reddedilmiş. iPhone Ayarlar → Bildirimler → KO Monitor'dan izin ver.");
    expect(line.className).toBe("note bad");
    expect(screen.queryByText(INSTALL_HINT)).toBeNull();
    expect((screen.getByRole("button", { name: "Bildirimleri aç" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("reports a refused permission prompt", async () => {
    stubStandalone(true);
    stubPushSupport("default", "denied");
    render(<Settings />);
    fireEvent.click(screen.getByRole("button", { name: "Bildirimleri aç" }));
    expect((await screen.findByText("Açılamadı: Bildirim izni verilmedi.")).className).toBe("note bad");
  });

  it("reports the test push result", async () => {
    stubStandalone(true);
    stubPushSupport("granted");
    const routes: Record<string, unknown> = { "/api/push/test": { delivered: false, subscriptions: 0 } };
    stubFetch(routes);
    render(<Settings />);
    const testButton = screen.getByRole("button", { name: "Test bildirimi gönder" });
    fireEvent.click(testButton);
    expect((await screen.findByText("Kayıtlı abonelik yok. Önce 'Bildirimleri aç'a dokun.")).className).toBe("note warn");
    routes["/api/push/test"] = { delivered: true, subscriptions: 1 };
    fireEvent.click(testButton);
    expect(await screen.findByText("Test bildirimi gönderildi.")).toBeTruthy();
    routes["/api/push/test"] = { delivered: false, subscriptions: 2 };
    fireEvent.click(testButton);
    expect(await screen.findByText("Gönderilemedi. Bilgisayardaki logs\\agent.log dosyasına bak.")).toBeTruthy();
  });
});
```

`frontend/test/Live.test.tsx`:
```tsx
import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { QUALITY_STORAGE_KEY } from "../src/quality";
import { Live } from "../src/screens/Live";
import { FakeWebSocket, installStreamFakes } from "./fakes";

describe("Live screen", () => {
  beforeEach(() => {
    installStreamFakes();
  });

  it("connects, shows the server status and then frames", () => {
    const { container, unmount } = render(<Live />);
    expect(screen.getByText("Bağlanıyor…")).toBeTruthy();
    expect(document.body.classList.contains("live-mode")).toBe(true);
    expect(
      screen.getByText(
        "Kalite seçilmedi: bilgisayardaki varsayılan kullanılıyor. Telefonu yan çevirince görüntü tam ekran olur.",
      ),
    ).toBeTruthy();
    expect(FakeWebSocket.last().url).toBe(`ws://${location.host}/api/stream`);

    act(() => FakeWebSocket.last().receive('{"status":"not_found"}'));
    expect(screen.getByText("Oyun penceresi bulunamadı")).toBeTruthy();

    act(() => FakeWebSocket.last().receive(new Blob(["jpeg"])));
    expect(screen.getByAltText("Canlı oyun görüntüsü").getAttribute("src")).toBe("blob:frame-1");
    expect((container.querySelector(".live-overlay") as HTMLElement).hidden).toBe(true);

    unmount();
    expect(document.body.classList.contains("live-mode")).toBe(false);
  });

  it("remembers the chosen quality and reconnects once", () => {
    render(<Live />);
    const high = screen.getByRole("button", { name: "Yüksek" });
    fireEvent.click(high);
    expect(localStorage.getItem(QUALITY_STORAGE_KEY)).toBe("high");
    expect(high.className).toBe("active");
    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(FakeWebSocket.instances[0].closed).toBe(true);
    expect(FakeWebSocket.last().url).toBe(`ws://${location.host}/api/stream?quality=high`);
    fireEvent.click(high);
    expect(FakeWebSocket.instances).toHaveLength(2);
    expect(screen.getByText("Telefonu yan çevirince görüntü tam ekran olur.")).toBeTruthy();
  });

  it("starts with the saved quality", () => {
    localStorage.setItem(QUALITY_STORAGE_KEY, "low");
    render(<Live />);
    expect(FakeWebSocket.last().url).toBe(`ws://${location.host}/api/stream?quality=low`);
    expect(screen.getByRole("button", { name: "Düşük" }).className).toBe("active");
  });
});
```

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

Run: `cd frontend; npx vitest run test/push.test.ts test/Settings.test.tsx test/Live.test.tsx`
Expected: FAIL — `Failed to resolve import "../src/push"`, `"../src/screens/Settings"`, `"../src/screens/Live"`

- [ ] **Step 3: `push.ts`**

`frontend/src/push.ts`:
```ts
import { getVapidKey, subscribe } from "./api";

// navigator.serviceWorker.ready never settles if the worker failed to install; do not hang the button.
export const SW_READY_TIMEOUT_MS = 5000;

export function base64UrlToBytes(value: string): Uint8Array<ArrayBuffer> {
  const padded = value + "=".repeat((4 - (value.length % 4)) % 4);
  const binary = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

function sameKey(subscription: PushSubscription, keyBytes: Uint8Array): boolean {
  const current = subscription.options && subscription.options.applicationServerKey;
  if (!current) return false;
  const bytes = new Uint8Array(current);
  return bytes.length === keyBytes.length && bytes.every((value, index) => value === keyBytes[index]);
}

/** Opened from the home screen icon (iOS only allows Web Push there). */
export function isStandalone(): boolean {
  const displayMode = typeof window.matchMedia === "function" && window.matchMedia("(display-mode: standalone)").matches;
  return displayMode || (navigator as Navigator & { standalone?: boolean }).standalone === true;
}

export function pushSupported(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}

export function serviceWorkerReady(timeoutMs: number = SW_READY_TIMEOUT_MS): Promise<ServiceWorkerRegistration> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error("Servis çalışanı hazır değil — sayfayı yenileyip tekrar dene")),
      timeoutMs,
    );
    void navigator.serviceWorker.ready.then((registration) => {
      clearTimeout(timer);
      resolve(registration);
    });
  });
}

/** Permission → VAPID key → (re)subscribe → POST /api/push/subscribe. Errors carry Turkish messages. */
export async function enableNotifications(): Promise<void> {
  // iOS only shows the permission prompt when it is requested directly from the tap.
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("Bildirim izni verilmedi.");
  }
  const registration = await serviceWorkerReady();
  const { key } = await getVapidKey();
  const keyBytes = base64UrlToBytes(key);
  let subscription = await registration.pushManager.getSubscription();
  if (subscription && !sameKey(subscription, keyBytes)) {
    await subscription.unsubscribe(); // the PC's VAPID key changed; the old subscription cannot be used
    subscription = null;
  }
  if (!subscription) {
    subscription = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes });
  }
  await subscribe(subscription.toJSON());
}
```

- [ ] **Step 4: Ayarlar ve Canlı ekranları**

`frontend/src/screens/Settings.tsx`:
```tsx
import { useState } from "react";
import { sendTest } from "../api";
import { enableNotifications, isStandalone, pushSupported } from "../push";

type LineTone = "" | "ok" | "warn" | "bad";

interface Line {
  text: string;
  tone: LineTone;
}

const INSTALL_HINT =
  "iPhone'da bildirim için önce Safari → Paylaş → Ana Ekrana Ekle ile uygulamayı kur ve ana ekrandaki simgeden aç.";
const UNSUPPORTED = "Bu tarayıcı Web Push desteklemiyor (iPhone'da iOS 16.4 veya üstü gerekir).";

function initialLine(supported: boolean): Line {
  if (supported && Notification.permission === "granted") {
    return {
      text: "Bildirim izni verilmiş. Aboneliği yenilemek için yine de 'Bildirimleri aç'a dokunabilirsin.",
      tone: "ok",
    };
  }
  if (supported && Notification.permission === "denied") {
    return { text: "Bildirim izni reddedilmiş. iPhone Ayarlar → Bildirimler → KO Monitor'dan izin ver.", tone: "bad" };
  }
  return { text: "", tone: "" };
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

export function Settings() {
  const [standalone] = useState(isStandalone);
  const [supported] = useState(pushSupported);
  const [line, setLine] = useState<Line>(() => initialLine(supported));
  const [enabling, setEnabling] = useState(false);
  const [testing, setTesting] = useState(false);
  const show = (text: string, tone: LineTone = "") => setLine({ text, tone });

  const onEnable = async () => {
    setEnabling(true);
    show("Bildirimler açılıyor…");
    try {
      await enableNotifications();
      show("Bildirimler açık. Şimdi test bildirimi gönderebilirsin.", "ok");
    } catch (error) {
      show(`Açılamadı: ${errorMessage(error)}`, "bad");
    } finally {
      setEnabling(false);
    }
  };

  const onTest = async () => {
    setTesting(true);
    show("Gönderiliyor…");
    try {
      const result = await sendTest();
      if (result.delivered) show("Test bildirimi gönderildi.", "ok");
      else if (result.subscriptions === 0) show("Kayıtlı abonelik yok. Önce 'Bildirimleri aç'a dokun.", "warn");
      else show("Gönderilemedi. Bilgisayardaki logs\\agent.log dosyasına bak.", "bad");
    } catch (error) {
      show(`Hata: ${errorMessage(error)}`, "bad");
    } finally {
      setTesting(false);
    }
  };

  return (
    <>
      <h1>Ayarlar</h1>
      <section className="card">
        <h2>Bildirimler</h2>
        {!standalone && <p className="note warn">{INSTALL_HINT}</p>}
        {!supported && <p className="note bad">{UNSUPPORTED}</p>}
        <div className="buttons">
          <button className="primary" type="button" disabled={!supported || enabling} onClick={() => void onEnable()}>
            Bildirimleri aç
          </button>
          <button type="button" disabled={testing} onClick={() => void onTest()}>
            Test bildirimi gönder
          </button>
        </div>
        <p className={line.tone ? `note ${line.tone}` : "note"}>{line.text}</p>
      </section>
    </>
  );
}
```

`frontend/src/screens/Live.tsx`:
```tsx
import { useEffect, useRef, useState } from "react";
import { useStream } from "../hooks/useStream";
import { loadQuality, QUALITIES, saveQuality } from "../quality";
import type { Quality } from "../types";

type FullscreenElement = HTMLElement & { webkitRequestFullscreen?: () => void };

function fullscreenSupported(): boolean {
  const proto = HTMLElement.prototype as FullscreenElement;
  return typeof proto.requestFullscreen === "function" || typeof proto.webkitRequestFullscreen === "function";
}

export function Live() {
  const [quality, setQuality] = useState<Quality | null>(loadQuality);
  const [canFullscreen] = useState(fullscreenSupported);
  const { frameUrl, overlay } = useStream(quality, true);
  const stageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    document.body.classList.add("live-mode");
    return () => document.body.classList.remove("live-mode");
  }, []);

  const choose = (next: Quality) => {
    if (next === quality) return;
    saveQuality(next);
    setQuality(next);
  };

  const enterFullscreen = () => {
    const stage = stageRef.current as FullscreenElement | null;
    if (!stage) return;
    if (typeof stage.requestFullscreen === "function") stage.requestFullscreen().catch(() => undefined);
    else stage.webkitRequestFullscreen?.();
  };

  return (
    <>
      <div className="live-header">
        <h1>Canlı</h1>
        <div className="quality">
          {QUALITIES.map(([key, text]) => (
            <button
              key={key}
              type="button"
              data-quality={key}
              className={key === quality ? "active" : undefined}
              onClick={() => choose(key)}
            >
              {text}
            </button>
          ))}
          <button type="button" hidden={!canFullscreen} onClick={enterFullscreen}>
            Tam ekran
          </button>
        </div>
      </div>
      <div className="live-stage" ref={stageRef}>
        <img className="live-frame" alt="Canlı oyun görüntüsü" src={frameUrl ?? undefined} />
        <div className="live-overlay" hidden={!overlay}>
          {overlay}
        </div>
      </div>
      <p className="meta">
        {(quality ? "" : "Kalite seçilmedi: bilgisayardaki varsayılan kullanılıyor. ") +
          "Telefonu yan çevirince görüntü tam ekran olur."}
      </p>
    </>
  );
}
```

- [ ] **Step 5: Testlerin geçtiğini gör**

Run: `cd frontend; npm test`
Expected: `Test Files  10 passed (10)` / `Tests  50 passed (50)`

Run: `cd frontend; npx tsc -p tsconfig.json`
Expected: çıktı yok.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/push.ts frontend/src/screens/Settings.tsx frontend/src/screens/Live.tsx frontend/test/push.test.ts frontend/test/Settings.test.tsx frontend/test/Live.test.tsx
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: settings push flow and live screen in react" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Uygulama kabuğu — hash yönlendirme, sekme çubuğu, `App`, `main.tsx` ve güvenlik denetimi

**Files:**
- Create: `frontend/src/hooks/useHashRoute.ts`, `frontend/src/components/TabBar.tsx`, `frontend/src/App.tsx`, `frontend/src/main.tsx`
- Test: `frontend/test/App.test.tsx`, `frontend/test/security.test.ts`

**Interfaces:**
- Consumes: `Status`, `Events` (Task 4), `Settings`, `Live` (Task 5); `stubFetch`, `agentStatus` (`test/fakes.ts`); `frontend/index.html` `<div id="root">` (Task 1); `styles.css` `#screen`, `nav.tabs`, `a.active`.
- Produces:
  - `useHashRoute.ts`: `ROUTES = ["status", "live", "events", "settings"] as const`, `type Route`, `ROUTE_TITLES: Record<Route, string>` (Durum, Canlı, Olaylar, Ayarlar), `parseRoute(hash: string): Route`, `useHashRoute(): Route`.
  - `TabBar({ route: Route })`, `App()` — `<main id="screen">` + `<nav class="tabs">`, `document.title = "<başlık> · KO Monitor"`.
  - `main.tsx`: üretimde `navigator.serviceWorker.register("/sw.js", { scope: "/" })`; SW'den gelen `{type: "navigate", url}` mesajı `location.hash`'i ayarlar (Task 7'deki `notificationclick` gönderir).

- [ ] **Step 1: Failing testleri yaz**

`frontend/test/App.test.tsx`:
```tsx
import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import { parseRoute } from "../src/hooks/useHashRoute";
import { agentStatus, stubFetch } from "./fakes";

function goTo(hash: string) {
  act(() => {
    window.location.hash = hash;
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
}

describe("App", () => {
  it("parses hash routes and falls back to Durum", () => {
    expect(parseRoute("#/events")).toBe("events");
    expect(parseRoute("#live?x=1")).toBe("live");
    expect(parseRoute("")).toBe("status");
    expect(parseRoute("#/nope")).toBe("status");
  });

  it("shows the four tabs in order and switches screens on hashchange", async () => {
    stubFetch({ "/api/status": agentStatus(), "/api/events": [], "/api/snapshots": [] });
    vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true })));
    render(<App />);
    const tabs = screen.getAllByRole("link");
    expect(tabs.map((tab) => tab.getAttribute("href"))).toEqual(["#/status", "#/live", "#/events", "#/settings"]);
    expect(tabs.map((tab) => tab.textContent)).toEqual(["Durum", "Canlı", "Olaylar", "Ayarlar"]);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Durum");
    expect(document.title).toBe("Durum · KO Monitor");
    await screen.findByText("Bölge: Moradon");

    goTo("#/settings");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Ayarlar");
    expect(document.title).toBe("Ayarlar · KO Monitor");
    expect(screen.getByRole("link", { name: "Ayarlar" }).className).toBe("active");
    expect(screen.getByRole("link", { name: "Durum" }).className).toBe("");

    goTo("#/events");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Olaylar");
    await screen.findByText("Son 24 saat");
  });
});
```

`frontend/test/security.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import indexHtml from "../index.html?raw";

const sources = import.meta.glob("../src/**/*.{ts,tsx,css}", { query: "?raw", import: "default", eager: true }) as Record<
  string,
  string
>;

describe("security", () => {
  it("scans every source file", () => {
    expect(Object.keys(sources)).toContain("../src/App.tsx");
  });

  it("never renders raw HTML", () => {
    for (const [path, text] of Object.entries(sources)) {
      expect(text, path).not.toMatch(/dangerouslySetInnerHTML|innerHTML/);
    }
  });

  it("loads nothing from another host (no CDN)", () => {
    for (const [path, text] of Object.entries({ ...sources, "index.html": indexHtml })) {
      expect(text, path).not.toMatch(/https?:\/\//);
    }
  });
});
```

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

Run: `cd frontend; npx vitest run test/App.test.tsx test/security.test.ts`
Expected: FAIL — `App.test.tsx`: `Failed to resolve import "../src/App"`; `security.test.ts` › `scans every source file`: `expected [ …(n) ] to include '../src/App.tsx'` (diğer iki güvenlik testi şimdiden geçer).

- [ ] **Step 3: Yönlendirme ve sekme çubuğu**

`frontend/src/hooks/useHashRoute.ts`:
```ts
import { useSyncExternalStore } from "react";

/** Tab order; the first route is the default. Push notifications open "/#/events". */
export const ROUTES = ["status", "live", "events", "settings"] as const;
export type Route = (typeof ROUTES)[number];

export const ROUTE_TITLES: Record<Route, string> = {
  status: "Durum",
  live: "Canlı",
  events: "Olaylar",
  settings: "Ayarlar",
};

/** "#/events" or "#events?x" → "events"; anything unknown → "status". */
export function parseRoute(hash: string): Route {
  const name = hash.replace(/^#\/?/, "").split("?")[0];
  return (ROUTES as readonly string[]).includes(name) ? (name as Route) : ROUTES[0];
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener("hashchange", onChange);
  return () => window.removeEventListener("hashchange", onChange);
}

export function useHashRoute(): Route {
  return useSyncExternalStore(subscribe, () => parseRoute(location.hash), () => ROUTES[0]);
}
```

`frontend/src/components/TabBar.tsx`:
```tsx
import { type Route, ROUTE_TITLES, ROUTES } from "../hooks/useHashRoute";

export function TabBar({ route }: { route: Route }) {
  return (
    <nav className="tabs">
      {ROUTES.map((name) => (
        <a key={name} href={`#/${name}`} data-route={name} className={name === route ? "active" : undefined}>
          {ROUTE_TITLES[name]}
        </a>
      ))}
    </nav>
  );
}
```

- [ ] **Step 4: `App.tsx` ve `main.tsx`**

`frontend/src/App.tsx`:
```tsx
import { type ComponentType, useEffect } from "react";
import { TabBar } from "./components/TabBar";
import { type Route, ROUTE_TITLES, useHashRoute } from "./hooks/useHashRoute";
import { Events } from "./screens/Events";
import { Live } from "./screens/Live";
import { Settings } from "./screens/Settings";
import { Status } from "./screens/Status";

const SCREENS: Record<Route, ComponentType> = {
  status: Status,
  live: Live,
  events: Events,
  settings: Settings,
};

export function App() {
  const route = useHashRoute();
  const Screen = SCREENS[route];

  useEffect(() => {
    document.title = `${ROUTE_TITLES[route]} · KO Monitor`;
  }, [route]);

  return (
    <>
      <main id="screen">
        <Screen key={route} />
      </main>
      <TabBar route={route} />
    </>
  );
}
```

`frontend/src/main.tsx`:
```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";

if ("serviceWorker" in navigator) {
  if (import.meta.env.PROD) {
    // Built by vite-plugin-pwa from src/sw.ts; the dev server has no worker.
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch((error: unknown) => {
      console.error("service worker:", error);
    });
  }
  // A tapped notification asks an already open window to show its page (see src/sw.ts).
  navigator.serviceWorker.addEventListener("message", (event: MessageEvent) => {
    const data = event.data as { type?: unknown; url?: unknown } | null;
    if (data && data.type === "navigate" && typeof data.url === "string") {
      location.hash = new URL(data.url, location.origin).hash || "#/events";
    }
  });
}

const root = document.getElementById("root");
if (!root) throw new Error("#root missing from index.html");
createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

- [ ] **Step 5: Testlerin geçtiğini gör**

Run: `cd frontend; npm test`
Expected: `Test Files  12 passed (12)` / `Tests  55 passed (55)`

Run: `cd frontend; npx tsc -p tsconfig.json`
Expected: çıktı yok.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/hooks/useHashRoute.ts frontend/src/components/TabBar.tsx frontend/src/App.tsx frontend/src/main.tsx frontend/test/App.test.tsx frontend/test/security.test.ts
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: react app shell with hash routing, tab bar and raw-html/cdn guard" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: Service worker — `swHelpers.ts` ve `sw.ts`

**Files:**
- Create: `frontend/src/swHelpers.ts`, `frontend/src/sw.ts`
- Modify: `frontend/test/security.test.ts` (kaynak taraması `sw.ts`'yi de kapsamalı)
- Test: `frontend/test/swHelpers.test.ts`

**Interfaces:**
- Consumes: `workbox-core` (`cacheNames.precache`, `clientsClaim`), `workbox-precaching` (`precache`, `matchPrecache`); `vite-plugin-pwa` `injectManifest` `self.__WB_MANIFEST` yerine derleme listesini koyar (Task 1 `vite.config.ts`); push payload'u `messages.render()`; `main.tsx` `{type: "navigate", url}` mesajını dinler (Task 6).
- Produces:
  - `swHelpers.ts`: `RUNTIME_CACHE = "ko-monitor-runtime"`, `NETWORK_TIMEOUT_MS = 3000`, `DEFAULT_URL = "/#/events"`, `type RequestKind = "api" | "navigate" | "static" | "ignore"`, `classifyRequest(request: {method, url, mode}, origin: string): RequestKind`, `interface PushMessage {title, body, url, kind, ts}`, `parsePushPayload(data: {json(): unknown; text(): string} | null, nowS: number): PushMessage`, `notificationOptions(message): {title: string; options: NotificationOptions}`, `notificationTarget(data: unknown, origin: string): string`, `staleCaches(existing: readonly string[], keep: readonly string[]): string[]`.
  - `sw.ts` → derlemede `web/sw.js` (Task 8).

- [ ] **Step 1: Failing testleri yaz**

`frontend/test/security.test.ts` içinde:
```ts
    expect(Object.keys(sources)).toContain("../src/App.tsx");
```
yerine:
```ts
    expect(Object.keys(sources)).toContain("../src/App.tsx");
    expect(Object.keys(sources)).toContain("../src/sw.ts");
```

`frontend/test/swHelpers.test.ts`:
```ts
import { describe, expect, it } from "vitest";
import {
  classifyRequest,
  notificationOptions,
  notificationTarget,
  parsePushPayload,
  RUNTIME_CACHE,
  staleCaches,
} from "../src/swHelpers";

const ORIGIN = "https://pc.tailnet.ts.net";

function request(path: string, init: { method?: string; mode?: string } = {}) {
  return { method: init.method ?? "GET", mode: init.mode ?? "cors", url: path.includes("://") ? path : ORIGIN + path };
}

describe("classifyRequest", () => {
  it("never lets the worker answer API calls, POSTs, WebSockets or other hosts", () => {
    expect(classifyRequest(request("/api/status"), ORIGIN)).toBe("api");
    expect(classifyRequest(request("/api/stream?quality=low"), ORIGIN)).toBe("api");
    expect(classifyRequest(request("/api/push/test", { method: "POST" }), ORIGIN)).toBe("ignore");
    expect(classifyRequest(request("/", { method: "POST", mode: "navigate" }), ORIGIN)).toBe("ignore");
    expect(classifyRequest(request("wss://pc.tailnet.ts.net/api/stream"), ORIGIN)).toBe("ignore");
    expect(classifyRequest(request("https://example.com/x.js"), ORIGIN)).toBe("ignore");
  });

  it("tells page loads from static files", () => {
    expect(classifyRequest(request("/", { mode: "navigate" }), ORIGIN)).toBe("navigate");
    expect(classifyRequest(request("/assets/index-abc.js"), ORIGIN)).toBe("static");
    expect(classifyRequest(request("/icons/icon-192.png", { mode: "no-cors" }), ORIGIN)).toBe("static");
  });
});

describe("push payload", () => {
  it("shows messages.render() fields", () => {
    const payload = { title: "💀 Karakter öldü", body: "HP 0 · 14:05", url: "/#/events", kind: "dead", ts: 1700000000.5 };
    const message = parsePushPayload({ json: () => payload, text: () => "" }, 1);
    expect(notificationOptions(message)).toEqual({
      title: "💀 Karakter öldü",
      options: {
        body: "HP 0 · 14:05",
        tag: "dead-1700000000.5",
        icon: "/icons/icon-192.png",
        badge: "/icons/icon-192.png",
        data: { url: "/#/events" },
      },
    });
  });

  it("falls back to defaults and plain text", () => {
    expect(parsePushPayload(null, 42)).toEqual({ title: "KO Monitor", body: "", url: "/#/events", kind: "unknown", ts: 42 });
    const text = parsePushPayload(
      {
        json: () => {
          throw new SyntaxError("bad json");
        },
        text: () => "düz metin",
      },
      42,
    );
    expect(text.body).toBe("düz metin");
    expect(text.title).toBe("KO Monitor");
  });

  it("opens the notification URL, else the events screen", () => {
    expect(notificationTarget({ url: "/#/status" }, ORIGIN)).toBe(`${ORIGIN}/#/status`);
    expect(notificationTarget(null, ORIGIN)).toBe(`${ORIGIN}/#/events`);
    expect(notificationTarget({ url: 5 }, ORIGIN)).toBe(`${ORIGIN}/#/events`);
  });
});

describe("staleCaches", () => {
  it("deletes the hand-versioned caches of the old worker", () => {
    const precache = `workbox-precache-v2-${ORIGIN}/`;
    expect(staleCaches(["ko-monitor-v4", precache, RUNTIME_CACHE], [precache, RUNTIME_CACHE])).toEqual(["ko-monitor-v4"]);
  });
});
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `cd frontend; npx vitest run test/swHelpers.test.ts test/security.test.ts`
Expected: FAIL — `Failed to resolve import "../src/swHelpers"` ve `security › scans every source file`: `expected [ …(n) ] to include '../src/sw.ts'`

- [ ] **Step 3: Saf yardımcılar**

`frontend/src/swHelpers.ts`:
```ts
// Pure helpers of the service worker (src/sw.ts), kept free of worker globals so Vitest can test them.

export const RUNTIME_CACHE = "ko-monitor-runtime";
// A phone on a flaky tailnet connection should not stare at a blank screen: after this long the
// cached copy is used if there is one.
export const NETWORK_TIMEOUT_MS = 3000;
export const DEFAULT_URL = "/#/events";

/** "api", "navigate" and "static" are same-origin GETs; everything else (POST, ws:, other hosts) is "ignore". */
export type RequestKind = "api" | "navigate" | "static" | "ignore";

export function classifyRequest(
  request: { method: string; url: string; mode: string },
  origin: string,
): RequestKind {
  if (request.method !== "GET") return "ignore";
  const url = new URL(request.url);
  if (url.origin !== origin) return "ignore";
  if (url.pathname.startsWith("/api/")) return "api";
  return request.mode === "navigate" ? "navigate" : "static";
}

/** Payload is exactly messages.render(): {title, body, url, kind, ts}. */
export interface PushMessage {
  title: string;
  body: string;
  url: string;
  kind: string;
  ts: number;
}

export function parsePushPayload(data: { json(): unknown; text(): string } | null, nowS: number): PushMessage {
  const message: PushMessage = { title: "KO Monitor", body: "", url: DEFAULT_URL, kind: "unknown", ts: nowS };
  if (!data) return message;
  try {
    return { ...message, ...(data.json() as Partial<PushMessage>) };
  } catch {
    return { ...message, body: data.text() };
  }
}

export function notificationOptions(message: PushMessage): { title: string; options: NotificationOptions } {
  return {
    title: message.title,
    options: {
      body: message.body,
      tag: `${message.kind}-${message.ts}`,
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      data: { url: message.url },
    },
  };
}

/** Absolute URL a tapped notification opens (notification.data.url, else the events screen). */
export function notificationTarget(data: unknown, origin: string): string {
  const url = data && typeof data === "object" && "url" in data ? (data as { url: unknown }).url : null;
  return new URL(typeof url === "string" && url ? url : DEFAULT_URL, origin).href;
}

/** Cache names to delete on activate: everything this worker version does not use (e.g. "ko-monitor-v4"). */
export function staleCaches(existing: readonly string[], keep: readonly string[]): string[] {
  return existing.filter((name) => !keep.includes(name));
}
```

- [ ] **Step 4: Service worker**

`frontend/src/sw.ts`:
```ts
/// <reference lib="webworker" />
import { cacheNames, clientsClaim } from "workbox-core";
import { matchPrecache, precache } from "workbox-precaching";
import {
  classifyRequest,
  NETWORK_TIMEOUT_MS,
  notificationOptions,
  notificationTarget,
  parsePushPayload,
  RUNTIME_CACHE,
  staleCaches,
} from "./swHelpers";

declare const self: ServiceWorkerGlobalScope;

// vite-plugin-pwa replaces self.__WB_MANIFEST with the build's file list (revisioned), so a new
// build installs a new precache without a hand-bumped cache name.
precache(self.__WB_MANIFEST);
self.skipWaiting();
clientsClaim();

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(staleCaches(keys, [cacheNames.precache, RUNTIME_CACHE]).map((key) => caches.delete(key)))),
  );
});

function timeout(ms: number): Promise<never> {
  return new Promise((_, reject) => setTimeout(() => reject(new Error("network timeout")), ms));
}

async function cachedCopy(request: Request): Promise<Response | undefined> {
  return (await caches.match(request, { cacheName: RUNTIME_CACHE })) ?? (await matchPrecache(request.url));
}

async function networkFirst(request: Request, navigate: boolean): Promise<Response> {
  const network = fetch(request).then((response) => {
    if (response.ok) {
      const copy = response.clone();
      void caches.open(RUNTIME_CACHE).then((cache) => cache.put(request, copy));
    }
    return response;
  });
  network.catch(() => undefined); // a late failure after the timeout is not an unhandled rejection
  try {
    return await Promise.race([network, timeout(NETWORK_TIMEOUT_MS)]);
  } catch {
    const cached = await cachedCopy(request);
    if (cached) return cached;
    try {
      return await network; // timed out with nothing cached: a slow answer beats none
    } catch {
      // Offline: only page loads get the app shell; a missing script or icon must not become HTML.
      if (navigate) {
        const shell = await matchPrecache("/index.html");
        if (shell) return shell;
      }
      return Response.error();
    }
  }
}

// Network first (the PC is the only source of truth), cached copy when slow or offline.
// /api/*, non-GET requests and WebSockets are never answered by the worker.
self.addEventListener("fetch", (event) => {
  const kind = classifyRequest(event.request, self.location.origin);
  if (kind !== "navigate" && kind !== "static") return;
  event.respondWith(networkFirst(event.request, kind === "navigate"));
});

self.addEventListener("push", (event) => {
  const { title, options } = notificationOptions(parsePushPayload(event.data, Date.now() / 1000));
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = notificationTarget(event.notification.data, self.location.origin);
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      for (const client of windows) {
        if ("focus" in client) {
          client.postMessage({ type: "navigate", url: target });
          return client.focus();
        }
      }
      return self.clients.openWindow(target);
    }),
  );
});
```

- [ ] **Step 5: Testlerin ve iki tip denetiminin geçtiğini gör**

Run: `cd frontend; npm test`
Expected: `Test Files  13 passed (13)` / `Tests  61 passed (61)`

Run: `cd frontend; npm run typecheck`
Expected: `> tsc -p tsconfig.json && tsc -p tsconfig.sw.json` satırından sonra hata yok, çıkış kodu 0.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/swHelpers.ts frontend/src/sw.ts frontend/test/swHelpers.test.ts frontend/test/security.test.ts
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: typescript service worker with workbox precache, network-first timeout and push handlers" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 8: `web/`'i derlenmiş çıktıyla değiştir; `tests/test_web.py`, kurulum belgesi ve üst spec

**Files:**
- Modify (derleme çıktısı): `web/index.html`, `web/sw.js`, `web/manifest.webmanifest`, `web/icons/*.png`; Create: `web/assets/index-<hash>.js`, `web/assets/index-<hash>.css`; Delete (derleme `emptyOutDir` ile siler): `web/js/app.js`, `web/js/api.js`, `web/js/ui.js`, `web/js/screens/events.js`, `web/js/screens/live.js`, `web/js/screens/settings.js`, `web/js/screens/status.js`, `web/styles.css`
- Modify: `tests/test_web.py` (tamamı), `docs/setup.md` (sona bölüm), `docs/superpowers/specs/2026-09-15-ko-monitor-design.md:23,61`
- Test: `tests/test_web.py`

**Interfaces:**
- Consumes: `frontend/` (Task 1–7), `npm run build` (Task 1 `package.json`), `vite.config.ts` `outDir: "../web"`; `ko_monitor.api.WEB_DIR`, `create_app(..., extra_hosts=["testserver"])`; `helpers.ROOT`; `scripts/make_icons.py` `render_icon`, `main`, `BACKGROUND`, `ICON_DIR` (Task 1).
- Produces: derlenmiş `web/` (commit edilir) — `/index.html` bir `/assets/*.js` modülüne ve `/assets/*.css`'e bağlanır, `/sw.js` precache listesi `web/`'deki diğer her dosyayı içerir. Task 9 bunu yeniden derleyip `git status --porcelain web` ile doğrular.

- [ ] **Step 1: `tests/test_web.py`'yi derlenmiş çıktıya göre yeniden yaz (failing)**

`tests/test_web.py` (dosyanın tamamı):
```python
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
    precached = set(re.findall(r'"url":"([^"]+)"', text))
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
```

- [ ] **Step 2: Testlerin eski `web/`'e karşı başarısız olduğunu gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_web.py -q`
Expected: FAIL — `5 failed, 11 passed`: `test_bundle_and_stylesheet_are_served`, `test_index_links_manifest_apple_icon_and_built_bundle`, `test_old_hand_written_files_are_gone`, `test_service_worker_precaches_every_built_file`, `test_bundle_has_every_screen_in_tab_order`.

- [ ] **Step 3: Derle**

Run: `cd frontend; npm run build`
Expected (çıkış kodu 0; hash'ler farklı olabilir):
```
> tsc -p tsconfig.json && tsc -p tsconfig.sw.json
vite v8.3.0 building client environment for production...
../web/index.html                   0.81 kB
../web/assets/index-<hash>.css      4.30 kB
../web/assets/index-<hash>.js     234.20 kB
PWA v1.3.0
Building src/sw.ts service worker ("es" format)...
 WARN  inlineDynamicImports option is deprecated, please use codeSplitting: false instead.
../web/sw.mjs  14.16 kB
mode      injectManifest
precache  7 entries (277.50 KiB)
files generated
  ../web/sw.js
```
`WARN inlineDynamicImports` satırı vite-plugin-pwa'nın SW derlemesinden gelir, zararsızdır (PowerShell stderr satırını `NativeCommandError` kutusuyla gösterebilir). `sw.mjs` ara dosyadır, çıktıda kalmaz.

Run (kökten): `Get-ChildItem web -Recurse -File | ForEach-Object { $_.FullName.Substring((Resolve-Path web).Path.Length + 1) }`
Expected (tam 8 dosya): `assets\index-<hash>.css`, `assets\index-<hash>.js`, `icons\icon-180.png`, `icons\icon-192.png`, `icons\icon-512.png`, `index.html`, `manifest.webmanifest`, `sw.js` — `js\` ve `styles.css` yok.

- [ ] **Step 4: Python testlerinin geçtiğini gör**

Run: `.venv\Scripts\python.exe -m pytest tests/test_web.py -q`
Expected: `16 passed`

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: `296 passed, 2 skipped` (eski `test_web.py`'nin 26 testi yerine 16; `test_api.py`/`test_stream.py` değişmeden geçer).

- [ ] **Step 5: `docs/setup.md` geliştirici bölümü**

`docs/setup.md` sonuna (8. bölümdeki tablodan sonra) ekle; kullanıcı adımları (1–8) değişmez:
````markdown

## 9. Arayüzü değiştirmek (geliştirici)

Telefon uygulamasının kaynağı `frontend\` klasöründedir (React + Vite + TypeScript). `web\` klasörü derleme çıktısıdır: elle düzenlenmez, her değişiklikten sonra yeniden derlenip git'e eklenir. Ajanı çalıştırmak için Node.js gerekmez; yalnızca arayüzü değiştirirken gerekir (Node.js 24).

```powershell
cd frontend
npm ci            # package-lock.json'daki sürümleri kurar
npm test          # arayüz testleri (Vitest)
npm run build     # tip denetimi + derleme → ..\web (önce temizlenir)
cd ..
.venv\Scripts\python.exe -m pytest -q tests\test_web.py
git add frontend web
```

- `npm run dev`: `http://localhost:5173` adresinde geliştirme sunucusu; `/api` istekleri ve canlı yayın çalışan ajana (`http://127.0.0.1:8765`) yönlendirilir. Service worker ve bildirimler yalnızca derlenmiş sürümde (`http://127.0.0.1:8765`) çalışır.
- İkonları yeniden üretmek: `.venv\Scripts\python.exe scripts\make_icons.py` (`frontend\public\icons`'a yazar), ardından `npm run build`.
````

- [ ] **Step 6: Üst spec'teki "vanilla JS" sapma notunu güncelle**

`docs/superpowers/specs/2026-09-15-ko-monitor-design.md` §2 tablosunda:
```markdown
| **Telefon: iPhone + PWA (derleme adımı olmayan HTML/CSS/JavaScript).** | Expo ile bildirim için yıllık Apple geliştirici hesabı gerekir; PWA ücretsiz. Bilgisayarda Node.js kurulu değil; yeni yazılım kurmamak için React + Vite yerine derleme gerektirmeyen vanilla ES modülleri seçildi (Plan 2). |
```
yerine:
```markdown
| **Telefon: iPhone + PWA (React + Vite + TypeScript; derlenmiş çıktı `web/`).** | Expo ile bildirim için yıllık Apple geliştirici hesabı gerekir; PWA ücretsiz. Plan 2'de Node.js olmadığı için vanilla ES modülleriyle yazılmıştı; React'e taşıma: `docs/superpowers/specs/2026-09-15-ko-monitor-react-pwa-design.md`. |
```

§3 bileşen tablosunda:
```markdown
| `pwa` | Vanilla HTML/CSS/JavaScript ES modülleri, derleme adımı yok; manifest ve service worker elle yazılır, ikonlar `scripts/make_icons.py` ile üretilir. (İlk taslakta React + Vite + TypeScript + `vite-plugin-pwa` idi; bu PC'de Node.js olmadığı için değiştirildi.) | — |
```
yerine:
```markdown
| `pwa` | React + Vite + TypeScript kaynağı `frontend/`; `npm run build` çıktısı `web/` (commit edilir, FastAPI sunar). Service worker `src/sw.ts` + `vite-plugin-pwa` injectManifest; ikonlar `scripts/make_icons.py` ile üretilir. Ayrıntı: `docs/superpowers/specs/2026-09-15-ko-monitor-react-pwa-design.md`. | React, Vite, vite-plugin-pwa, Workbox |
```

- [ ] **Step 7: Commit**

`git add web` silinen eski dosyaları da stage eder (`node_modules` `web/` altında değildir):
```powershell
git add web tests/test_web.py docs/setup.md docs/superpowers/specs/2026-09-15-ko-monitor-design.md
git status --short
git -c user.name="Serdar Gavas" -c user.email="serdargavas@gmail.com" commit -m "feat: serve the react build from web and validate the built output" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```
Expected `git status --short` (commit öncesi): `D  web/js/api.js`, `D  web/js/app.js`, `D  web/js/screens/events.js`, `D  web/js/screens/live.js`, `D  web/js/screens/settings.js`, `D  web/js/screens/status.js`, `D  web/js/ui.js`, `D  web/styles.css`, `A  web/assets/index-<hash>.css`, `A  web/assets/index-<hash>.js`, `M  web/index.html`, `M  web/sw.js`, `M  tests/test_web.py`, `M  docs/setup.md`, `M  docs/superpowers/specs/2026-09-15-ko-monitor-design.md` (ikonlar ve manifest bayt olarak aynıysa listede görünmez); `??` satırlarında yalnızca önceden var olan `samples/_auto/`, `samples/_review/`.

---

### Task 9: Tam doğrulama

Bu görev kod yazmaz; bir adım başarısız olursa ilgili görevin koduna dönülür ve düzeltme ayrı bir commit olur.

**Files:**
- Değişiklik yok (yalnızca doğrulama).

**Interfaces:**
- Consumes: Task 1–8'in tüm çıktıları.
- Produces: yok.

- [ ] **Step 1: Kilit dosyasından temiz kurulum**

Run: `cd frontend; npm ci`
Expected: `added 412 packages` civarı; peer dependency hatası yok (yalnızca `npm warn deprecated glob@11.1.0`).

- [ ] **Step 2: Arayüz testleri**

Run: `cd frontend; npm test`
Expected: `Test Files  13 passed (13)` / `Tests  61 passed (61)`

- [ ] **Step 3: Derlenmiş `web/` güncel mi**

Run: `cd frontend; npm run build`
Expected: Task 8 Step 3'teki çıktı, çıkış kodu 0.

Run (kökten): `git status --porcelain web`
Expected: çıktı yok (derleme deterministiktir; commit edilen `web/` kaynakla aynı). Çıktı varsa `frontend/` değişiklikleri derlenmeden commit edilmiştir: yeniden derle, `git add web`, `fix: rebuild web` commit'i at.

- [ ] **Step 4: Yasak kalıplar ve istenmeyen dosyalar**

Run: `Get-ChildItem frontend\src -Recurse -File | Select-String -Pattern 'dangerouslySetInnerHTML', 'innerHTML', 'https?://'`
Expected: çıktı yok.

Run: `git status --porcelain`
Expected: yalnızca `?? samples/_auto/` ve `?? samples/_review/`; `frontend/node_modules` görünmez.

Run: `git ls-files frontend | Select-String node_modules`
Expected: çıktı yok. `git ls-files frontend/package-lock.json` → `frontend/package-lock.json`.

- [ ] **Step 5: Python test paketi**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: `296 passed, 2 skipped`

- [ ] **Step 6: Elle kontrol (PC tarayıcısı, isteğe bağlı)**

Canlı `python -m ko_monitor run` süreci zaten çalışıyorsa (durdurma, yeniden başlatma):
1. `http://127.0.0.1:8765` → dört sekme, Durum verisi 5 sn'de bir yenilenir (DevTools → Network: `/api/status`; başka sekmeye geçince durur).
2. DevTools → Application → Service Workers: `/sw.js` etkin, kapsam `/`; Cache Storage: `workbox-precache-v2-…` ve `ko-monitor-runtime` var, eski `ko-monitor-v4` silinmiş. `/api/*` istekleri "from ServiceWorker" değildir.
3. Olaylar: liste + 24 saat çizelgesi; Canlı: görüntü ya da "Oyun penceresi bulunamadı", kalite düğmesi tek yeniden bağlanma yapar ve sayfa yenilenince hatırlanır.
4. Geliştirme sunucusu: `cd frontend; npm run dev` → `http://localhost:5173`: Durum verisi gelir, Canlı 1008 ile reddedilmez, Ayarlar → Test bildirimi 403 almaz (proxy Host/Origin'i düzeltir). Ctrl+C ile kapat.

- [ ] **Step 7: iPhone elle kontrol listesi (kullanıcı yapar; uygulayıcı çalıştırmaz)**

1. Ana ekrandaki KO Monitor simgesiyle aç: güncelleme sonrası ekranlar açılıyor (eski önbellek bozmuyor).
2. Ayarlar → Bildirimleri aç → Test bildirimi gönder: "🔔 Test bildirimi" gelir; dokununca uygulama Olaylar ekranında açılır.
3. Canlı: telefon yan çevrilince tam ekran; uygulamadan çıkınca yayın durur.
4. Yeni kurulum: Safari → Paylaş → Ana Ekrana Ekle hâlâ çalışır (apple-touch-icon görünür).
