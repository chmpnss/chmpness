# 📺 TV Reklamsız

Android TV / Google TV'deki reklamları ve sponsorlu önerileri kaldırır, yerine sade ve hızlı bir ana ekran kurar.
Bilgisayardan **ADB** ile çalışır; TV'ye root gerekmez.

> Hiçbir şey silinmez. Paketler yalnızca devre dışı bırakılır ve `./tv-reklamsiz.sh geri-al` ile her şey eski haline döner.

## Ne yapar?

| Adım | Etki |
|---|---|
| `reklam` | Google TV öneri/sponsorlu servislerini ve Xiaomi PatchWall reklam servislerini kapatır |
| `dns` | Özel DNS'i AdGuard DNS'e ayarlar → uygulama içi reklamların çoğu engellenir (Android 9+) |
| `hiz` | Animasyonları 0.5x yapar → menüler daha çevik |
| `baslatici` | Reklamsız **Projectivy Launcher**'ı kurar, isterseniz stok (reklamlı) ana ekranı kapatır |

## Kurulum (5 dakika)

1. **Bilgisayara ADB kurun:** [Platform Tools](https://developer.android.com/tools/releases/platform-tools)
   (macOS: `brew install android-platform-tools`, Linux: `sudo apt install adb`).
   Windows'ta betiği **Git Bash** ile çalıştırın.
2. **TV'de geliştirici modunu açın:** Ayarlar › Sistem › Hakkında › *Android TV OS derlemesi*ne 7 kez basın.
3. **USB/ağ hata ayıklamayı açın:** Ayarlar › Sistem › Geliştirici seçenekleri › *USB hata ayıklama* (ve varsa *Ağ üzerinden hata ayıklama*).
4. TV'nin IP adresini bulun: Ayarlar › Ağ ve İnternet › bağlı ağ.

## Kullanım

```bash
./tv-reklamsiz.sh baglan 192.168.1.50   # TV'de çıkan izni onaylayın
./tv-reklamsiz.sh hepsi                  # her şeyi uygula
```

ya da komutsuz çalıştırıp menüden seçin:

```bash
./tv-reklamsiz.sh
```

Diğer komutlar: `tara` (şüpheli reklam/analiz paketlerini listeler), `kapat <paket>`, `geri-al`, `yardim`.

Kendi başlatıcı APK'nızı kullanmak isterseniz: `./tv-reklamsiz.sh baslatici FLauncher.apk`.
Farklı DNS için: `DNS_SUNUCU=family.adguard-dns.com ./tv-reklamsiz.sh dns`.

## Bilinmesi gerekenler

- **YouTube reklamları** DNS ile engellenemez (aynı sunuculardan gelir). Bunun için reklamsız bir istemci (ör. SmartTube) ya da YouTube Premium gerekir.
- Stok ana ekran kapatılınca bazı Google TV özellikleri (ör. profil/ana ekran önerileri) görünmez; Ayarlar, Play Store, Chromecast ve uygulamalar çalışmaya devam eder.
- Büyük bir sistem güncellemesinden sonra kapatılan servisler geri gelebilir; betiği tekrar çalıştırmanız yeterli.
- Paket listeleri `listeler/` klasöründedir; markanıza özel paketleri buraya ekleyebilirsiniz.
