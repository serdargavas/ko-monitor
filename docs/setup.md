# KO Monitor — Kurulum

Bu belge bilgisayarda ajanın kurulmasını, dışarıdan canlılık kontrolünü, telefondan erişimi ve iPhone uygulamasının kurulmasını anlatır. Hesap açma, oturum açma ve sistem ayarı değiştiren adımları **sen** yaparsın; hiçbir şifre bu projeye yazılmaz.

## 1. Python ortamı

PowerShell'de proje klasöründe (`C:\Users\Serdar\Desktop\ko-monitor`):

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv   # yalnızca .venv yoksa
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m pytest -q
```

Testler geçmeli.

## 2. `config.toml`

```powershell
Copy-Item config.example.toml config.toml
notepad config.toml
```

- `[push] contact`: `mailto:` ile kendi e-posta adresin (Web Push servisleri iletişim için ister).
- `[api] port`: varsayılan `8765`. Değiştirirsen aşağıdaki `tailscale serve` komutunda da aynı portu kullan.
- `[api] stream_quality`: telefonda kalite seçilmediğinde canlı yayın kalitesi (`low` / `medium` / `high`).
- `[heartbeat]`: 3. adımda doldurulur.

`config.toml` ve `data\` git'e girmez. `data\vapid_private.pem` ilk çalıştırmada oluşur; silersen telefonda Ayarlar → **Bildirimleri aç**'a yeniden dokunman gerekir.

## 3. Dış canlılık kontrolü: healthchecks.io + ntfy

Bilgisayar, internet ya da ajan çökerse ajan kendi bildirimini atamaz; bu durumda healthchecks.io haber verir.

1. iPhone'a App Store'dan **ntfy** uygulamasını kur. Uygulamada tahmin edilmesi zor bir konu (topic) adına abone ol, ör. `ko-monitor-<rastgele harfler>`.
2. https://healthchecks.io adresinde hesap aç (ücretsiz plan yeterli).
3. **Add Check**: Period **1 minute**, Grace **3 minutes**. Oluşan **ping URL**'ini (`https://hc-ping.com/<uuid>`) `config.toml` → `[heartbeat] ping_url` alanına yaz.
4. Project → **Settings** → **API Keys** → okuma-yazma (read-write) anahtar oluştur → `[heartbeat] api_key`. (Oyunu kapattığında ajan kontrolü bu anahtarla duraklatır; oyun yeniden açılınca ilk ping kontrolü kendiliğinden etkinleştirir.)
5. **Integrations** → **ntfy** → sunucu `https://ntfy.sh`, konu: 1. adımdaki konu adı → kaydet → **Test** ile iPhone'da ntfy bildirimi geldiğini gör.

## 4. İlk çalıştırma (elle)

```powershell
.venv\Scripts\python.exe -m ko_monitor run
```

Bilgisayarın tarayıcısında `http://127.0.0.1:8765` açılır: Durum ekranı görünmeli. Sunucu yalnızca `127.0.0.1`'de dinler; ev ağından (LAN) erişilemez. Durdurmak için Ctrl+C.

## 5. Telefondan erişim: Tailscale

1. Bilgisayara https://tailscale.com/download adresinden Tailscale'i kur ve oturum aç.
2. iPhone'a App Store'dan **Tailscale**'i kur, **aynı hesapla** oturum aç, VPN'i aç.
3. Tailscale yönetim panelinde (https://login.tailscale.com/admin/dns) **MagicDNS** ve **HTTPS Certificates** açık olmalı (Web Push ve PWA geçerli HTTPS ister).
4. Ajan çalışırken bilgisayarda:
   ```powershell
   tailscale serve --bg 8765
   tailscale serve status
   ```
   `status` çıktısındaki adresi not al: `https://<bilgisayar-adı>.<tailnet>.ts.net`. Bu adres yalnızca senin Tailscale cihazlarından açılır; ek şifre yoktur.
   Yayını kaldırmak için: `tailscale serve reset`.

   `tailscale serve` ile yayınlanan her şey (canlı görüntü dahil) tailnet'inin izin verdiği her cihazdan açılabilir; bu bilgisayarı (node) başkalarıyla paylaşma. Telefonda sayfa yerine HTTP 400 "Invalid host header" görürsen `logs\agent.log` dosyasıyla birlikte bunu bildir (sunucu yalnızca `127.0.0.1`, `localhost` ve `*.ts.net` adreslerine yanıt verir; `tailscale serve`'ün `.ts.net` adresini ilettiği varsayılıyor).

## 6. iPhone uygulaması (PWA) ve bildirimler

Gereken: **iOS 16.4** veya üstü. Web Push iPhone'da yalnızca ana ekrana eklenmiş uygulamada çalışır.

1. iPhone'da Tailscale VPN açıkken **Safari** ile 5. adımdaki `https://...ts.net` adresini aç.
2. **Paylaş** düğmesi → **Ana Ekrana Ekle** → **Ekle**.
3. Ana ekrandaki **KO Monitor** simgesiyle uygulamayı aç (Safari sekmesinden değil).
4. **Ayarlar** → **Bildirimleri aç** → çıkan izin isteğinde **İzin Ver**.
5. **Test bildirimi gönder** → birkaç saniye içinde "🔔 Test bildirimi" gelmeli; dokununca uygulama Olaylar ekranında açılır.
6. **Canlı** sekmesi: görüntü kendiliğinden başlar; Düşük / Orta / Yüksek ile kalite seçilir; telefonu yan çevirince tam ekran olur. Uygulamadan çıkınca yayın durur.

Bildirimler Apple push servisi üzerinden gelir: telefonun o anda Tailscale'e bağlı olması gerekmez. Uygulamayı açıp durum/canlı görüntü görmek için Tailscale VPN açık olmalı (Tailscale uygulamasında "VPN On Demand" ile hep açık tutulabilir).

## 7. Otomatik başlatma (Görev Zamanlayıcı)

Elle çalışan ajanı (4. adım) Ctrl+C ile kapat; aynı anda iki kopya çalışırsa ikincisi izlemeye başlamadan "port 8765 kullanımda" hatasıyla kapanır.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1
Start-ScheduledTask -TaskName "KO Monitor"
Get-ScheduledTask -TaskName "KO Monitor" | Get-ScheduledTaskInfo
Get-Content logs\agent.log -Tail 20
```

Görev oturum açılışında başlar ve konsol penceresi açmaz (`pythonw.exe`). Ayrıca her dakika tetiklenen bir bekçi (watchdog) tetikleyicisi vardır: ajan çalışıyorsa bu tetikleme yok sayılır (aynı anda tek kopya çalışır); çalışmıyorsa (çöktüyse ya da hata ile kapandıysa) Görev Zamanlayıcı onu en geç 1 dakika içinde yeniden başlatır. Günlük: `logs\agent.log`.

**Doğrulama (kayıttan sonra bir kez yap):**

1. `Start-ScheduledTask -TaskName "KO Monitor"` → `logs\agent.log` içinde `API on http://127.0.0.1:8765` satırı görünmeli.
2. Ajanı kapat: Görev Yöneticisi → **Ayrıntılar** → `pythonw.exe` → **Görevi sonlandır**. (Ya da portu kısa süre meşgul et: `Stop-ScheduledTask -TaskName "KO Monitor"` ile durdur, 4. adımdaki gibi elle başlat; bu sırada günlükte her dakika "port 8765 kullanımda" satırı çıkar. Sonra elle çalışanı Ctrl+C ile kapat.)
3. Yaklaşık 1 dakika bekle: `Get-ScheduledTask -TaskName "KO Monitor" | Get-ScheduledTaskInfo` çıktısında **LastRunTime** yenilenmeli, **Görev Zamanlayıcı** → **Görev Zamanlayıcı Kitaplığı** → **KO Monitor** → **Geçmiş** sekmesinde yeni bir "Görev başlatıldı" kaydı ve `logs\agent.log`'da yeni bir `API on` satırı görünmeli. (Geçmiş sekmesi kapalıysa sağdaki **Tüm Görevlerin Geçmişini Etkinleştir** yönetici izni ister; LastRunTime ve günlük yeterlidir.)

- Durdurmak: bekçi tetikleyicisi görevi 1 dakika içinde yeniden başlatır; kalıcı durdurmak için önce `Disable-ScheduledTask -TaskName "KO Monitor"`, sonra `Stop-ScheduledTask -TaskName "KO Monitor"`. Yeniden açmak: `Enable-ScheduledTask -TaskName "KO Monitor"`.
- Görev kayıtlıyken elle çalıştırmak (4. adım) istersen önce görevi aynı şekilde devre dışı bırak.
- Kaldırmak: `Unregister-ScheduledTask -TaskName "KO Monitor" -Confirm:$false`

`tailscale serve --bg` ayarı Tailscale tarafından saklanır; bilgisayar yeniden başlayınca tekrar çalıştırman gerekmez.

## 8. Sorun giderme

| Belirti | Kontrol |
|---|---|
| Telefonda sayfa açılmıyor | iPhone'da Tailscale VPN açık mı? Bilgisayarda `tailscale serve status` adresi gösteriyor mu? Ajan çalışıyor mu (`logs\agent.log`)? |
| "Bildirimleri aç" izin sormuyor | Uygulama ana ekran simgesinden mi açıldı? iOS 16.4+ mı? iPhone Ayarlar → Bildirimler → KO Monitor. |
| Test bildirimi "Gönderilemedi" | `logs\agent.log` içindeki `push failed` satırları; bilgisayarın internet bağlantısı. |
| Canlı ekranda "Oyun penceresi küçültülmüş" | Oyun penceresi simge durumunda; Windows küçültülmüş pencereden görüntü vermez. |
| Durum "Son güncelleme" sürekli eskiyor | Ajan döngüsü durmuş olabilir; görev yeniden başlatılır, `logs\agent.log`'a bak. |
| `logs\agent.log`'da her dakika "port 8765 kullanımda" | Başka bir KO Monitor (ör. elle başlatılmış) çalışıyor; onu kapat ya da görevi devre dışı bırak. |
| healthchecks.io'dan yanlış alarm | Oyun kapatılınca kontrol duraklatılır; `[heartbeat] api_key` doğru mu? |

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
