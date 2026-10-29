# TV Ana Ekran – güncellemeler

Bu dal, Android TV kutusundaki **Ana Ekran** uygulamasının internetten güncellenmesi için kullanılır.
Ana ekran 6 saatte bir (ve "+ → Ana ekran güncellemelerini denetle" ile istendiğinde) `update.json` dosyasına bakar;
`versionCode` kutudakinden büyükse `AnaEkran.apk` dosyasını indirir, SHA-256 ile doğrular ve kurulum penceresini açar.

- `update.json` – son sürüm bilgisi
- `AnaEkran.apk` – son sürüm
- `kaynak/` – uygulamanın kaynak kodu

Kişisel ayarlar (selamlama, konum, arka plan resmi) bu depoda değil, yalnızca kutuda saklanır.
İmza anahtarı da depoda değildir; yeni sürümler aynı anahtarla imzalanmalıdır.
