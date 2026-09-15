# KO Monitor — Tasarım

**Tarih:** 2026-09-15
**Durum:** Taslak (kullanıcı onayı bekliyor)

## 1. Amaç

Knight Online private sunucusunda ("Knight Evolution" client'ı, HomekoWorld) oynarken:

- Karakter öldüğünde, envanter dolduğunda, sunucudan düşüldüğünde veya izleme bozulduğunda **iPhone'a birkaç saniye içinde bildirim** gelsin.
- Oyun açıkken **dakikada bir durum kaydı** (health check) tutulsun, telefondan görülebilsin.
- Telefondan **tek dokunuşla canlı oyun ekranı** izlenebilsin (evde ve dışarıda).

Kullanım senaryoları: Knight Genie açıkken bilgisayar başında değilken (AFK) ve bilgisayar başında başka işle uğraşırken.

## 2. Kısıtlar ve temel kararlar

| Karar | Gerekçe |
|---|---|
| **Sadece ekran okuma (read-only).** Bellek okuma, paket dinleme, oyuna tuş/tıklama gönderme yok. | Client ACME anti-cheat ile korunuyor; bunlar ban riski ve sunucu kuralı ihlali. |
| **Ekran yakalama: Windows Graphics Capture** (`windows-capture` paketi). | Spike'ta hem görünürken hem başka pencerenin arkasındayken doğru kare verdi. |
| **Ajan: Python 3.12.** | Görüntü işleme (OpenCV, OCR) ekosistemi en güçlü. |
| **Telefon: iPhone + PWA (React).** | Expo ile bildirim için yıllık Apple geliştirici hesabı gerekir; PWA ücretsiz. |
| **Erişim: Tailscale + `tailscale serve`.** | Port açmadan dışarıdan erişim; PWA ve Web Push için gereken geçerli HTTPS sertifikası. |
| **Dış canlılık kontrolü: healthchecks.io → ntfy.** | PC/internet/ajan çökerse ajan kendi bildirimini atamaz. |

### Spike bulguları (2026-09-15)

- Client: `C:\HomekoWorld\Binaries\Client.acme`, pencere başlığı `Knight Evolution`, borderless 2560x1440, ana monitörde. Oyun log dosyası yazmıyor.
- `PrintWindow`: siyah kare → kullanılamaz.
- Masaüstünden kopyalama: sadece oyun öndeyken çalışır.
- **Windows Graphics Capture: oyun önde ve kısmen/tamamen örtülü iken çalışır.** Küçültülmüş (minimize) pencerede kare üretilmez.
- HUD: HP/MP sol üstte sayı olarak (`9718/9996`). Bilgi chat'i sağ altta (`Picked up N Coins.` vb.). Para ve envanter sadece envanter penceresi açıkken görünür.

## 3. Mimari

```
┌─────────────── PC: Python ajanı (tek süreç) ───────────────┐
│ process_watch → capture → detectors → monitor               │
│                                     ├→ storage (SQLite)     │
│                                     ├→ notifier (Web Push)  │
│                                     └→ heartbeat (hc.io)    │
│ api (FastAPI): durum, geçmiş, olaylar, canlı yayın, PWA     │
└──────────────────────┬──────────────────────────────────────┘
                       │ tailscale serve (HTTPS)
                iPhone PWA: Durum · Canlı · Olaylar · Ayarlar
```

### Bileşenler

| Bileşen | Görev | Bağımlılık |
|---|---|---|
| `process_watch` | `Client.acme` süreci var mı; açıldı/kapandı olayları. | psutil |
| `capture` | Oyun penceresinin son karesini verir; pencere durumu: `ok`, `minimized`, `not_found`, `black`. Kopunca yeniden bağlanır (artan bekleme). | windows-capture |
| `detectors` | Saf fonksiyonlar: kare → `Readings`. Ekrana dair tüm bilgi yalnızca burada. | OpenCV, RapidOCR, `calibration.json` |
| `monitor` | `Readings` akışı + saat → durum makinesi, olaylar, dakikalık snapshot. | detectors, storage, notifier, heartbeat |
| `notifier` | Arayüz: `send(event)`. v1 uygulaması: Web Push. Sonradan Pushover eklenebilir. | pywebpush |
| `heartbeat` | Oyun izlenirken dakikada bir healthchecks.io ping; oyun normal kapanınca kontrolü duraklatır. | httpx |
| `storage` | SQLite: `snapshots`, `events`, `push_subscriptions`. | sqlite3 |
| `api` | FastAPI; yalnızca `127.0.0.1` üzerinde dinler; PWA'nın build dosyalarını da sunar. | FastAPI, uvicorn |
| `pwa` | React + Vite + TypeScript + `vite-plugin-pwa`. | — |

`Readings` alanları (her biri okunamazsa `None` = bilinmiyor):
`hud_visible` (bool: HP yazısı geçerli okundu mu), `hp`, `hp_max`, `zone`, `revive_dialog`, `login_screen`, `disconnect_dialog`, `dialog_text` (ekranın ortasındaki açık pencerenin okunan yazısı; pencere yoksa `None`), `chat_events` (liste: `inventory_full`, …), `inventory_open`, `money`, `slots_used`, `slots_total`, `frame_diff`.

## 4. Tespit

- **Bölgeler (ROI):** 2560x1440 ve UI ölçeği 1.0 için `calibration.json` içinde tanımlı.
- **Yazılar (HP, para, bölge adı):** sabit bölgede RapidOCR yalnızca tanıma modu (`use_det=False`). Spike ölçümü: ~15 ms; gerçek karelerde `9718/9996` ve `Ronark Land (428, 506)` hatasız okundu. (Rakam şablonlarına gerek kalmadı.)
- **Ekranlar ve envanter (envanter başlığı, giriş/sunucu seçim ekranı, boş slot):** yalnızca şablon eşleştirme, eşik değeri kalibrasyonda. Diriltme ve bağlantı koptu pencereleri ayrı şablon değildir: ikisi de aşağıdaki orta penceredir (çerçeve şablonu + yazı OCR).
- **Orta pencere (ölüm ve bağlantı koptu bildirimi aynı pencere):** ölüm bildirimi ile bağlantı koptu bildirimi ekranın ortasındaki aynı pencerede, yalnızca farklı yazıyla çıkar; disconnect sırasında HUD arkada görünür kalır. Pencere, yazıdan bağımsız sabit bir çerçeve parçasının (sol üst köşe süsü) şablonuyla bulunur; açıksa yazı satırları sabit bölgelerden RapidOCR tanıma modunda okunur (`dialog_text`). Bu OCR yalnızca çerçeve bulunduğunda çalışır ve yazı bölgelerinin pikselleri bir önceki okumayla aynıyken atlanır (önceki sonuç kullanılır); pencere kapanınca bu önbellek sıfırlanır. Yazı `calibration.json` içindeki ifade listeleriyle sınıflanır: diriltme ifadeleri → `revive_dialog`, disconnect ifadeleri → `disconnect_dialog`, yoksayılacak ifadeler → pencere yok sayılır. Hiçbir listeye uymayan yazı "tanınmayan pencere"dir (bkz. §5).
- **Chat mesajları:** RapidOCR algılama + tanıma (spike ölçümü ~0.8 sn/çağrı); yalnızca HUD görünürken çalışır; bir önceki okumada olmayan (yeni) satırlar değerlendirilir; anahtar ifadeler `calibration.json`'da.
- **Belirsiz okuma** (eşik altı eşleşme, düşük OCR güveni) → `None`; asla ölüm/disconnect sayılmaz.

### Kalibrasyon

`python -m ko_monitor snap <etiket>` komutu o anki kareyi `samples/<etiket>/<zaman>.png` olarak kaydeder. Gerekli örnekler:

1. `death` — ölüm ekranı
2. `inventory_full` — dolu mesajının chat'te göründüğü an
3. `inventory_open` — envanter penceresi açık, para görünür
4. `disconnect` — bağlantı koptu penceresi ve/veya giriş ekranı
5. `normal` — sıradan oyun (negatif örnek)

Chat'teki gerçek "envanter dolu" ve ölüm/disconnect metinleri bu örneklerden alınıp `calibration.json`'a yazılır. Aynı örnekler detector testlerinin verisidir.

## 5. İzleme döngüsü ve bildirimler

### Zamanlama

| Döngü | Aralık | Ne yapar |
|---|---|---|
| Süreç kontrolü (oyun kapalıyken) | 10 sn | `Client.acme` açıldı mı |
| Hızlı kontrol (oyun açıkken) | 2 sn | kare → okumalar → kurallar |
| Health check (oyun açıkken) | 60 sn | `snapshots` kaydı + healthchecks.io ping |

### Durum makinesi

```
Kapalı ──süreç açıldı──> Canlı                   (HUD görülene kadar, en fazla 5 dk: kötü durum yok)
Canlı ──> Ölü | Disconnect | Donmuş | Kör        (girişte bildirim)
Ölü/Disconnect/Donmuş/Kör ──düzeldi──> Canlı    (olay kaydı, bildirim yok)
(herhangi) ──süreç kayboldu──> Kapalı            (bildirim: "Oyun kapandı")
```

Envanter dolu, durum makinesinden bağımsız bir olaydır.

Aynı anda birden fazla koşul doğruysa **öncelik:** Kapalı > Kör > Disconnect > Ölü > Donmuş > Canlı. Yalnızca en yüksek öncelikli durum geçerlidir; örneğin ölüm ekranı sabit kaldığı için ayrıca "Donmuş" bildirimi gönderilmez (Donmuş yalnızca Canlı durumdayken değerlendirilir).

### Kurallar (varsayılanlar, `config.toml` ile değiştirilebilir)

| Olay | Koşul | Onay süresi | Tekrar |
|---|---|---|---|
| Ölüm | `hp == 0` **veya** `revive_dialog` | art arda 2 okuma (~4 sn) | durum değişene kadar tek |
| Envanter dolu | `inventory_full` chat olayı **veya** (`inventory_open` ve `slots_used == slots_total`) | chat en fazla 4 sn'de bir okunur (~4-6 sn) | en fazla 10 dk'da bir |
| Disconnect (kesin) | `login_screen` **veya** `disconnect_dialog` | art arda 2 okuma (~4 sn) | durum değişene kadar tek |
| Disconnect (pencere yazısı) | orta pencere açık ve yazısı bir disconnect ifadesi içeriyor (`disconnect_dialog`); bildirimde pencere yazısı | art arda 2 okuma (~4 sn) | durum değişene kadar tek |
| Tanınmayan pencere, karakter canlı | orta pencere açık, yazısı hiçbir listeye uymuyor ve `hp > 0`; bildirimde pencere yazısı (ilk gerçek disconnect yazıyı öğretir) | 30 sn kesintisiz (`unknown_dialog_s`) | durum değişene kadar tek |
| Disconnect (dolaylı) | süreç açık ve `hud_visible == False` | 15 sn kesintisiz | durum değişene kadar tek |
| Oyun kapandı | izlenirken süreç kayboldu | anında | tek |
| Donmuş | `frame_diff` ≈ 0 | 120 sn kesintisiz | durum değişene kadar tek |
| Kör | capture `minimized`/`not_found`/`black` **veya** kare okunamıyor (çözünürlük uyuşmazlığı, detector hatası) | 60 sn kesintisiz (bu sürede mevcut durum korunur) | durum değişene kadar tek |

- Ajan başladığında oyun zaten kapalıysa "Oyun kapandı" bildirimi gönderilmez.
- Oyun açıldıktan sonra HUD ilk kez görülene kadar (en fazla 5 dk, `startup_grace_s`) Disconnect/Kör/Donmuş/Ölü bildirimi verilmez (giriş, sunucu ve karakter seçim ekranları). Bu sürede koşul sayaçları işlemez: HUD görülünce sayaçlar sıfırdan başlar; süre HUD görülmeden dolarsa kurallar o andan itibaren normal işler (ör. Disconnect (dolaylı) 15 sn sonra). Envanter dolu olayı bundan etkilenmez. Oyun her yeniden açıldığında bu süre yeniden başlar.
- Kötü durumdan çıkış olumlu okuma ister: Ölü → Canlı ancak `hp > 0` okunduğunda, Disconnect → Canlı ancak HUD görüldüğünde; pencere kaynaklı Disconnect → Canlı ancak pencere kapanmış ve HUD görülmüşken. Ölüm penceresi de aynı orta pencere olduğundan, pencere kaynaklı Disconnect sırasında HUD görünürken art arda 2 okumada `revive_dialog` okunursa pencere kapanmış sayılır ve durum Ölü olur (bildirim gider); tek bir hatalı diriltme okuması Disconnect'i bırakmaz. Belirsiz okuma (`None`) durumu değiştirmez; böylece tek bir hatalı okuma tekrar bildirime yol açmaz.
- Karakter ölüyken (`hp == 0`) açık olan tanınmayan pencere ayrıca bildirilmez (Ölü bildirimi zaten gitti); ölüyken okunan `disconnect_dialog` da disconnect okuması sayılmaz. Pencere yazısındaki disconnect ifadeleri yalnızca ilk yazı satırında (alt satırlara çoğunlukla arkadaki isim yazıları karışır) tam kelime/ifade olarak, harfler küçültülüp Türkçe karakterler sadeleştirilerek (ı→i, ğ→g, ş→s, ç→c, ö→o, ü→u) aranır; böylece pencerenin arkasındaki isim yazıları kelime içi eşleşmeyle yanlış disconnect sayılmaz.
- Oyun izlenirken kapanırsa heartbeat kontrolü duraklatılır (bilerek kapatmada dış alarm gelmez; çökme durumunda "Oyun kapandı" push'u zaten gider). Oyun tekrar açılınca ilk ping kontrolü otomatik olarak yeniden etkinleştirir.

### Bildirim içeriği

Başlık + kısa gövde, örn. **"💀 Karakter öldü"** / "Ronark Land · 11:42". Dokununca PWA "Olaylar" ekranında açılır.

### Web Push

İlk çalıştırmada VAPID anahtarları üretilir ve saklanır. PWA'dan izin verilince abonelik `push_subscriptions` tablosuna yazılır. Gönderim Apple push servisi üzerinden olur; telefonun Tailscale'e bağlı olması gerekmez.

## 6. Kayıt (SQLite)

- `snapshots(ts, state, hp, hp_max, zone, money_last, slots_used_last, slots_total_last, inventory_seen_at)` — 30 gün saklanır.
- `events(id, ts, kind, detail, notified, notified_at)`
- `push_subscriptions(id, endpoint, keys_json, created_at)`

## 7. Telefon uygulaması (PWA)

| Ekran | İçerik |
|---|---|
| **Durum** | Durum rozeti, HP barı, "son güncelleme X sn önce", son görülen para ve slotlar (+ ne zaman görüldüğü), son 5 olay. Açıkken 5 sn'de bir `/api/status` sorgular. |
| **Canlı** | Tek dokunuşla canlı görüntü; yatayda tam ekran; kalite: Düşük / Orta / Yüksek. |
| **Olaylar** | Olay listesi + son 24 saat durum zaman çizelgesi. |
| **Ayarlar** | Bildirim izni, test bildirimi. |

### Canlı yayın

- WebSocket üzerinden JPEG kareler, yalnızca Canlı ekranı açıkken; bağlantı kapanınca veya sayfa arka plana geçince yayın durur.
- Kalite ön ayarları: Düşük 960x540 ~5 fps · **Orta (varsayılan) 1280x720 ~10 fps** · Yüksek 1920x1080 ~20 fps.
- Bağlantı koparsa istemci otomatik yeniden bağlanır.

### API

| Uç | Açıklama |
|---|---|
| `GET /api/status` | anlık durum + son okumalar |
| `GET /api/snapshots?since=` | health check geçmişi |
| `GET /api/events?limit=` | olaylar |
| `WS /api/stream?quality=` | canlı JPEG kareler |
| `GET /api/push/vapid-key` | VAPID public key |
| `POST /api/push/subscribe` | abonelik kaydı |
| `POST /api/push/test` | test bildirimi |

### Erişim ve güvenlik

- Sunucu yalnızca `127.0.0.1`'de dinler; LAN'a açık değildir.
- `tailscale serve` ile `https://<pc>.<tailnet>.ts.net` üzerinden sadece kullanıcının Tailscale cihazlarına açılır; ek şifre yok.
- Kurulum: iPhone Safari → adres → Paylaş → Ana Ekrana Ekle → uygulamadan bildirim izni.

## 8. Hata yönetimi

- **Belirsiz okuma** → `None`, alarm yok; 60 sn boyunca hiçbir şey okunamazsa "Kör".
- **Capture kopması** → artan beklemeyle yeniden bağlanma (1, 2, 4 … en fazla 30 sn).
- **Push hatası** → 3 deneme (artan bekleme); 404/410 yanıtında abonelik silinir; 5 dk'dan eski bildirim gönderilmez; olay her durumda `events`'e yazılır.
- **Ajan çökmesi** → Windows Görev Zamanlayıcı yeniden başlatır; PC/internet kesintisi → healthchecks.io → ntfy.
- **Günlük** → dönen log dosyası (`logs/agent.log`, 5 MB × 5).

## 9. Test

- **detectors:** pytest, `samples/` altındaki etiketli görüntülerle beklenen `Readings`.
- **monitor:** sahte okuma dizileri + sahte saat; onay süreleri, tekrar engelleme, durum geçişleri.
- **Tekrar oynatma modu:** `--replay <klasör>` ile canlı capture yerine kayıtlı kareler; oyun kapalıyken uçtan uca deneme.
- **api:** FastAPI TestClient.
- **notifier:** sahte notifier ile unit test; gerçek iPhone'da bir kez elle push testi.
- **PWA:** iPhone'da elle kurulum, bildirim ve canlı ekran kontrolü.

## 10. Kurulum ve ayarlar

- Proje: `C:\Users\Serdar\Desktop\ko-monitor`; Python 3.12 sanal ortamı; bağımlılıklar `pyproject.toml`'da.
- Otomatik başlatma: Görev Zamanlayıcı, oturum açılışında, hata olursa yeniden başlat.
- `config.toml`: süreler/eşikler, healthchecks.io ping URL'i, yayın kalitesi, port.
- `calibration.json`: ROI'ler, şablon yolları, eşikler, chat anahtar ifadeleri.
- Gizli bilgiler (VAPID private key, healthchecks URL) git'e girmez (`.gitignore`).

## 11. Kapsam dışı (v1)

- Birden fazla client/karakter (tasarım buna engel değil).
- Oyuna girdi göndermek, telefondan kontrol.
- Chat'ten para sayımı, Genie açık/kapalı tespiti.
- Küçültülmüş pencereyi okumak (teknik olarak mümkün değil; "Kör" bildirimi verilir).
- WebRTC yayını, native uygulama, Pushover (sonradan eklenebilir).

## 12. Uygulama sırası

Uygulama iki plana bölünür: **Plan 1 – Ajan** (adım 1-3; `docs/superpowers/plans/2026-09-15-ko-monitor-agent.md`) ve **Plan 2 – API, PWA ve kurulum** (adım 4-6; Plan 1 bittikten sonra gerçek koda dayanarak yazılır).

1. **Ajan çekirdeği:** capture, process_watch, `snap` komutu, storage.
2. **Kalibrasyon + detectors** (kullanıcıdan örnek ekranlar) ve testleri.
3. **monitor + notifier (Web Push) + heartbeat.**
4. **api + PWA:** Durum, Olaylar, Ayarlar.
5. **Canlı yayın.**
6. **Kurulum:** Tailscale, Görev Zamanlayıcı, iPhone kurulumu.
