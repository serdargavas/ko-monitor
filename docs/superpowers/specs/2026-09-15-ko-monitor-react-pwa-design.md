# KO Monitor — PWA'nın React'e taşınması (Tasarım)

**Tarih:** 2026-09-15
**Durum:** Onaylandı (kullanıcı, sohbet içinde); spec incelemesi bekliyor
**Üst spec:** `docs/superpowers/specs/2026-09-15-ko-monitor-design.md` (§7 PWA, §3 bileşenler)

## 1. Amaç

Plan 2'de düz HTML/CSS/JS ES modülleriyle (derleme adımı yok, Node.js kurulu değildi) yazılan telefon uygulamasını **React + Vite + TypeScript**'e taşımak. Node.js v24.19.0 artık kurulu.

**Başarı ölçütü:** Kullanıcı açısından hiçbir şey değişmez — aynı dört ekran (Durum, Canlı, Olaylar, Ayarlar), aynı Türkçe metinler, aynı API, aynı bildirim davranışı, iPhone'da ana ekrana ekleme aynı şekilde çalışır; kod tipli, bileşenlere ayrılmış ve gerçek JS testleriyle korunur.

**Kapsam dışı:** görsel yeniden tasarım, yeni özellik, API/sunucu değişikliği (tek istisna §6'daki statik servis testleri), React Native/Expo.

## 2. Kararlar

| Karar | Gerekçe |
|---|---|
| **Kaynak `frontend/`, derlenmiş çıktı `web/`, çıktı git'e dahil** (yaklaşım A) | FastAPI `web/`'i değişmeden sunar; oyun PC'sinde çalışmak için Node gerekmez; kurulum rehberi kullanıcı için aynı kalır. Bedeli: derlenmiş dosyalar commit'lere girer. |
| Vite + React 19 + TypeScript | Kullanıcı React biliyor; Vite hızlı derleme ve geliştirme sunucusu. |
| Hash tabanlı yönlendirme (`/#/status`, `/#/live`, `/#/events`, `/#/settings`) | Push bildirim payload'ındaki `url: "/#/events"` sözleşmesi ve mevcut service worker davranışı korunur. |
| `vite-plugin-pwa` `injectManifest` modu + kendi `sw.ts` dosyamız | Önbellek listesi ve sürümü otomatik üretilir (elle `CACHE = v4` artırma biter); push/notificationclick/ağ zaman aşımı mantığı bizim kodumuzda kalır. Vite 8 ile uyumsuzsa: aynı `sw.ts`'yi küçük bir derleme betiğiyle (Vite build sonrası dosya listesi enjekte ederek) üret. |
| Harici UI/durum/yönlendirme kütüphanesi yok; yönlendirme için küçük bir `useHashRoute` hook'u (`location.hash` + `hashchange`) | YAGNI; dört sabit ekran için router kütüphanesi gereksiz. |
| Test: Vitest + @testing-library/react (jsdom) | Plan 2'de JS yalnızca yapısal (metin arama) testlerle korunuyordu; artık davranış testleri. |

Sürümler (2026-09-15 npm): vite 8.3.0, react 19.3.0, vite-plugin-pwa 1.3.0, @vitejs/plugin-react 6.1.1, vitest 5.0.1, @testing-library/react 16.3.3, typescript 7.0.2. Plan aşamasında birbirleriyle uyumları doğrulanır ve tam sürümler `package-lock.json` ile sabitlenir.

## 3. Yapı

```
frontend/
  package.json, package-lock.json, tsconfig.json, vite.config.ts, index.html
  public/icons/icon-180.png, icon-192.png, icon-512.png   (mevcut web/icons'tan taşınır)
  src/
    main.tsx            (React kök, service worker kaydı)
    App.tsx             (sekme çubuğu + hash router + ekran seçimi)
    api.ts              (tipli API istemcisi)
    types.ts            (AgentStatus, Snapshot, EventItem, StreamStatus …)
    labels.ts           (STATE_LABELS, EVENT_LABELS — messages.TITLES ile aynı)
    format.ts           (sayı/para tr-TR biçimi, "X sn önce", saat)
    hooks/usePolling.ts
    hooks/useStream.ts
    hooks/useVisibility.ts
    hooks/useHashRoute.ts
    timeline.ts         (buildSegments — saf fonksiyon)
    screens/Status.tsx, Live.tsx, Events.tsx, Settings.tsx
    components/         (StateBadge, HpBar, InventoryCard, EventList, Timeline, TabBar)
    push.ts             (izin → VAPID anahtarı → subscribe → POST; 5 sn hazır olma zaman aşımı)
    sw.ts               (service worker)
    styles.css          (mevcut web/styles.css'ten taşınır)
  test/ …               (Vitest testleri)
web/                    (npm run build çıktısı — commit edilir; elle düzenlenmez)
```

`scripts/make_icons.py` kalır; çıktısı `frontend/public/icons/`'a yazacak şekilde güncellenir.

## 4. Bileşen sözleşmeleri

- **api.ts:** `getStatus()`, `getSnapshots(since)`, `getEvents(limit)`, `getVapidKey()`, `subscribe(sub)`, `sendTest()`, `streamUrl(quality)` (ws/wss sayfa protokolünden). Alan adları sunucu yanıtlarıyla birebir (`src/ko_monitor/status.py` `AgentStatus.to_dict`, `api.py`); `types.ts` bunları tipler.
- **usePolling(fn, intervalMs):** görünürken `intervalMs`'de bir çağırır, `document.hidden` iken durur, görünür olunca hemen yeniler, unmount'ta temizlenir; hata durumunda son veriyi ve hata bayrağını döner ("Bağlanamadı" mesajı).
- **useStream(quality, enabled):** tek WebSocket; `binaryType = "blob"`; ikili mesaj → `URL.createObjectURL` ile kare, önceki URL revoke; metin mesaj → `{status}`; kopunca sınırlı artan bekleme ile yeniden bağlanma; `enabled=false`, sayfa gizli veya unmount → bağlantı kapanır ve zamanlayıcılar temizlenir; kalite değişince bir kez yeniden bağlanır; 1008 ile kapanırsa yeniden denemez ve hata gösterir.
- **timeline.buildSegments(snapshots, start, end, maxGapS=90):** mevcut `events.js` davranışının aynısı (bitiş = max(istemci şimdi, en yeni snapshot ts), boşluklar "veri yok").
- **push.ts:** mevcut `settings.js` akışı (standalone/push desteği algılama ve Türkçe ipuçları, VAPID anahtarı değişince yeniden abone olma, `serviceWorker.ready` için 5 sn zaman aşımı).
- **sw.ts:** Workbox precache (derleme dosya listesi); gezinme ve statik dosyalar için ağ-öncelikli + 3 sn zaman aşımı, başarısızsa önbellek, `index.html` yedeği yalnızca gezinmelerde; `/api/*`, POST ve WebSocket asla önbelleğe alınmaz/araya girilmez; `push` olayı `render()` payload'ını (title, body, url, kind, ts) gösterir; `notificationclick` açık pencereyi odaklar veya `url`'i açar; eski önbellekler temizlenir.
- **Güvenlik:** `dangerouslySetInnerHTML` yasak (OCR metinleri React ile güvenli yazılır); harici CDN/ağ kaynağı yok.

## 5. Geliştirme ve derleme

- `npm run dev`: Vite geliştirme sunucusu; `/api` ve `/api/stream` (WebSocket) `http://127.0.0.1:8765`'e yönlendirilir (proxy Host/Origin başlıklarını sunucunun güvenlik kontrollerinden geçecek şekilde ayarlar).
- `npm run build`: tip denetimi + derleme → `web/` (önce temizlenir), service worker ve manifest dahil.
- `npm test`: Vitest.
- Python testleri (`tests/test_web.py`) derlenmiş `web/` çıktısını doğrular: `index.html`, manifest (standalone, ikonlar), `sw.js` var ve doğru içerik türleriyle sunuluyor, dört ekranın derlenmiş paket içinde bulunması.
- `docs/setup.md` kullanıcı adımları değişmez; "arayüzü değiştirmek için" kısa bir geliştirici notu eklenir (`cd frontend`, `npm ci`, `npm run build`, derlenmiş `web/` commit edilir).

## 6. Test

| Birim | Test |
|---|---|
| `buildSegments` | boş liste, sıralı/ardışık aynı durum birleşmesi, 90 sn boşluk, istemci saati geride (en yeni ts > şimdi), tek snapshot |
| `format.ts` | tr-TR para gruplama, "X sn/dk önce", null değerler "—" |
| `usePolling` | sahte zamanlayıcı: aralık, gizliyken durma, görünür olunca yenileme, unmount temizliği, hata bayrağı |
| `useStream` | sahte WebSocket: tek bağlantı, kalite değişiminde tek yeniden bağlanma, gizliyken kapanma, backoff sınırı, revokeObjectURL, 1008'de yeniden denememe |
| Ekranlar | sahte API ile: Durum (rozet, HP, envanter, son olaylar), Olaylar (liste + çizelge), Ayarlar (push desteklenmiyor/izin reddedildi metinleri), Canlı (bağlanıyor/kare/durum metni) |
| `sw.ts` | saf yardımcılar (istek sınıflandırma: api/gezinme/statik; bildirim payload'ından seçenekler) birim testleri |
| Python | mevcut API/stream testleri değişmeden geçer; `test_web.py` derlenmiş çıktıya göre güncellenir |

Elle kontrol (iPhone, kullanıcı): ana ekrana ekleme, bildirim izni + test bildirimi, bildirime dokununca Olaylar, Canlı yatay tam ekran, güncelleme sonrası ekranların açılması.

## 7. Geçiş

- Tek seferde taşınır; eski `web/js/*`, `web/sw.js`, `web/styles.css`, `web/index.html` derleme çıktısıyla değiştirilir.
- Service worker adı `/sw.js` ve kapsamı `/` aynı kalır; yeni SW eski önbellekleri siler, böylece yüklü PWA güncellemede bozulmaz.
- Üst spec §2/§3'teki "React yerine düz JS" sapma notu, bu taşımayı gösterecek şekilde güncellenir.
