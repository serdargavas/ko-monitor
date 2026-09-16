# Telefon bağlantısı — kalan adımlar

Bu dosya, oyun PC'sindeki kurulum bittikten sonra kalan işleri anlatır.
Diğer bilgisayardan okunmak için yazıldı.

## Bu kurulumun gerçek adresi

**Telefon ve diğer bilgisayar için:** <https://ko-monitor-pc.tail5a4474.ts.net>

Tailscale kurulumu (bölüm 1) ve port yayını (bölüm 2) oyun PC'sinde
tamamlandı ve HTTPS üzerinden doğrulandı. Aşağıdaki 1. ve 2. bölümler
referans olarak duruyor; yeniden kurulum gerekirse işe yararlar.
Kalan iş: telefona Tailscale kurup aynı hesapla (serdargavas@) girmek
ve adresi Safari'den ana ekrana eklemek (bölüm 3). healthchecks
(bölüm 5) sonraya bırakıldı.

## Şu an hazır olanlar (oyun PC'si)

- `config.toml` oluşturuldu (bildirim iletişim adresi: serdargavas@gmail.com).
- Görev Zamanlayıcı'da **KO Monitor** görevi kayıtlı ve çalışıyor:
  açılışta başlar, süreç ölürse 1 dakika içinde geri gelir.
- Ajan `http://127.0.0.1:8765` üzerinde dinliyor ve oyunu okuyor
  (durum, HP, bölge, envanter, para, canlı görüntü).
- **Eksik olan tek şey:** bu adresin telefona açılması (Tailscale) ve
  isteğe bağlı kalp atışı (healthchecks.io).

Ajan sadece `127.0.0.1` dinler. Yani Tailscale kurulmadan ev ağındaki
başka bir cihaz bile bu adrese erişemez.

## 1. Tailscale — oyun PC'si

Kurulum (oyun PC'sinde, PowerShell):

```powershell
winget install --id tailscale.tailscale --accept-package-agreements --accept-source-agreements
```

Giriş için iki yol var:

**A) Oyun PC'sinin başındaysan:** `tailscale up` komutu tarayıcı açar,
kendi hesabınla onaylarsın.

**B) Uzaktan hazırlamak istersen:** diğer bilgisayardan
<https://login.tailscale.com/admin/settings/keys> adresinde bir **auth key**
üret (reusable olmasına gerek yok), sonra oyun PC'sinde:

```powershell
tailscale up --auth-key=tskey-auth-XXXXXXXX
```

Anahtarı kimseyle paylaşma; ağa cihaz eklemeye yarar.

Giriş bittikten sonra adresi öğren:

```powershell
tailscale status
```

Makine adı `<pc-adi>.<tailnet>.ts.net` şeklinde görünür.

## 2. Portu telefona aç

Oyun PC'sinde bir kez:

```powershell
tailscale serve --bg 8765
```

Bu, HTTPS ile `https://<pc-adi>.<tailnet>.ts.net` adresini ajanın
`127.0.0.1:8765` adresine bağlar. Yeniden başlatmalarda kalıcıdır.

Kontrol:

```powershell
tailscale serve status
```

## 3. Telefon (iPhone)

1. App Store'dan **Tailscale** kur, oyun PC'siyle **aynı hesapla** giriş yap.
   (Telefonun PC'ye fiziksel yakınlığı veya kablo gerekmez; mobil veriyle de çalışır.)
2. Safari'de `https://<pc-adi>.<tailnet>.ts.net` adresini aç.
3. Paylaş → **Ana Ekrana Ekle**.
4. Uygulamayı **ana ekrandan** aç (bildirimler ancak böyle çalışır).
5. Ayarlar sekmesi → **Bildirimleri aç** → **Test bildirimi** gönder.
6. Bildirime dokunduğunda Olaylar ekranının açıldığını gör.

## 4. Diğer bilgisayardan izleme

O bilgisayara da Tailscale kurup aynı hesapla giriş yaptıktan sonra
tarayıcıdan aynı adresi açman yeterli:
`https://<pc-adi>.<tailnet>.ts.net`

Aynı dört ekranı ve canlı görüntüyü görürsün. Ayrı bir kurulum gerekmez.

## 5. healthchecks.io (kalp atışı — PC kapanırsa haber verir)

1. healthchecks.io'da hesap aç.
2. Yeni bir **check** oluştur (Period 5 dakika, Grace 5 dakika yeterli).
3. Ping adresini kopyala: `https://hc-ping.com/<uuid>`
4. Proje ayarlarından **API key** (read-write) al.
5. Telefona düşmesi için check'e bir entegrasyon bağla (en kolayı **ntfy**:
   telefona ntfy uygulamasını kurup bir konu adı belirlersin).
6. Oyun PC'sindeki `config.toml` dosyasında şu iki satırı doldur:

```toml
[heartbeat]
ping_url = "https://hc-ping.com/BURAYA-UUID"
api_key = "BURAYA-API-KEY"
```

7. Ajanı yeniden başlat:

```powershell
Restart-ScheduledTask -TaskName "KO Monitor"
```

Boş bırakılırsa kalp atışı kapalı kalır; ölüm/envanter/disconnect
bildirimleri yine çalışır. Kaybettiğin tek şey, bilgisayar tamamen
kapanırsa gelen "ajan sustu" uyarısıdır.

## 6. Günlük kullanım ve sorun giderme

| Durum | Ne yapmalı |
|---|---|
| Ajanı durdurmak | `Disable-ScheduledTask -TaskName "KO Monitor"` sonra `Stop-ScheduledTask -TaskName "KO Monitor"`. Sadece durdurursan gözcü 1 dakikada geri başlatır. |
| Tekrar açmak | `Enable-ScheduledTask -TaskName "KO Monitor"`; `Start-ScheduledTask -TaskName "KO Monitor"` |
| Durumu görmek | `Get-ScheduledTaskInfo -TaskName "KO Monitor"` |
| Kayıtlar | `logs\` klasöründeki en yeni `.log` dosyası |
| "port 8765 kullanımda" | Zaten bir kopya çalışıyor demektir; beklenen davranış |
| Telefonda "Invalid host header" (400) | `tailscale serve` Host başlığını değiştiriyor demektir; bana bildir, izin listesini ayarlarım |
| Canlı görüntü takılıyorsa | Ayarlar'dan kaliteyi `low` veya `medium` yap |
| Oyun kapalıyken | Durum "Oyun kapalı" görünür; bu normaldir |

## 7. Henüz veri bekleyen iki şey

- **Disconnect penceresi yazısı:** ilk gerçek disconnect olduğunda
  `data\incidents\` altına görüntü kaydedilir; o yazıyı tanıma listesine ekleriz.
  O zamana kadar tanınmayan pencere 30 saniye açık kalırsa "disconnect" sayılır.
- **"Envanter dolu" chat mesajı:** örnek yok. Envanter doluluğu şu an
  envanter penceresi açıkken siyah (boş) kutucuk sayısından anlaşılıyor.
