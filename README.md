# NumberPainting · Piksel Stüdyo

**Piksel sanatı "sayı ile boyama" kitapları üreten masaüstü uygulaması.** Görselleri Gemini ile alırsın, uygulama onları siyah sayfalı, kodlu boyama sayfalarına çevirir ve Amazon KDP'ye hazır bir kitap PDF'i oluşturur.

> **English:** A Windows desktop app that turns images (made with Google Gemini or your own photos) into pixel-art colour-by-number pages and builds a print-ready (Amazon KDP, 8.5×11 in, full bleed) book PDF. A clipboard "autopilot" saves images you copy in Gemini and puts the next prompt on the clipboard, so a whole book takes about 25 rounds of *paste → enter → copy image*.

---

## Özellikler

- **Pano otopilotu:** Gemini'de görsele sağ tık → *Görseli kopyala* dediğin an görsel kaydedilir, sıradaki prompt panoya gelir. Pencere değiştirmen gerekmez.
- **Bir promptta 4 resim:** Gemini 2×2 düzende 4 resim çizer, uygulama bunları 4 ayrı sayfaya böler. 100 sayfalık bir kitap yaklaşık 25 tur sürer.
- **Bitmeyen, tekrar etmeyen konular:** 17 kategoride 200'den fazla konu var: çiçekler, kuşlar, deniz canlıları, yiyecekler, müzik aletleri, uzay, Türk kültürü ve daha fazlası. Her tür ve obje bir kez gelir, her 4'lü sayfa 4 farklı kategoriden oluşur, liste azalınca kendini doldurur.
- **Özel konu:** "gözlüklü kapibara" yaz, sıranın başına geçer. İstersen "çocuk için" sevimli stilde çizilir.
- **Kendi fotoğrafların:** sürükle bırak. Fotoğraflar otomatik temizlenip boyama sayfasına uygun hâle getirilir.
- **Boyama önizleme:** her görselin kitapta nasıl duracağını galeride görürsün.
- **KDP'ye hazır kitap:** başlık sayfası, nasıl boyanır sayfası, renk deneme paleti, içindekiler (işaretleme kutulu), her resim için lejant ve boyama sayfası, cevap anahtarları.
- **Kalite raporu:** renk sayısı, zorluk (Kolay/Orta/Zor) ve sorunlu görseller için uyarılar.

## Gereksinimler

| | |
|---|---|
| İşletim sistemi | **Windows 10 veya 11** (pano otopilotu Windows'a özel) |
| Python | **3.10 veya üstü**: [python.org/downloads](https://www.python.org/downloads/) |
| Tarayıcı | Microsoft Edge (Windows'ta hazır gelir; yoksa varsayılan tarayıcı açılır) |
| Görsel üretimi | Bir Google hesabı ve [gemini.google.com](https://gemini.google.com). Görsel üretme limitleri hesap türüne göre değişir |
| Kütüphaneler | `pillow`, `reportlab` (ilk açılışta otomatik kurulur) |

## Kurulum

1. **Python'u kur.** Kurulumun ilk ekranında **"Add python.exe to PATH"** kutusunu mutlaka işaretle.
2. **Bu repoyu indir:**
   - Kolay yol: sayfanın üstündeki yeşil **Code → Download ZIP**, sonra ZIP'i bir klasöre çıkar.
   - Ya da git ile:
     ```bash
     git clone https://github.com/weberkanedu/NumberPainting.git
     ```
3. Klasördeki **`Uygulamayi_Ac.bat`** dosyasına çift tıkla.
   - İlk açılışta gerekli kütüphaneler kurulur (bir kerelik, birkaç saniye).
   - Uygulama kendi penceresinde açılır.

> Kütüphaneleri elle kurmak istersen: `python -m pip install -r requirements.txt`

## Kullanım

### 1 · Gemini ile görsel al

1. **▶ Otopilotu başlat**'a bas. İlk prompt panoya kopyalanır.
2. **Gemini'yi aç ↗** ile gemini.google.com'u aç, sonra şunu tekrarla:
   - Gemini'de **Ctrl+V** ve **Enter**
   - Görsel gelince üzerine **sağ tık → Görseli kopyala**
   - Bu kadar: görsel kaydedilir, sıradaki prompt panoya gelir.

Diğer düğmeler:

| Düğme | Ne yapar |
|---|---|
| **4 resim (2×2) / 1 resim** | Bir promptta kaç resim isteneceği |
| **Özel konu ekle** | Yazdığın konu sıranın başına geçer, tek resim olarak istenir. "Çocuk için" seçiliyse sevimli stilde |
| **✕ kaldır** | Sıradaki özel konuyu sıradan çıkarır |
| **Atla / Önceki** | Konular arasında gezinir |
| **Son kaydı geri al** | Kötü çıkan görseli geri alır, aynı konu tekrar istenir |
| **Konuları yenile** | Bekleyen konuların yerine yepyeni konular getirir |
| Galeride **Sil** | Görseli `silinenler/` klasörüne taşır, o konu bir daha istenmez |

> **İpucu:** Gemini aynı sohbette önceki görsellerin stilini taklit edebilir. Stil kayarsa Gemini'de yeni bir sohbet başlat.
> Otopilot açıkken alınan **ekran görüntüleri** (Win+Shift+S) kaydedilmez, sadece Gemini görseline benzeyen görseller alınır.

### 2 · Kendi görselin

Fotoğraf veya çizimleri pencereye **sürükle bırak**. Bunlar "kendi" olarak işaretlenir (`k001_…`) ve kitaba eklenir.

### 3 · Kitabı oluştur

Kitap adını yaz, hücre şeklini seç (**Kare** veya **Nokta (petek)**) ve **Kitabı oluştur**'a bas. Sonuç `cikti/` klasörüne yazılır:

- `kitap_ic_sayfalar.pdf`: KDP'ye yüklenecek iç sayfalar
- `rapor.html`: her resim için renk sayısı, zorluk ve uyarılar

## Kitap formatı

- **Sayfa:** 8.5 × 11 inç, taşmalı (bleed) PDF boyutu 8.625 × 11.25 inç. Sayfalar siyah zeminli.
- **Kenar boşluğu:** 300 sayfaya kadar KDP'nin iç kenar (gutter) kuralına uyar.
- **Izgara:** 40 × 54 hücre (yaklaşık 4.6 mm), resim başına en fazla 15 renk.
- **Sayfa düzeni:** her resim için solda lejant (kodlar, renk adları, hücre sayıları), sağda boyama sayfası. Alkol markerlar arkaya geçtiği için boyama sayfasının arkası boş kalır.

### Renk kodları

Tek karakterli kodlar kullanılır. **I** ve **O** harfleri, 1 ve 0 ile karışmasın diye kullanılmaz.

| Kod | Renk | Kod | Renk | Kod | Renk |
|---|---|---|---|---|---|
| 0 | Black | 8 | Red Orange | G | Light Blue |
| 1 | Gray | 9 | Orange | H | Blue |
| 2 | Dark Gray | A | Yellow Orange | J | Dark Blue |
| 3 | Dark Brown | B | Yellow | K | Pink |
| 4 | Brown | C | Yellow Green | L | Violet |
| 5 | Tan | D | Green | M | Dark Violet |
| 6 | Peach | E | Dark Green | N | Magenta |
| 7 | Red | F | Aqua Green | **W** | **Beyaz: boyanmaz** |

> Renklerin RGB değerleri yaklaşıktır. Kendi marker setine göre `pixelbook.py` içindeki `PALETTE` listesinden ayarlayabilirsin.

## Klasör yapısı

```
Uygulamayi_Ac.bat   uygulamayı açar
sunucu.py           uygulamanın kendisi (yerel sunucu + otopilot)
arayuz.html         arayüz
pixelbook.py        görsel → kodlu ızgara, sayfa çizimi, renk paleti
kitap_yap.py        kitap PDF'i ve kalite raporu
konu_uret.py        konu üretici (kategoriler ve konu listeleri)
promptlar.py        Gemini promptları
pano.py             Windows pano erişimi

girdi/              görsellerin (otomatik oluşur)
cikti/              kitap PDF'i ve rapor
silinenler/         sildiğin görseller (geri almak için buradan taşı)
konular.csv         konu listen (otomatik oluşur, elle de düzenlenebilir)
```

## Komut satırı (isteğe bağlı)

```bash
python pixelbook.py resim.png -o sayfa.pdf --title "Kedi" --shape circle --hex
```

```bash
python kitap_yap.py girdi -o cikti --book-title "Pixel Color by Number" --sort
```

## Gizlilik

- Uygulama sadece bu bilgisayarda (`127.0.0.1`) çalışır, internete hiçbir şey göndermez.
- Promptları Gemini'ye sen yapıştırırsın.
- Pano sadece otopilot açıkken izlenir.

## Sorun giderme

| Sorun | Çözüm |
|---|---|
| "Python bulunamadı" | Python'u kur, kurulumda "Add python.exe to PATH" kutusunu işaretle |
| Pencere açılmıyor | Klasördeki `hata.log` dosyasına bak |
| "PDF açık olduğu için yazılamadı" | Açık olan PDF'i kapatıp tekrar dene |
| 4'lü görsel kayık bölünüyor | "1 resim" moduna geç |

## Notlar

- Gemini ile üretilen görsellerin ticari kullanımı Google'ın kullanım şartlarına tabidir.
- Amazon KDP, yapay zekâ ile üretilmiş içeriğin yayınlarken **beyan edilmesini** ister.

## Lisans

[MIT](LICENSE): kodu serbestçe kullanabilir, değiştirebilir ve dağıtabilirsin. Lisans metni kopyalarda korunmalıdır.
