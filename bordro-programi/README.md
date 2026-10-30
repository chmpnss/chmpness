# Bordro Programı

Sağlık Bakanlığı birimleri için **657 kadrolu memur** ve **4/B sözleşmeli personel** maaşı hesaplayan masaüstü programı.
KBS'deki maaş hesabının yerel bir benzeridir: personeli kaydedersiniz, dönemi seçip **Hesapla** dersiniz, bordroyu kaydedip çıktısını alırsınız.

> **Önemli:** Bu program KBS'nin yerine geçmez; ön hesap, kontrol ve raporlama içindir. Resmî ödemeden önce
> sonuçları KBS ile karşılaştırın. Katsayı ve oranları her dönem genelgeden kontrol edin.

## Kurulum

### Windows (.exe)
1. [Python 3.10+](https://www.python.org/downloads/) kurun (kurulumda *Add Python to PATH* işaretli olsun).
2. Bu klasörde `exe_olustur.bat` dosyasına çift tıklayın.
3. `dist\BordroProgrami.exe` oluşur. Bu dosyayı istediğiniz bilgisayara kopyalayıp çalıştırabilirsiniz, Python gerekmez.

### Python ile doğrudan çalıştırma
```
pip install -r requirements.txt
python bordro_app.py
```

Veriler kullanıcı klasöründeki `BordroProgrami\bordro.db` dosyasında tutulur (örn. `C:\Users\Ad\BordroProgrami\bordro.db`).
Yol programın alt satırında yazar. **Dosya → Yedek Al** ile düzenli yedek alın.

## Kullanım

1. **Parametreler ve Ayarlar**
   - Kurum ve birim/hastane adını girin (bordro başlığında çıkar).
   - Katsayıları kontrol edin. Program Ocak 2026 ve Temmuz 2026 değerleriyle gelir. Yeni dönemde
     **Yeni Dönem Olarak Kopyala** (örn. `2027-01`) deyip yeni katsayıları girin. Hesapta, dönemden önceki en son set kullanılır.
   - Gelir vergisi tarifesini yıl yıl girin (2026 hazır gelir).
   - Gösterge tablosu 657 md. 43'e göre gelir; gerekirse satır ekleyin/düzeltin.
   - Kontrol ettikten sonra *"…karşılaştırdım; doğrudur"* kutusunu işaretleyin (işaretlenene kadar Bordro ekranında uyarı çıkar).
2. **Personel**: Formdan tek tek ya da **Excel Şablonu → Excel'den Aktar** ile toplu girin.
   Aynı T.C. no ile tekrar aktarılan personel güncellenir. **Ek Ödeme ve Kesintiler** ile nöbet, ek ders, icra,
   nafaka, lojman gibi kalemleri tek bir ay için ya da her ay için ekleyin.
3. **Bordro**: Yılı ve ayı seçip **Hesapla** deyin. Satıra çift tıklarsanız kalem kalem ayrıntı açılır.
   **Bordroyu Kaydet** ile kaydedin. Sonraki ayların kümülatif vergi matrahı kayıtlı bordrodan hesaplanır, bu yüzden ayları sırayla kaydedin.
   Ödeme yapıldıktan sonra **Dönemi Kilitle** deyin.
4. **Çıktılar**: kişi bordrosu PDF (seçili kişi ya da herkes), toplu bordro PDF, birim bazında icmal PDF,
   toplu bordro ve icmal Excel, banka ödeme listesi (Excel / CSV).

## Hesaplama yöntemi

| Kalem | Formül |
|---|---|
| Aylık | gösterge (derece/kademe) × aylık katsayı |
| Ek gösterge | ek gösterge × aylık katsayı |
| Taban aylık | 1000 × taban aylık katsayısı |
| Kıdem aylığı | hizmet yılı (en çok 25) × 20 × aylık katsayı |
| Yan ödeme | puan × yan ödeme katsayısı |
| Özel hizmet / Ek ödeme (666) | (9500 × aylık katsayı + 1000 × taban katsayı) × oran % |
| Aile / çocuk yardımı | gösterge (2273 / 250 / 0-6 yaş 500) × aylık katsayı; vergi ve primden istisna |
| SGK (5510, 4/c) | kişi %9 + GSS %5; kurum %11 + GSS %7,5 (aile/çocuk hariç tüm ödemeler üzerinden) |
| Emekli keseneği (5434) | kişi %16 / kurum %20 (aylık + ek gösterge + taban + kıdem üzerinden) |
| 4/B (4/a) | kişi %14 (GSS dahil) + işsizlik %1; işveren %21,75 + işsizlik %2 |
| Gelir vergisi | (vergiye tabi ödemeler − kişi SGK payları − engellilik indirimi), yıllık kümülatif tarife; asgari ücret istisnası düşülür |
| Damga vergisi | damgaya tabi ödemeler × %0,759 − asgari ücret damga istisnası |

Tüm oranlar **Parametreler** ekranından değiştirilebilir. Kod içinde sabit mevzuat rakamı yoktur.

### Kontrol etmeniz gereken varsayımlar
- **Engellilik indirimi** tutarları 0 olarak gelir. Güncel tutarları girin.
- **SGK prim tavanı** asgari ücretin 7,5 katı varsayıldı; güncel katsayıyı kontrol edin.
- **4/B işveren payı** %21,75 varsayıldı.
- 5434'lülerin GSS matrahı, 5510'lularla aynı kabul edildi.
- Kapsam dışında kalanlar (ek kalem olarak elle girilebilir): döner sermaye ek ödemesi, nöbet/icap ücreti, toplu sözleşme
  ikramiyesi, makam/görev/temsil tazminatı, BES kesintisi, fark ve kıst (ay içi giriş/çıkış) hesapları.

## Geliştirici notları

```
bordro/hesap.py       hesap motoru (arayüzden bağımsız, Decimal ile)
bordro/veritabani.py  SQLite şeması ve veri işlemleri
bordro/raporlar.py    PDF (reportlab) ve Excel (openpyxl) çıktıları
bordro/iceaktar.py    Excel'den personel aktarımı
bordro/arayuz.py      Tkinter arayüzü
tests/                pytest testleri:  python -m pytest tests
```
