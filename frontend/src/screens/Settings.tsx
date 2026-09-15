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
