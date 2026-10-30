"""SQLite veri katmanı: personel, parametreler, ek kalemler ve kaydedilmiş bordrolar."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, fields
from decimal import Decimal

from .hesap import (D, EkKalem, PARAMETRE_TANIMLARI, Personel, Satir, Sonuc,
                    VARSAYILAN_DILIMLER, VARSAYILAN_GOSTERGELER, hesapla)

SEMA = """
CREATE TABLE IF NOT EXISTS ayar (
    anahtar TEXT PRIMARY KEY,
    deger TEXT
);
CREATE TABLE IF NOT EXISTS parametre (
    gecerlilik TEXT NOT NULL,          -- YYYY-MM, bu aydan itibaren geçerli
    anahtar TEXT NOT NULL,
    deger TEXT NOT NULL,
    PRIMARY KEY (gecerlilik, anahtar)
);
CREATE TABLE IF NOT EXISTS vergi_dilimi (
    yil INTEGER NOT NULL,
    sira INTEGER NOT NULL,
    ust_sinir TEXT,                    -- NULL: son dilim
    oran TEXT NOT NULL,
    PRIMARY KEY (yil, sira)
);
CREATE TABLE IF NOT EXISTS gosterge (
    derece INTEGER NOT NULL,
    kademe INTEGER NOT NULL,
    gosterge INTEGER NOT NULL,
    PRIMARY KEY (derece, kademe)
);
CREATE TABLE IF NOT EXISTS personel (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tc TEXT NOT NULL UNIQUE,
    ad TEXT NOT NULL,
    soyad TEXT NOT NULL,
    unvan TEXT DEFAULT '',
    birim TEXT DEFAULT '',
    statu TEXT NOT NULL DEFAULT '657',
    iban TEXT DEFAULT '',
    derece INTEGER DEFAULT 1,
    kademe INTEGER DEFAULT 1,
    ek_gosterge INTEGER DEFAULT 0,
    hizmet_yili INTEGER DEFAULT 0,
    yan_odeme_puani INTEGER DEFAULT 0,
    ozel_hizmet_orani TEXT DEFAULT '0',
    ek_odeme_orani TEXT DEFAULT '0',
    sozlesme_ucreti TEXT DEFAULT '0',
    emeklilik TEXT DEFAULT '5510',
    es_yardimi INTEGER DEFAULT 0,
    cocuk_0_6 INTEGER DEFAULT 0,
    cocuk_6_ustu INTEGER DEFAULT 0,
    engellilik INTEGER DEFAULT 0,
    sendika_aidati TEXT DEFAULT '0',
    devreden_matrah TEXT DEFAULT '0',
    aktif INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS ek_kalem (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    personel_id INTEGER NOT NULL REFERENCES personel(id) ON DELETE CASCADE,
    donem TEXT,                        -- NULL: her ay sürekli
    ad TEXT NOT NULL,
    tutar TEXT NOT NULL,
    tur TEXT NOT NULL DEFAULT 'odeme',
    vergiye_tabi INTEGER DEFAULT 1,
    damgaya_tabi INTEGER DEFAULT 1,
    sgk_tabi INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS bordro (
    donem TEXT NOT NULL,
    personel_id INTEGER NOT NULL,
    brut TEXT, kesinti TEXT, net TEXT,
    gv_matrahi TEXT, kumulatif_matrah TEXT,
    detay TEXT NOT NULL,               -- JSON: personel kopyası ve tüm satırlar
    PRIMARY KEY (donem, personel_id)
);
CREATE TABLE IF NOT EXISTS donem (
    donem TEXT PRIMARY KEY,
    kilitli INTEGER DEFAULT 0
);
"""

DECIMAL_ALANLAR = {"ozel_hizmet_orani", "ek_odeme_orani", "sozlesme_ucreti",
                   "sendika_aidati", "devreden_matrah"}
BOOL_ALANLAR = {"es_yardimi", "aktif"}
PERSONEL_ALANLARI = [f.name for f in fields(Personel) if f.name != "id"]

# Ocak-Haziran 2026 katsayıları; diğer parametreler Temmuz ile aynı varsayılır.
OCAK_2026 = {"aylik_katsayi": "1.387871", "taban_katsayi": "22.722793",
             "yan_odeme_katsayi": "0.440141"}


class DonemKilitli(Exception):
    pass


class Veritabani:
    def __init__(self, yol: str):
        self.baglanti = sqlite3.connect(yol)
        self.baglanti.row_factory = sqlite3.Row
        self.baglanti.execute("PRAGMA foreign_keys = ON")
        self.baglanti.executescript(SEMA)
        self._varsayilanlari_yukle()

    def kapat(self):
        self.baglanti.close()

    def _sorgu(self, sql, *args):
        return self.baglanti.execute(sql, args).fetchall()

    def _varsayilanlari_yukle(self):
        b = self.baglanti
        if not self._sorgu("SELECT 1 FROM parametre LIMIT 1"):
            temmuz = {k: v for k, (_, v) in PARAMETRE_TANIMLARI.items()}
            self.parametre_kaydet("2026-07", temmuz)
            self.parametre_kaydet("2026-01", {**temmuz, **OCAK_2026})
        if not self._sorgu("SELECT 1 FROM vergi_dilimi LIMIT 1"):
            for yil, dilimler in VARSAYILAN_DILIMLER.items():
                self.dilim_kaydet(yil, dilimler)
        if not self._sorgu("SELECT 1 FROM gosterge LIMIT 1"):
            b.executemany("INSERT INTO gosterge VALUES (?,?,?)",
                          [(d, k + 1, g) for d, gs in VARSAYILAN_GOSTERGELER.items()
                           for k, g in enumerate(gs)])
        b.execute("INSERT OR IGNORE INTO ayar VALUES ('kurum_adi', 'T.C. SAĞLIK BAKANLIĞI')")
        b.execute("INSERT OR IGNORE INTO ayar VALUES ('birim_adi', '')")
        b.execute("INSERT OR IGNORE INTO ayar VALUES ('parametreler_dogrulandi', '0')")
        b.commit()

    # --- Ayarlar ---
    def ayar(self, anahtar: str, varsayilan: str = "") -> str:
        r = self._sorgu("SELECT deger FROM ayar WHERE anahtar=?", anahtar)
        return r[0]["deger"] if r else varsayilan

    def ayar_yaz(self, anahtar: str, deger: str):
        self.baglanti.execute("INSERT OR REPLACE INTO ayar VALUES (?,?)", (anahtar, deger))
        self.baglanti.commit()

    # --- Parametreler ---
    def parametre_donemleri(self) -> list[str]:
        return [r[0] for r in self._sorgu(
            "SELECT DISTINCT gecerlilik FROM parametre ORDER BY gecerlilik DESC")]

    def parametreler(self, donem: str) -> dict[str, str]:
        """Dönemde geçerli olan (en son başlangıçlı) parametre setini döndürür."""
        r = self._sorgu("SELECT MAX(gecerlilik) FROM parametre WHERE gecerlilik <= ?", donem)
        gecerlilik = r[0][0]
        if gecerlilik is None:
            raise ValueError(f"{donem} dönemi için tanımlı parametre yok.")
        return self.parametre_seti(gecerlilik)

    def parametre_seti(self, gecerlilik: str) -> dict[str, str]:
        return {r["anahtar"]: r["deger"] for r in self._sorgu(
            "SELECT anahtar, deger FROM parametre WHERE gecerlilik=?", gecerlilik)}

    def parametre_kaydet(self, gecerlilik: str, degerler: dict):
        for k, v in degerler.items():
            D(v)  # sayı değilse hata versin
        self.baglanti.executemany(
            "INSERT OR REPLACE INTO parametre VALUES (?,?,?)",
            [(gecerlilik, k, str(D(v))) for k, v in degerler.items()])
        self.baglanti.commit()

    def parametre_sil(self, gecerlilik: str):
        self.baglanti.execute("DELETE FROM parametre WHERE gecerlilik=?", (gecerlilik,))
        self.baglanti.commit()

    # --- Vergi dilimleri ---
    def dilim_yillari(self) -> list[int]:
        return [r[0] for r in self._sorgu("SELECT DISTINCT yil FROM vergi_dilimi ORDER BY yil DESC")]

    def dilimler(self, yil: int) -> list[tuple[Decimal | None, Decimal]]:
        r = self._sorgu("SELECT MAX(yil) FROM vergi_dilimi WHERE yil <= ?", yil)
        if r[0][0] is None:
            raise ValueError(f"{yil} yılı için gelir vergisi tarifesi tanımlı değil.")
        return [(None if x["ust_sinir"] is None else D(x["ust_sinir"]), D(x["oran"]))
                for x in self._sorgu("SELECT ust_sinir, oran FROM vergi_dilimi WHERE yil=? ORDER BY sira",
                                     r[0][0])]

    def dilim_kaydet(self, yil: int, dilimler):
        b = self.baglanti
        b.execute("DELETE FROM vergi_dilimi WHERE yil=?", (yil,))
        b.executemany("INSERT INTO vergi_dilimi VALUES (?,?,?,?)",
                      [(yil, i, None if ust in (None, "") else str(D(ust)), str(D(oran)))
                       for i, (ust, oran) in enumerate(dilimler)])
        b.commit()

    # --- Gösterge tablosu ---
    def gosterge(self, derece: int, kademe: int) -> int:
        r = self._sorgu("SELECT gosterge FROM gosterge WHERE derece=? AND kademe=?", derece, kademe)
        if not r:
            raise ValueError(f"{derece}. derece {kademe}. kademe için gösterge tanımlı değil.")
        return r[0][0]

    def gostergeler(self) -> list[tuple[int, int, int]]:
        return [tuple(r) for r in self._sorgu("SELECT derece, kademe, gosterge FROM gosterge ORDER BY derece, kademe")]

    def gosterge_kaydet(self, derece: int, kademe: int, gosterge: int):
        self.baglanti.execute("INSERT OR REPLACE INTO gosterge VALUES (?,?,?)", (derece, kademe, gosterge))
        self.baglanti.commit()

    # --- Personel ---
    @staticmethod
    def _personel(row) -> Personel:
        veri = dict(row)
        for a in DECIMAL_ALANLAR:
            veri[a] = D(veri[a])
        for a in BOOL_ALANLAR:
            veri[a] = bool(veri[a])
        return Personel(**veri)

    def personeller(self, sadece_aktif: bool = True) -> list[Personel]:
        sql = "SELECT * FROM personel" + (" WHERE aktif=1" if sadece_aktif else "") + " ORDER BY birim, ad, soyad"
        return [self._personel(r) for r in self._sorgu(sql)]

    def personel(self, pid: int) -> Personel:
        return self._personel(self._sorgu("SELECT * FROM personel WHERE id=?", pid)[0])

    def personel_kaydet(self, p: Personel) -> int:
        if not tc_gecerli(p.tc):
            raise ValueError("T.C. kimlik numarası geçersiz.")
        if not p.ad.strip() or not p.soyad.strip():
            raise ValueError("Ad ve soyad zorunludur.")
        if p.statu not in ("657", "4B"):
            raise ValueError("Statü 657 veya 4B olmalıdır.")
        if p.iban and not iban_gecerli(p.iban):
            raise ValueError("IBAN geçersiz.")
        p.iban = p.iban.replace(" ", "").upper()
        if p.statu == "657":
            self.gosterge(p.derece, p.kademe)  # tabloda yoksa hata verir
        degerler = [_db_deger(getattr(p, a)) for a in PERSONEL_ALANLARI]
        b = self.baglanti
        try:
            if p.id:
                b.execute(f"UPDATE personel SET {', '.join(a + '=?' for a in PERSONEL_ALANLARI)} WHERE id=?",
                          degerler + [p.id])
            else:
                cur = b.execute(f"INSERT INTO personel ({', '.join(PERSONEL_ALANLARI)}) "
                                f"VALUES ({', '.join('?' * len(PERSONEL_ALANLARI))})", degerler)
                p.id = cur.lastrowid
        except sqlite3.IntegrityError:
            raise ValueError("Bu T.C. kimlik numarası ile kayıtlı personel var.")
        b.commit()
        return p.id

    def personel_sil(self, pid: int):
        """Bordrosu olan personel silinmez, pasife alınır."""
        b = self.baglanti
        if self._sorgu("SELECT 1 FROM bordro WHERE personel_id=? LIMIT 1", pid):
            b.execute("UPDATE personel SET aktif=0 WHERE id=?", (pid,))
        else:
            b.execute("DELETE FROM personel WHERE id=?", (pid,))
        b.commit()

    # --- Ek ödeme / kesintiler ---
    def ek_kalem_listesi(self, pid: int) -> list[dict]:
        return [dict(r) for r in self._sorgu(
            "SELECT * FROM ek_kalem WHERE personel_id=? ORDER BY donem IS NOT NULL, donem, id", pid)]

    def ek_kalemler(self, pid: int, donem: str) -> list[EkKalem]:
        return [EkKalem(ad=r["ad"], tutar=D(r["tutar"]), tur=r["tur"],
                        vergiye_tabi=bool(r["vergiye_tabi"]), damgaya_tabi=bool(r["damgaya_tabi"]),
                        sgk_tabi=bool(r["sgk_tabi"]))
                for r in self._sorgu("SELECT * FROM ek_kalem WHERE personel_id=? AND (donem IS NULL OR donem=?) "
                                     "ORDER BY id", pid, donem)]

    def ek_kalem_ekle(self, pid: int, donem: str | None, k: EkKalem):
        if k.tur not in ("odeme", "kesinti"):
            raise ValueError("Tür 'odeme' veya 'kesinti' olmalıdır.")
        self.baglanti.execute(
            "INSERT INTO ek_kalem (personel_id, donem, ad, tutar, tur, vergiye_tabi, damgaya_tabi, sgk_tabi) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (pid, donem or None, k.ad, str(D(k.tutar)), k.tur, int(k.vergiye_tabi), int(k.damgaya_tabi),
             int(k.sgk_tabi)))
        self.baglanti.commit()

    def ek_kalem_sil(self, kid: int):
        self.baglanti.execute("DELETE FROM ek_kalem WHERE id=?", (kid,))
        self.baglanti.commit()

    # --- Bordro ---
    def onceki_kumulatif_matrah(self, pid: int, donem: str) -> Decimal:
        yil = donem[:4]
        r = self._sorgu("SELECT gv_matrahi FROM bordro WHERE personel_id=? AND donem LIKE ? AND donem < ?",
                        pid, f"{yil}-%", donem)
        return sum((D(x[0]) for x in r), Decimal("0"))

    def donem_hesapla(self, donem: str) -> list[Sonuc]:
        """Aktif tüm personelin bordrosunu hesaplar (kaydetmez)."""
        donem_dogrula(donem)
        parametreler = self.parametreler(donem)
        dilimler = self.dilimler(int(donem[:4]))
        sonuclar = []
        for p in self.personeller():
            gosterge = self.gosterge(p.derece, p.kademe) if p.statu == "657" else 0
            sonuclar.append(hesapla(p, donem, parametreler, dilimler, gosterge=gosterge,
                                    onceki_kumulatif_matrah=self.onceki_kumulatif_matrah(p.id, donem),
                                    ek_kalemler=self.ek_kalemler(p.id, donem)))
        return sonuclar

    def donem_kilitli(self, donem: str) -> bool:
        r = self._sorgu("SELECT kilitli FROM donem WHERE donem=?", donem)
        return bool(r and r[0][0])

    def donem_kilitle(self, donem: str, kilitli: bool = True):
        self.baglanti.execute("INSERT OR REPLACE INTO donem VALUES (?,?)", (donem, int(kilitli)))
        self.baglanti.commit()

    def kayitli_donemler(self) -> list[str]:
        return [r[0] for r in self._sorgu("SELECT DISTINCT donem FROM bordro ORDER BY donem DESC")]

    def bordro_kaydet(self, donem: str, sonuclar: list[Sonuc]):
        if self.donem_kilitli(donem):
            raise DonemKilitli(f"{donem} dönemi kilitli; önce kilidi açın.")
        b = self.baglanti
        b.execute("DELETE FROM bordro WHERE donem=?", (donem,))
        b.executemany("INSERT INTO bordro VALUES (?,?,?,?,?,?,?,?)", [
            (donem, s.personel.id, str(s.brut), str(s.kesinti_toplami), str(s.net),
             str(s.gv_matrahi), str(s.kumulatif_matrah), json.dumps(sonuc_sozluk(s), ensure_ascii=False))
            for s in sonuclar])
        b.execute("INSERT OR IGNORE INTO donem VALUES (?, 0)", (donem,))
        b.commit()

    def kayitli_bordro(self, donem: str) -> list[Sonuc]:
        sonuclar = [sozlukten_sonuc(json.loads(r[0]))
                    for r in self._sorgu("SELECT detay FROM bordro WHERE donem=?", donem)]
        return sorted(sonuclar, key=lambda s: (s.personel.birim, s.personel.ad, s.personel.soyad))


def _db_deger(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, Decimal):
        return str(v)
    return v


def sonuc_sozluk(s: Sonuc) -> dict:
    def satirlar(liste):
        return [{**asdict(x), "tutar": str(x.tutar)} for x in liste]
    return {"personel": {k: _db_deger(v) for k, v in asdict(s.personel).items()},
            "donem": s.donem, "odemeler": satirlar(s.odemeler), "kesintiler": satirlar(s.kesintiler),
            "isveren": satirlar(s.isveren), "gv_matrahi": str(s.gv_matrahi),
            "kumulatif_matrah": str(s.kumulatif_matrah), "sgk_matrahi": str(s.sgk_matrahi)}


def sozlukten_sonuc(v: dict) -> Sonuc:
    def satirlar(liste):
        return [Satir(**{**x, "tutar": D(x["tutar"])}) for x in liste]
    return Sonuc(personel=Veritabani._personel(v["personel"]), donem=v["donem"],
                 odemeler=satirlar(v["odemeler"]), kesintiler=satirlar(v["kesintiler"]),
                 isveren=satirlar(v["isveren"]), gv_matrahi=D(v["gv_matrahi"]),
                 kumulatif_matrah=D(v["kumulatif_matrah"]), sgk_matrahi=D(v["sgk_matrahi"]))


def donem_dogrula(donem: str):
    try:
        yil, ay = donem.split("-")
        if len(yil) != 4 or not 1 <= int(ay) <= 12:
            raise ValueError
    except ValueError:
        raise ValueError("Dönem YYYY-AA biçiminde olmalıdır (örn. 2026-07).")


def tc_gecerli(tc: str) -> bool:
    tc = tc.strip()
    if len(tc) != 11 or not tc.isdigit() or tc[0] == "0":
        return False
    r = [int(c) for c in tc]
    on = ((r[0] + r[2] + r[4] + r[6] + r[8]) * 7 - (r[1] + r[3] + r[5] + r[7])) % 10
    return on == r[9] and sum(r[:10]) % 10 == r[10]


def iban_gecerli(iban: str) -> bool:
    iban = iban.replace(" ", "").upper()
    if not (iban.startswith("TR") and len(iban) == 26 and iban[2:].isdigit()):
        return False
    sayi = "".join(str(int(c, 36)) for c in iban[4:] + iban[:4])
    return int(sayi) % 97 == 1
