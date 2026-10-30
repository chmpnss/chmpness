"""Maaş hesap motoru.

Arayüzden ve veritabanından bağımsızdır; tüm tutarlar Decimal ile hesaplanır
ve her satır kuruşa yuvarlanır. Katsayı, oran ve tutarların tamamı
`parametreler` sözlüğünden okunur; kod içinde sabit mevzuat rakamı yoktur.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

SIFIR = Decimal("0")
YUZ = Decimal("100")


def D(deger) -> Decimal:
    if isinstance(deger, Decimal):
        return deger
    if deger in (None, ""):
        return SIFIR
    metin = str(deger).strip().replace(" ", "")
    if "," in metin:  # Türkçe yazım: 3.500,75 -> 3500.75
        metin = metin.replace(".", "").replace(",", ".")
    elif metin.count(".") > 1:  # 1.250.000 -> 1250000
        metin = metin.replace(".", "")
    return Decimal(metin)


def yuvarla(tutar: Decimal) -> Decimal:
    return D(tutar).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class Personel:
    id: int | None = None
    tc: str = ""
    ad: str = ""
    soyad: str = ""
    unvan: str = ""
    birim: str = ""
    statu: str = "657"            # "657" kadrolu memur, "4B" sözleşmeli
    iban: str = ""
    derece: int = 1
    kademe: int = 1
    ek_gosterge: int = 0
    hizmet_yili: int = 0
    yan_odeme_puani: int = 0
    ozel_hizmet_orani: Decimal = SIFIR   # % olarak, örn. 140
    ek_odeme_orani: Decimal = SIFIR      # % olarak (666 KHK), örn. 60
    sozlesme_ucreti: Decimal = SIFIR     # 4/B brüt sözleşme ücreti
    emeklilik: str = "5510"              # "5510" (2008 sonrası) veya "5434"
    es_yardimi: bool = False
    cocuk_0_6: int = 0
    cocuk_6_ustu: int = 0
    engellilik: int = 0                  # 0 yok, 1-2-3 derece
    sendika_aidati: Decimal = SIFIR
    devreden_matrah: Decimal = SIFIR     # yıl içinde başka kurumdan gelen kümülatif GV matrahı
    aktif: bool = True

    @property
    def ad_soyad(self) -> str:
        return f"{self.ad} {self.soyad}".strip()


@dataclass
class EkKalem:
    """Personele o dönem için elle girilen ödeme veya kesinti."""
    ad: str
    tutar: Decimal
    tur: str = "odeme"            # "odeme" veya "kesinti"
    vergiye_tabi: bool = True
    damgaya_tabi: bool = True
    sgk_tabi: bool = False


@dataclass
class Satir:
    ad: str
    tutar: Decimal
    gv: bool = True       # gelir vergisi matrahına girer
    dv: bool = True       # damga vergisine tabi
    sgk: bool = True      # SGK / GSS prim matrahına girer


@dataclass
class Sonuc:
    personel: Personel
    donem: str
    odemeler: list[Satir] = field(default_factory=list)
    kesintiler: list[Satir] = field(default_factory=list)
    isveren: list[Satir] = field(default_factory=list)
    gv_matrahi: Decimal = SIFIR
    kumulatif_matrah: Decimal = SIFIR    # bu ay dahil yıl içi toplam
    sgk_matrahi: Decimal = SIFIR

    @property
    def brut(self) -> Decimal:
        return sum((s.tutar for s in self.odemeler), SIFIR)

    @property
    def kesinti_toplami(self) -> Decimal:
        return sum((s.tutar for s in self.kesintiler), SIFIR)

    @property
    def net(self) -> Decimal:
        return self.brut - self.kesinti_toplami

    @property
    def isveren_toplami(self) -> Decimal:
        return sum((s.tutar for s in self.isveren), SIFIR)

    def kesinti(self, ad: str) -> Decimal:
        return sum((s.tutar for s in self.kesintiler if s.ad == ad), SIFIR)

    def odeme(self, ad: str) -> Decimal:
        return sum((s.tutar for s in self.odemeler if s.ad == ad), SIFIR)


# Kesinti ve işveren payı satır adları; raporlar ve icmal bu adları kullanır.
GELIR_VERGISI = "Gelir Vergisi"
DAMGA_VERGISI = "Damga Vergisi"
SENDIKA = "Sendika Aidatı"
GSS_KISI = "GSS Primi (Kişi)"
GSS_KURUM = "GSS Primi (Kurum)"
SGK_KISI = "SGK Malullük-Yaşlılık (Kişi)"
SGK_KURUM = "SGK Malullük-Yaşlılık (Kurum)"
KESENEK_KISI = "Emekli Keseneği (Kişi)"
KESENEK_KURUM = "Emekli Keseneği (Kurum)"
ISSIZLIK_KISI = "İşsizlik Sigortası (Kişi)"
ISSIZLIK_KURUM = "İşsizlik Sigortası (Kurum)"


def vergi_tarifesi(matrah: Decimal, dilimler: list[tuple[Decimal | None, Decimal]]) -> Decimal:
    """Artan oranlı tarifeye göre toplam vergi. dilimler: [(üst sınır, oran %), ...]
    son dilimin üst sınırı None olur."""
    matrah = D(matrah)
    vergi = SIFIR
    alt = SIFIR
    for ust, oran in dilimler:
        if matrah <= alt:
            break
        dilim_ust = matrah if ust is None else min(matrah, D(ust))
        vergi += (dilim_ust - alt) * D(oran) / YUZ
        if ust is None:
            break
        alt = D(ust)
    return vergi


def kumulatif_vergi(onceki: Decimal, bu_ay: Decimal, dilimler) -> Decimal:
    return vergi_tarifesi(onceki + bu_ay, dilimler) - vergi_tarifesi(onceki, dilimler)


def en_yuksek_dm_ayligi(p: dict) -> Decimal:
    """Özel hizmet tazminatı ve ek ödemenin hesaplandığı en yüksek devlet memuru aylığı."""
    return D(p["eydm_gosterge"]) * D(p["aylik_katsayi"]) + 1000 * D(p["taban_katsayi"])


def asgari_ucret_istisnasi(p: dict, ay: int, dilimler) -> tuple[Decimal, Decimal]:
    """Asgari ücrete isabet eden (gelir vergisi, damga vergisi) istisna tutarları."""
    asg = D(p["asgari_ucret_brut"])
    if asg <= 0:
        return SIFIR, SIFIR
    kesinti_orani = (D(p["sgk_4a_kisi"]) + D(p["issizlik_kisi"])) / YUZ
    asg_matrah = asg - yuvarla(asg * kesinti_orani)
    gv = kumulatif_vergi(asg_matrah * (ay - 1), asg_matrah, dilimler)
    dv = asg * D(p["damga_orani"]) / YUZ
    return yuvarla(gv), yuvarla(dv)


def hesapla(personel: Personel, donem: str, parametreler: dict, dilimler,
            gosterge: int = 0, onceki_kumulatif_matrah: Decimal = SIFIR,
            ek_kalemler: list[EkKalem] | None = None) -> Sonuc:
    """Bir personelin bir aylık maaşını hesaplar.

    donem: "YYYY-MM". gosterge: derece/kademeye karşılık gelen gösterge (yalnız 657).
    onceki_kumulatif_matrah: aynı yıl içinde önceki aylarda oluşan GV matrahı toplamı.
    """
    p = {k: D(v) for k, (_, v) in PARAMETRE_TANIMLARI.items()}
    p.update({k: D(v) for k, v in parametreler.items()})
    ay = int(donem.split("-")[1])
    ak, tk, yk = p["aylik_katsayi"], p["taban_katsayi"], p["yan_odeme_katsayi"]
    s = Sonuc(personel=personel, donem=donem)
    ode = s.odemeler.append

    kesenek_matrahi = SIFIR  # 5434'e tabi memurlarda emekli keseneği matrahı
    eydm = en_yuksek_dm_ayligi(p)

    if personel.statu == "657":
        aylik = yuvarla(D(gosterge) * ak)
        ek_gosterge = yuvarla(D(personel.ek_gosterge) * ak)
        taban = yuvarla(1000 * tk)
        kidem = yuvarla(min(personel.hizmet_yili, 25) * 20 * ak)
        ode(Satir("Aylık (Gösterge)", aylik))
        if ek_gosterge:
            ode(Satir("Ek Gösterge Aylığı", ek_gosterge))
        ode(Satir("Taban Aylık", taban))
        if kidem:
            ode(Satir("Kıdem Aylığı", kidem))
        if personel.yan_odeme_puani:
            ode(Satir("Yan Ödeme", yuvarla(personel.yan_odeme_puani * yk)))
        if D(personel.ozel_hizmet_orani):
            ode(Satir("Özel Hizmet Tazminatı", yuvarla(eydm * D(personel.ozel_hizmet_orani) / YUZ)))
        kesenek_matrahi = aylik + ek_gosterge + taban + kidem
    elif personel.statu == "4B":
        ode(Satir("Sözleşme Ücreti", yuvarla(personel.sozlesme_ucreti)))
    else:
        raise ValueError(f"Bilinmeyen statü: {personel.statu}")

    if D(personel.ek_odeme_orani):
        ode(Satir("Ek Ödeme (666 KHK)", yuvarla(eydm * D(personel.ek_odeme_orani) / YUZ)))

    # Aile ve çocuk yardımı vergiden ve primden istisnadır.
    if personel.es_yardimi:
        ode(Satir("Aile Yardımı (Eş)", yuvarla(p["es_yardimi_gosterge"] * ak), gv=False, dv=False, sgk=False))
    cocuk = (yuvarla(personel.cocuk_0_6 * p["cocuk_0_6_gosterge"] * ak)
             + yuvarla(personel.cocuk_6_ustu * p["cocuk_gosterge"] * ak))
    if cocuk:
        ode(Satir("Çocuk Yardımı", cocuk, gv=False, dv=False, sgk=False))

    ek_kesintiler = []
    for k in ek_kalemler or []:
        if k.tur == "odeme":
            ode(Satir(k.ad, yuvarla(k.tutar), gv=k.vergiye_tabi, dv=k.damgaya_tabi, sgk=k.sgk_tabi))
        else:
            ek_kesintiler.append(Satir(k.ad, yuvarla(k.tutar)))

    # --- Sosyal güvenlik ---
    sgk_matrahi = sum((x.tutar for x in s.odemeler if x.sgk), SIFIR)
    tavan = D(p["asgari_ucret_brut"]) * p["sgk_tavan_kat"]
    if tavan > 0:
        sgk_matrahi = min(sgk_matrahi, tavan)
    s.sgk_matrahi = sgk_matrahi
    kes, isv = s.kesintiler.append, s.isveren.append

    def oran(matrah, anahtar):
        return yuvarla(matrah * p[anahtar] / YUZ)

    if personel.statu == "4B":
        kes(Satir(SGK_KISI, oran(sgk_matrahi, "sgk_4a_kisi") - oran(sgk_matrahi, "gss_kisi")))
        kes(Satir(GSS_KISI, oran(sgk_matrahi, "gss_kisi")))
        kes(Satir(ISSIZLIK_KISI, oran(sgk_matrahi, "issizlik_kisi")))
        isv(Satir("SGK İşveren Payı", oran(sgk_matrahi, "sgk_4a_isveren")))
        isv(Satir(ISSIZLIK_KURUM, oran(sgk_matrahi, "issizlik_isveren")))
    elif personel.emeklilik == "5434":
        kes(Satir(KESENEK_KISI, oran(kesenek_matrahi, "kesenek_kisi")))
        kes(Satir(GSS_KISI, oran(sgk_matrahi, "gss_kisi")))
        isv(Satir(KESENEK_KURUM, oran(kesenek_matrahi, "kesenek_kurum")))
        isv(Satir(GSS_KURUM, oran(sgk_matrahi, "gss_kurum")))
    else:
        kes(Satir(SGK_KISI, oran(sgk_matrahi, "sgk_4c_kisi")))
        kes(Satir(GSS_KISI, oran(sgk_matrahi, "gss_kisi")))
        isv(Satir(SGK_KURUM, oran(sgk_matrahi, "sgk_4c_kurum")))
        isv(Satir(GSS_KURUM, oran(sgk_matrahi, "gss_kurum")))
    sgk_kisi_toplam = sum((x.tutar for x in s.kesintiler), SIFIR)

    # --- Gelir vergisi (kümülatif) ---
    vergiye_tabi = sum((x.tutar for x in s.odemeler if x.gv), SIFIR)
    engelli = p.get(f"engelli_indirimi_{personel.engellilik}", SIFIR) if personel.engellilik else SIFIR
    matrah = max(vergiye_tabi - sgk_kisi_toplam - engelli, SIFIR)
    onceki = D(onceki_kumulatif_matrah) + D(personel.devreden_matrah)
    gv = yuvarla(kumulatif_vergi(onceki, matrah, dilimler))
    gv_istisna, dv_istisna = asgari_ucret_istisnasi(p, ay, dilimler)
    s.gv_matrahi = matrah
    s.kumulatif_matrah = onceki + matrah
    kes(Satir(GELIR_VERGISI, max(gv - gv_istisna, SIFIR)))

    damgaya_tabi = sum((x.tutar for x in s.odemeler if x.dv), SIFIR)
    dv = yuvarla(damgaya_tabi * p["damga_orani"] / YUZ)
    kes(Satir(DAMGA_VERGISI, max(dv - dv_istisna, SIFIR)))

    if D(personel.sendika_aidati):
        kes(Satir(SENDIKA, yuvarla(personel.sendika_aidati)))
    s.kesintiler.extend(ek_kesintiler)
    return s


# Parametre anahtarı -> (açıklama, varsayılan değer). Varsayılanlar Temmuz 2026
# dönemi içindir; her dönem genelgeden kontrol edilip güncellenmelidir.
PARAMETRE_TANIMLARI: dict[str, tuple[str, str]] = {
    "aylik_katsayi": ("Memur aylık katsayısı", "1.575512"),
    "taban_katsayi": ("Taban aylık katsayısı", "25.794915"),
    "yan_odeme_katsayi": ("Yan ödeme katsayısı", "0.499649"),
    "eydm_gosterge": ("En yüksek devlet memuru gösterge + ek gösterge toplamı", "9500"),
    "es_yardimi_gosterge": ("Aile yardımı (eş) gösterge rakamı", "2273"),
    "cocuk_gosterge": ("Çocuk yardımı gösterge rakamı (6 yaş üstü)", "250"),
    "cocuk_0_6_gosterge": ("Çocuk yardımı gösterge rakamı (0-6 yaş)", "500"),
    "asgari_ucret_brut": ("Brüt asgari ücret (GV/DV istisnası ve SGK tavanı için)", "33030.00"),
    "damga_orani": ("Damga vergisi oranı (%)", "0.759"),
    "sgk_tavan_kat": ("SGK prim tavanı (asgari ücretin kaç katı, 0 = tavan yok)", "7.5"),
    "sgk_4c_kisi": ("5510 (4/c) malullük-yaşlılık kişi payı (%)", "9"),
    "sgk_4c_kurum": ("5510 (4/c) malullük-yaşlılık kurum payı (%)", "11"),
    "kesenek_kisi": ("5434 emekli keseneği kişi payı (%)", "16"),
    "kesenek_kurum": ("5434 emekli keseneği kurum payı (%)", "20"),
    "gss_kisi": ("Genel sağlık sigortası kişi payı (%)", "5"),
    "gss_kurum": ("Genel sağlık sigortası kurum payı (%)", "7.5"),
    "sgk_4a_kisi": ("4/a (4/B sözleşmeli) SGK kişi payı, GSS dahil (%)", "14"),
    "sgk_4a_isveren": ("4/a (4/B sözleşmeli) SGK işveren payı, GSS dahil (%)", "21.75"),
    "issizlik_kisi": ("İşsizlik sigortası kişi payı (%)", "1"),
    "issizlik_isveren": ("İşsizlik sigortası işveren payı (%)", "2"),
    "engelli_indirimi_1": ("Engellilik indirimi 1. derece (aylık TL)", "0"),
    "engelli_indirimi_2": ("Engellilik indirimi 2. derece (aylık TL)", "0"),
    "engelli_indirimi_3": ("Engellilik indirimi 3. derece (aylık TL)", "0"),
}

# 2026 ücret gelirleri tarifesi (yıllık kümülatif matrah üst sınırı, oran %)
VARSAYILAN_DILIMLER = {
    2026: [("190000", "15"), ("400000", "20"), ("1500000", "27"), ("5300000", "35"), (None, "40")],
}

# 657 sayılı Kanun md. 43 gösterge tablosu (derece -> kademe göstergeleri)
VARSAYILAN_GOSTERGELER = {
    1: [1320, 1380, 1440, 1500],
    2: [1155, 1210, 1265, 1320],
    3: [1020, 1065, 1110, 1155],
    4: [915, 950, 985, 1020],
    5: [835, 865, 895, 915],
    6: [760, 785, 810, 835],
    7: [705, 720, 740, 760],
    8: [660, 675, 690, 705],
    9: [620, 630, 645, 660],
    10: [590, 600, 610, 620],
    11: [560, 570, 580, 590],
    12: [545, 550, 555, 560],
    13: [530, 535, 540, 545],
    14: [515, 520, 525, 530],
    15: [500, 505, 510, 515],
}
