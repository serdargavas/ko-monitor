# KO Monitor — Genie durumu, ok/pot takibi ve kazanç grafiği (Tasarım)

**Tarih:** 2026-09-16
**Durum:** Kullanıcı sohbette onayladı
**Üst spec:** `docs/superpowers/specs/2026-09-15-ko-monitor-design.md`

## 1. Amaç

Üç eksiği kapatmak:

1. **Ok ve mana potu tükenirse haber vermek.** Ok biterse karakter vurmayı
   bırakır, pot biterse büyü kullanamaz; ikisinde de farm sessizce durur ve
   mevcut sistem bunu fark etmez (HP dolu, oyun açık, ekran değişiyor).
2. **Sadece Genie çalışırken rahatsız etmek.** Kullanıcı kendi oynarken
   ölümü zaten görüyor; telefonunun ötmesi gereksiz.
3. **Kazancı ölçmek.** Saat başına ne kazanıldığını ve saatlik değişimi
   görebilmek.

**Kapsam dışı:** yeni yakalama yöntemi, oyuna müdahale, Genie'yi programla
başlatma/durdurma, kazanç tahmini/projeksiyon.

## 2. Kararlar

| Karar | Gerekçe |
|---|---|
| Genie durumu **stop düğmesinin rengiyle** okunur | Ölçüldü: açıkken doygunluk 194-234, kapalıyken 66. 12x13 piksellik kontrol, OCR maliyeti yok. |
| Sınıflandırma **stop ile play'in karşılaştırmasıyla** yapılır | Play düğmesi tam tersi davranıyor (açık 76, kapalı 171). Göreli karşılaştırma, ekran parlaklığı/gama değişse de ayakta kalır. |
| Panel bulunamazsa durum **"bilinmiyor"** ve bildirimler **susturulmaz** | Yanlış sessizlik, fazladan bildirimden kötüdür: susturulan tek şey ölüm uyarısı ve kullanıcı onu kaçırmamalı. |
| Karakterin üstündeki dönen "GENIE" yazısı **kullanılmaz** | Sağlam bir iz ama 3B döndüğü için tek karede görünmeyebiliyor; OCR ve zaman penceresi gerektirir. Düğme yeterli. Panel kapatma sorun olursa sonra eklenir. |
| Ok ve pot **ikonlarıyla** bulunur, slot konumuyla değil | Kullanıcı eşyayı taşıyabilir; ikon şablonu taşımaya dayanıklı. |
| Sayılar slotun **sol alt köşesinden OCR** ile okunur | Test edildi: 6380 ve 4150 değerleri %99,9 güvenle, iki farklı kırpımda aynı okundu. |
| Eşya hiçbir slotta bulunamazsa sayı **0** kabul edilir | Ok tükenince slot tamamen kaybolur; "bulunamadı" ile "bitti" aynı şeydir. |
| Eşikler: **ok < 1000**, **pot < 200** (config) | Ölçülen harcama hızı ok ~1790/saat, pot ~311/saat → ikisi de ~30-35 dakika önceden uyarır. |
| Kazanç verisi **mevcut snapshot'lardan** hesaplanır | Ajan zaten dakikada bir `money_last` kaydediyor ve 30 gün saklıyor; yeni toplama mekanizması gereksiz. |
| Grafik **Olaylar ekranının üstüne** gelir | Kullanıcı tercihi; yeni sekme açmaya gerek yok. |

## 3. Genie detektörü (`detectors/genie.py`)

**Panel konumu.** Önce `templates/genie_header.png` şablonu kare içinde
aranır (envanter penceresiyle aynı yöntem: `template_present`/eşleşme
konumu, eşik 0.8). Bulunursa düğme kutuları eşleşme konumuna **göreli**
hesaplanır, böylece panel sürüklenirse koordinatlar kaymaz.

**Sınıflandırma.** Eşleşme noktasına göre iki kutu okunur (kalibrasyonda
saklanan göreli kutular):

- `stop_box` — durdur düğmesinin iç karesi (ölçülen mutlak konum: 2511, 9, 12, 13)
- `play_box` — başlat düğmesinin iç karesi (ölçülen mutlak konum: 2482, 9, 14, 14)

Her kutunun HSV doygunluk ortalaması alınır:

```
aktif  = stop_doygunluk - play_doygunluk >= genie_margin   (varsayılan 60)
kapali = play_doygunluk - stop_doygunluk >= genie_margin
```

İkisi de sağlanmazsa durum **bilinmiyor**. Ölçülen gerçek değerler:
açıkken fark +132 (208 - 76), kapalıyken -105 (66 - 171). Yani 60'lık pay
iki yönde de geniş marjla ayırıyor.

**Okuma:** `Readings.genie_active: bool | None` (None = bilinmiyor).

**Kararlılık:** Durum değişimi, mevcut ölüm/disconnect mantığındaki gibi
**2 ardışık okuma** ile onaylanır; tek karelik bir yanılma bildirimleri
susturmaz veya açmaz.

## 4. Ok ve pot detektörü (`detectors/items.py`)

Envanter penceresi açıkken (`inventory_open`) çalışır; kapalıyken her iki
sayı da `None` döner ve son bilinen değer korunur.

**Bulma.** `templates/item_arrow.png` ve `templates/item_mana.png`
şablonları 28 slotun her birine karşı denenir (`cv2.matchTemplate`,
`TM_CCOEFF_NORMED`, eşik kalibrasyonda `item_match_threshold`, varsayılan
0.85). En yüksek skorlu slot seçilir.

Şablonlar slotun **üst 27 pikselinden** kesilir (45x27). Alt şerit
kasıtlı olarak dışarıda bırakılır: adet sayısı orada yazıyor ve sürekli
değişiyor, şablona girerse eşleşme sayı değiştikçe bozulur. Eşleşme de
her slotun aynı üst 45x27 bölgesinde aranır.

**Sayma.** Bulunan slotun sol alt köşesi (slot içinde göreli kutu, ölçülen:
x+1, y+28, 30x16) 4 kat büyütülüp `ocr.read_line` ile okunur, rakam dışı
karakterler atılır (mevcut `parse_money` ile aynı yaklaşım).

**Okumalar:** `Readings.arrow_count: int | None`, `Readings.mana_count: int | None`.

**Hiç bulunamazsa** 0 döner (slot kaybolmuş = eşya bitmiş).

## 5. Uyarılar ve susturma

**Yeni olay türleri:** `EventKind.ARROW_LOW`, `EventKind.MANA_LOW`.

Tetikleme: sayı eşiğin altına **düştüğü anda** bir kez. Aynı uyarı
`item_low_repeat_s` (varsayılan 600 sn) dolmadan tekrarlanmaz — envanter
dolu uyarısıyla aynı kural. Sayı eşiğin üstüne çıkarsa (kullanıcı ok
satın aldı) tekrar tetiklenebilir hale gelir.

**Bildirim metinleri** (`messages.py`):

- `ARROW_LOW` → "🏹 Ok azaldı" / gövde: kalan sayı + bölge
- `MANA_LOW` → "🧪 Mana potu azaldı" / gövde: kalan sayı + bölge

**Susturma kuralı.** `genie_active is False` iken şu olaylar veritabanına
yazılır ama telefona **gönderilmez**: `DEAD`, `INVENTORY_FULL`,
`ARROW_LOW`, `MANA_LOW` (ve bunların `RECOVERED` eşleri).

Her zaman gönderilenler: `DISCONNECTED`, `GAME_CLOSED`, `FROZEN`, `BLIND`,
`GAME_STARTED`, `TEST`.

`genie_active is None` (bilinmiyor) susturma **yapmaz** — her şey gönderilir.

Susturma noktası `Agent._handle` içindedir: olay kaydedilir, `event.notify`
değeri susturma kuralıyla birlikte değerlendirilir. Böylece geçmiş
eksiksiz kalır ve "ben oynarken ne oldu" sorusu sonradan cevaplanabilir.

## 6. Kazanç hesabı ve grafik

**Sunucu.** Yeni uç: `GET /api/income?hours=24` (1-720 arası, varsayılan 24).
`snapshots` tablosundan `money_last` okunur ve saatlik kovalara bölünür:

```json
{"hours": [{"start": 1789540000, "delta": 11840000, "samples": 60}, ...],
 "avg_1h": 11840000, "avg_6h": 11200000, "avg_24h": 10950000}
```

- Bir saatin farkı = o saatteki **son** ölçüm − **ilk** ölçüm.
- Saatte hiç ölçüm yoksa (oyun kapalı, envanter kapalı) `delta: null`,
  `samples: 0` döner ve **ortalamaya katılmaz**.
- **Aykırı değer eleme:** iki ardışık ölçüm arasındaki fark
  `income_max_jump` (varsayılan 50.000.000) sınırını aşarsa o adım atlanır.
  Tek bir OCR hatasının grafiği bozmasını engeller. Gerçek büyük harcamalar
  (ekipman alımı) da elenir; amaç farm hızını ölçmek, muhasebe tutmak değil.

**Arayüz.** `Olaylar` ekranının en üstünde saatlik çubuk grafik:

- Son 24 saat, saat başına bir çubuk.
- Pozitif kazanç yeşil, negatif (harcama) kırmızı, veri yok gri.
- Grafiğin altında özet: "Son 1 saat / 6 saat / 24 saat ortalaması".
- Dokunma/tıklama gerektirmez; salt okunur.

Yeni bileşen `frontend/src/components/IncomeChart.tsx`, saf SVG (harici
grafik kütüphanesi yok — mevcut `Timeline` bileşeni de böyle çalışıyor).

## 7. Kalibrasyon ve yapılandırma

`calibration.json` içine yeni bloklar:

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
  "count_box": [1, 28, 30, 16]
}
```

`stop_box` ve `play_box` kalibrasyonda **mutlak** tutulur; çalışma anında
şablon eşleşme konumuyla arasındaki fark uygulanarak göreli hale getirilir.

`config.toml` `[thresholds]` içine:

```toml
arrow_low = 1000
mana_low = 200
item_low_repeat_s = 600.0
income_max_jump = 50000000
```

## 8. Test

| Birim | Test |
|---|---|
| `genie.py` | açık/kapalı/bilinmiyor sınıflandırması (gerçek karelerden kesilmiş üç örnek), panel bulunamayınca None, panel kaydırılınca göreli konumun doğru hesaplanması |
| `items.py` | ok ve pot bulma, sayı okuma (gerçek kareler: 6380 ve 4150), eşya yokken 0, envanter kapalıyken None, eşleşme eşiği altında kalınca 0 |
| `monitor.py` | eşik altına düşünce tek uyarı, 600 sn içinde tekrar yok, eşiğin üstüne çıkıp tekrar düşünce yeniden uyarı |
| Susturma | genie kapalıyken DEAD kaydedilir ama gönderilmez; DISCONNECTED gönderilir; genie bilinmiyorken her şey gönderilir |
| `income` | saatlik kovalama, boş saat null, aykırı sıçrama elenmesi, saat sınırı doğrulaması, ortalamalarda null saatlerin dışlanması |
| `IncomeChart` | boş veri, tek saat, negatif değer, null saat, tr-TR biçimi |
| Gerçek kareler | `samples/` altına eklenen Genie açık/kapalı ve envanter kareleriyle uçtan uca `detect` testi |

Mevcut testlerin tamamı (304) geçmeye devam etmeli.

**Test için commit edilecek kareler:** `samples/genie_on/` ve
`samples/genie_off/` altına birer tam kare (2560x1440 PNG, ~6 MB each).
Tam kare gerekiyor çünkü kalibrasyon koordinatları mutlak; kırpılmış
görüntüde ROI'ler tutmaz. Bu iki kare envanteri de açık gösterdiği için
ok/pot testleri de aynı dosyaları kullanır — ayrıca örnek eklenmez.

## 9. Bilinen sınırlar

- Ok/pot takibi **envanter penceresi açıkken** çalışır. Kullanıcı envanteri
  kapatırsa son bilinen değer gösterilir, uyarı tetiklenmez.
- Genie paneli kapatılırsa durum "bilinmiyor" olur ve susturma devre dışı
  kalır (bildirimler gelir).
- Kazanç grafiği farm hızını ölçer; büyük alışverişler aykırı değer
  elemesine takılacağı için muhasebe amaçlı kullanılamaz.
- Eşya şablonları bu sunucunun ikon setine bağlıdır; sunucu ikon
  değiştirirse şablonların yeniden kesilmesi gerekir.
