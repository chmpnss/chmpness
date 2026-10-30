"""Tkinter masaüstü arayüzü."""
from __future__ import annotations

import os
import shutil
import sys
import tkinter as tk
from datetime import date, datetime
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import iceaktar, raporlar
from .hesap import D, EkKalem, PARAMETRE_TANIMLARI, Personel
from .raporlar import AYLAR, donem_adi, tl
from .veritabani import DonemKilitli, Veritabani, donem_dogrula

UYGULAMA_ADI = "Bordro Programı"


def veri_klasoru() -> str:
    klasor = os.path.join(os.path.expanduser("~"), "BordroProgrami")
    os.makedirs(klasor, exist_ok=True)
    return klasor


def hata_goster(fonk):
    """Arayüz olaylarında oluşan hataları kullanıcıya mesaj kutusuyla gösterir."""
    def sarici(*args, **kwargs):
        try:
            return fonk(*args, **kwargs)
        except (ValueError, DonemKilitli, RuntimeError) as e:
            messagebox.showerror(UYGULAMA_ADI, str(e))
        except Exception as e:  # beklenmeyen hata: programı kapatma
            messagebox.showerror(UYGULAMA_ADI, f"Beklenmeyen hata:\n{type(e).__name__}: {e}")
    return sarici


class Uygulama(tk.Tk):
    def __init__(self, db_yolu: str | None = None):
        super().__init__()
        self.db_yolu = db_yolu or os.path.join(veri_klasoru(), "bordro.db")
        self.db = Veritabani(self.db_yolu)
        self.title(UYGULAMA_ADI)
        self.geometry("1260x740")
        self.minsize(980, 600)
        stil = ttk.Style(self)
        if "clam" in stil.theme_names() and sys.platform != "win32":
            stil.theme_use("clam")
        stil.configure("Uyari.TLabel", foreground="#9a3412", font=("TkDefaultFont", 9, "bold"))
        stil.configure("Toplam.TLabel", font=("TkDefaultFont", 10, "bold"))

        self._menu()
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)
        self.personel_sekmesi = PersonelSekmesi(nb, self)
        self.bordro_sekmesi = BordroSekmesi(nb, self)
        self.parametre_sekmesi = ParametreSekmesi(nb, self)
        nb.add(self.personel_sekmesi, text="  Personel  ")
        nb.add(self.bordro_sekmesi, text="  Bordro  ")
        nb.add(self.parametre_sekmesi, text="  Parametreler ve Ayarlar  ")
        nb.bind("<<NotebookTabChanged>>", lambda e: self.bordro_sekmesi.uyari_guncelle())

        durum = ttk.Label(self, text=f"Veritabanı: {self.db_yolu}", anchor="w", foreground="#555")
        durum.pack(fill="x", padx=8, pady=(0, 4))
        self.protocol("WM_DELETE_WINDOW", self.kapat)

    def _menu(self):
        m = tk.Menu(self)
        dosya = tk.Menu(m, tearoff=False)
        dosya.add_command(label="Yedek Al...", command=self.yedek_al)
        dosya.add_command(label="Veri Klasörünü Aç", command=lambda: _klasor_ac(os.path.dirname(self.db_yolu)))
        dosya.add_separator()
        dosya.add_command(label="Çıkış", command=self.kapat)
        m.add_cascade(label="Dosya", menu=dosya)
        self.config(menu=m)

    @hata_goster
    def yedek_al(self):
        ad = f"bordro_yedek_{datetime.now():%Y%m%d_%H%M}.db"
        hedef = filedialog.asksaveasfilename(title="Yedek dosyası", initialfile=ad, defaultextension=".db",
                                             filetypes=[("Veritabanı", "*.db")])
        if hedef:
            self.db.baglanti.commit()
            shutil.copy2(self.db_yolu, hedef)
            messagebox.showinfo(UYGULAMA_ADI, f"Yedek alındı:\n{hedef}")

    def kapat(self):
        self.db.kapat()
        self.destroy()


def _klasor_ac(yol: str):
    if sys.platform == "win32":
        os.startfile(yol)  # noqa: S606
    elif sys.platform == "darwin":
        os.system(f'open "{yol}"')
    else:
        os.system(f'xdg-open "{yol}" >/dev/null 2>&1 &')


def _form_satiri(ust, satir, etiket, widget, sutun=0):
    ttk.Label(ust, text=etiket).grid(row=satir, column=sutun, sticky="w", padx=(0, 6), pady=2)
    widget.grid(row=satir, column=sutun + 1, sticky="ew", pady=2)
    return widget


# =========================================================================== Personel
class PersonelSekmesi(ttk.Frame):
    METIN = [("tc", "T.C. Kimlik No"), ("ad", "Ad"), ("soyad", "Soyad"), ("unvan", "Unvan"),
             ("birim", "Birim"), ("iban", "IBAN")]
    MEMUR = [("derece", "Derece"), ("kademe", "Kademe"), ("ek_gosterge", "Ek Gösterge"),
             ("hizmet_yili", "Hizmet Yılı"), ("yan_odeme_puani", "Yan Ödeme Puanı"),
             ("ozel_hizmet_orani", "Özel Hizmet %")]
    ORTAK = [("ek_odeme_orani", "Ek Ödeme % (666 KHK)"), ("sozlesme_ucreti", "Sözleşme Ücreti (4/B)"),
             ("cocuk_0_6", "Çocuk (0-6 yaş)"), ("cocuk_6_ustu", "Çocuk (6 yaş üstü)"),
             ("sendika_aidati", "Sendika Aidatı"), ("devreden_matrah", "Devreden GV Matrahı")]

    def __init__(self, ust, app: Uygulama):
        super().__init__(ust, padding=6)
        self.app = app
        self.secili_id: int | None = None

        # Sağdaki form önce yerleşir ki pencere daralınca liste küçülsün, form kırpılmasın.
        sag = ttk.Frame(self, padding=(10, 0, 0, 0))
        sag.pack(side="right", fill="y")
        sol = ttk.Frame(self)
        sol.pack(side="left", fill="both", expand=True)
        ara = ttk.Frame(sol)
        ara.pack(fill="x")
        ttk.Label(ara, text="Ara:").pack(side="left")
        self.ara = tk.StringVar()
        self.ara.trace_add("write", lambda *_: self.listele())
        ttk.Entry(ara, textvariable=self.ara, width=20).pack(side="left", padx=4)
        self.pasif = tk.BooleanVar(value=False)
        ttk.Checkbutton(ara, text="Pasifleri göster", variable=self.pasif, command=self.listele).pack(side="left")
        ttk.Button(ara, text="Excel'den Aktar...", command=self.excelden_aktar).pack(side="right")
        ttk.Button(ara, text="Excel Şablonu...", command=self.sablon).pack(side="right", padx=4)

        sutunlar = ("tc", "adsoyad", "unvan", "birim", "statu", "aktif")
        self.liste = ttk.Treeview(sol, columns=sutunlar, show="headings", selectmode="browse")
        for s, b, w in zip(sutunlar, ("T.C. No", "Ad Soyad", "Unvan", "Birim", "Statü", "Durum"),
                           (100, 170, 140, 140, 55, 55)):
            self.liste.heading(s, text=b)
            self.liste.column(s, width=w, anchor="w")
        kay = ttk.Scrollbar(sol, orient="vertical", command=self.liste.yview)
        self.liste.configure(yscrollcommand=kay.set)
        self.liste.pack(side="left", fill="both", expand=True, pady=(6, 0))
        kay.pack(side="left", fill="y", pady=(6, 0))
        self.liste.bind("<<TreeviewSelect>>", self.secildi)
        self.sayi = ttk.Label(sol)

        self.degiskenler: dict[str, tk.Variable] = {}
        form = ttk.LabelFrame(sag, text="Kimlik ve Kadro", padding=6)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        r = 0
        for alan, etiket in self.METIN:
            self.degiskenler[alan] = tk.StringVar()
            _form_satiri(form, r, etiket, ttk.Entry(form, textvariable=self.degiskenler[alan], width=24))
            r += 1
        self.degiskenler["statu"] = tk.StringVar(value="657")
        cb = ttk.Combobox(form, textvariable=self.degiskenler["statu"], values=["657", "4B"], state="readonly",
                          width=8)
        _form_satiri(form, r, "Statü", cb)
        cb.bind("<<ComboboxSelected>>", lambda e: self.statu_degisti())
        r += 1
        self.degiskenler["emeklilik"] = tk.StringVar(value="5510")
        self.emeklilik_cb = ttk.Combobox(form, textvariable=self.degiskenler["emeklilik"],
                                         values=["5510", "5434"], state="readonly", width=8)
        _form_satiri(form, r, "Emeklilik (memur)", self.emeklilik_cb)

        mf = ttk.LabelFrame(sag, text="Maaş Bilgileri", padding=6)
        mf.pack(fill="x", pady=6)
        self.memur_girdileri = []
        for i, (alan, etiket) in enumerate(self.MEMUR + self.ORTAK):
            self.degiskenler[alan] = tk.StringVar(value="0")
            e = _form_satiri(mf, i // 2, etiket, ttk.Entry(mf, textvariable=self.degiskenler[alan], width=10),
                             sutun=(i % 2) * 2)
            if i % 2 == 0:
                e.grid_configure(padx=(0, 12))
            if (alan, etiket) in self.MEMUR:
                self.memur_girdileri.append(e)
            if alan == "sozlesme_ucreti":
                self.sozlesme_girdisi = e
        r = (len(self.MEMUR) + len(self.ORTAK) + 1) // 2
        self.degiskenler["engellilik"] = tk.StringVar(value="0")
        _form_satiri(mf, r, "Engellilik Derecesi", ttk.Combobox(
            mf, textvariable=self.degiskenler["engellilik"], values=["0", "1", "2", "3"], state="readonly",
            width=6), sutun=2)
        self.degiskenler["es_yardimi"] = tk.BooleanVar(value=False)
        ttk.Checkbutton(mf, text="Eş için aile yardımı alır", variable=self.degiskenler["es_yardimi"]).grid(
            row=r, column=0, columnspan=2, sticky="w")

        dug = ttk.Frame(sag)
        dug.pack(fill="x")
        ttk.Button(dug, text="Yeni", command=self.temizle).pack(side="left")
        ttk.Button(dug, text="Kaydet", command=self.kaydet).pack(side="left", padx=4)
        ttk.Button(dug, text="Sil / Pasife Al", command=self.sil).pack(side="left")
        ttk.Button(sag, text="Ek Ödeme ve Kesintiler...", command=self.ek_kalemler).pack(fill="x", pady=(6, 0))
        self.aktif_btn = ttk.Button(sag, text="Aktif Yap", command=self.aktif_yap)

        self.listele()
        self.statu_degisti()

    def statu_degisti(self):
        memur = self.degiskenler["statu"].get() == "657"
        for e in self.memur_girdileri + [self.emeklilik_cb]:
            e.configure(state="normal" if memur else "disabled")
        self.emeklilik_cb.configure(state="readonly" if memur else "disabled")
        self.sozlesme_girdisi.configure(state="disabled" if memur else "normal")

    def listele(self):
        self.liste.delete(*self.liste.get_children())
        aranan = self.ara.get().strip().lower()
        for p in self.app.db.personeller(sadece_aktif=not self.pasif.get()):
            metin = f"{p.tc} {p.ad_soyad} {p.unvan} {p.birim}".lower()
            if aranan and aranan not in metin:
                continue
            self.liste.insert("", "end", iid=str(p.id), values=(p.tc, p.ad_soyad, p.unvan, p.birim, p.statu,
                                                                "Aktif" if p.aktif else "Pasif"))

    def secildi(self, _=None):
        sec = self.liste.selection()
        if not sec:
            return
        p = self.app.db.personel(int(sec[0]))
        self.secili_id = p.id
        for alan, v in self.degiskenler.items():
            deger = getattr(p, alan)
            v.set(deger if isinstance(v, tk.BooleanVar) else str(deger))
        self.statu_degisti()
        if p.aktif:
            self.aktif_btn.pack_forget()
        else:
            self.aktif_btn.pack(fill="x", pady=(6, 0))

    def temizle(self):
        self.secili_id = None
        self.liste.selection_remove(*self.liste.selection())
        for alan, v in self.degiskenler.items():
            if isinstance(v, tk.BooleanVar):
                v.set(False)
            elif alan in dict(self.METIN):
                v.set("")
            else:
                v.set("0")
        self.degiskenler["statu"].set("657")
        self.degiskenler["emeklilik"].set("5510")
        self.degiskenler["derece"].set("1")
        self.degiskenler["kademe"].set("1")
        self.aktif_btn.pack_forget()
        self.statu_degisti()

    def _formdan_personel(self) -> Personel:
        v = {a: d.get() for a, d in self.degiskenler.items()}
        try:
            tam = {a: int(v[a] or 0) for a in ("derece", "kademe", "ek_gosterge", "hizmet_yili",
                                                "yan_odeme_puani", "cocuk_0_6", "cocuk_6_ustu", "engellilik")}
            ondalik = {a: D(v[a] or 0) for a in ("ozel_hizmet_orani", "ek_odeme_orani", "sozlesme_ucreti",
                                                  "sendika_aidati", "devreden_matrah")}
        except Exception:
            raise ValueError("Sayısal alanlara yalnızca sayı girin (ondalık için virgül veya nokta).")
        aktif = True
        if self.secili_id:
            aktif = self.app.db.personel(self.secili_id).aktif
        return Personel(id=self.secili_id, tc=v["tc"].strip(), ad=v["ad"].strip(), soyad=v["soyad"].strip(),
                        unvan=v["unvan"].strip(), birim=v["birim"].strip(), statu=v["statu"],
                        iban=v["iban"].strip(), emeklilik=v["emeklilik"], es_yardimi=bool(v["es_yardimi"]),
                        aktif=aktif, **tam, **ondalik)

    @hata_goster
    def kaydet(self):
        p = self._formdan_personel()
        pid = self.app.db.personel_kaydet(p)
        self.listele()
        if self.liste.exists(str(pid)):
            self.liste.selection_set(str(pid))
            self.liste.see(str(pid))
        messagebox.showinfo(UYGULAMA_ADI, f"{p.ad_soyad} kaydedildi.")

    @hata_goster
    def sil(self):
        if not self.secili_id:
            return
        p = self.app.db.personel(self.secili_id)
        if messagebox.askyesno(UYGULAMA_ADI, f"{p.ad_soyad} silinsin mi?\n\nGeçmiş bordrosu olan personel "
                                             f"silinmez, pasife alınır."):
            self.app.db.personel_sil(p.id)
            self.temizle()
            self.listele()

    @hata_goster
    def aktif_yap(self):
        if self.secili_id:
            p = self.app.db.personel(self.secili_id)
            p.aktif = True
            self.app.db.personel_kaydet(p)
            self.listele()
            self.aktif_btn.pack_forget()

    def ek_kalemler(self):
        if not self.secili_id:
            messagebox.showinfo(UYGULAMA_ADI, "Önce listeden bir personel seçin.")
            return
        EkKalemPenceresi(self, self.app, self.app.db.personel(self.secili_id))

    @hata_goster
    def sablon(self):
        yol = filedialog.asksaveasfilename(title="Şablonu kaydet", initialfile="personel_sablonu.xlsx",
                                           defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if yol:
            iceaktar.sablon_olustur(yol)
            messagebox.showinfo(UYGULAMA_ADI, "Şablon kaydedildi. Örnek satırı silip kendi personelinizi girin.")

    @hata_goster
    def excelden_aktar(self):
        yol = filedialog.askopenfilename(title="Personel Excel dosyası", filetypes=[("Excel", "*.xlsx")])
        if not yol:
            return
        mevcut = {p.tc: p for p in self.app.db.personeller(sadece_aktif=False)}
        eklenen = guncellenen = 0
        hatalar = []
        for i, p in enumerate(iceaktar.personel_oku(yol), 2):
            if p.tc in mevcut:
                p.id = mevcut[p.tc].id
                p.aktif = mevcut[p.tc].aktif
            try:
                self.app.db.personel_kaydet(p)
                guncellenen += bool(p.tc in mevcut)
                eklenen += p.tc not in mevcut
            except ValueError as e:
                hatalar.append(f"Satır {i} ({p.ad_soyad or p.tc}): {e}")
        self.listele()
        mesaj = f"{eklenen} personel eklendi, {guncellenen} personel güncellendi."
        if hatalar:
            mesaj += "\n\nAktarılamayan satırlar:\n" + "\n".join(hatalar[:20])
            if len(hatalar) > 20:
                mesaj += f"\n... ve {len(hatalar) - 20} satır daha"
        messagebox.showinfo(UYGULAMA_ADI, mesaj)


class EkKalemPenceresi(tk.Toplevel):
    def __init__(self, ust, app: Uygulama, p: Personel):
        super().__init__(ust)
        self.app, self.p = app, p
        self.title(f"Ek Ödeme ve Kesintiler — {p.ad_soyad}")
        self.geometry("760x440")
        self.transient(ust.winfo_toplevel())

        sutunlar = ("donem", "tur", "ad", "tutar", "gv", "dv", "sgk")
        self.liste = ttk.Treeview(self, columns=sutunlar, show="headings", height=10)
        for s, b, w in zip(sutunlar, ("Dönem", "Tür", "Açıklama", "Tutar", "GV", "DV", "SGK"),
                           (80, 70, 250, 100, 40, 40, 40)):
            self.liste.heading(s, text=b)
            self.liste.column(s, width=w, anchor="e" if s == "tutar" else "w")
        self.liste.pack(fill="both", expand=True, padx=8, pady=8)

        f = ttk.LabelFrame(self, text="Yeni kalem", padding=6)
        f.pack(fill="x", padx=8)
        self.tur = tk.StringVar(value="Ödeme")
        self.ad = tk.StringVar()
        self.tutar = tk.StringVar()
        self.donem = tk.StringVar(value=date.today().strftime("%Y-%m"))
        self.surekli = tk.BooleanVar(value=False)
        self.gv, self.dv, self.sgk = tk.BooleanVar(value=True), tk.BooleanVar(value=True), tk.BooleanVar()
        ttk.Combobox(f, textvariable=self.tur, values=["Ödeme", "Kesinti"], state="readonly", width=8).grid(
            row=0, column=0)
        ttk.Label(f, text="Açıklama").grid(row=0, column=1, padx=(8, 2))
        ttk.Entry(f, textvariable=self.ad, width=28).grid(row=0, column=2)
        ttk.Label(f, text="Tutar").grid(row=0, column=3, padx=(8, 2))
        ttk.Entry(f, textvariable=self.tutar, width=12).grid(row=0, column=4)
        ttk.Label(f, text="Dönem").grid(row=0, column=5, padx=(8, 2))
        ttk.Entry(f, textvariable=self.donem, width=9).grid(row=0, column=6)
        ttk.Checkbutton(f, text="Her ay (sürekli)", variable=self.surekli).grid(row=1, column=0, columnspan=2,
                                                                                sticky="w")
        ttk.Checkbutton(f, text="Gelir vergisine tabi", variable=self.gv).grid(row=1, column=2, sticky="w")
        ttk.Checkbutton(f, text="Damga vergisine tabi", variable=self.dv).grid(row=1, column=3, columnspan=2,
                                                                               sticky="w")
        ttk.Checkbutton(f, text="SGK matrahına dahil", variable=self.sgk).grid(row=1, column=5, columnspan=2,
                                                                              sticky="w")
        ttk.Label(f, text="Vergi/SGK seçenekleri yalnız ödemeler için geçerlidir. Örnek kesintiler: icra, "
                          "nafaka, kefalet, lojman.", foreground="#555").grid(row=2, column=0, columnspan=7,
                                                                           sticky="w", pady=(4, 0))
        d = ttk.Frame(self)
        d.pack(fill="x", padx=8, pady=8)
        ttk.Button(d, text="Ekle", command=self.ekle).pack(side="left")
        ttk.Button(d, text="Seçileni Sil", command=self.sil).pack(side="left", padx=4)
        ttk.Button(d, text="Kapat", command=self.destroy).pack(side="right")
        self.listele()

    def listele(self):
        self.liste.delete(*self.liste.get_children())
        e = lambda b: "✓" if b else ""
        for k in self.app.db.ek_kalem_listesi(self.p.id):
            self.liste.insert("", "end", iid=str(k["id"]), values=(
                k["donem"] or "Her ay", "Ödeme" if k["tur"] == "odeme" else "Kesinti", k["ad"], tl(D(k["tutar"])),
                e(k["vergiye_tabi"]) if k["tur"] == "odeme" else "", e(k["damgaya_tabi"]) if k["tur"] == "odeme"
                else "", e(k["sgk_tabi"]) if k["tur"] == "odeme" else ""))

    @hata_goster
    def ekle(self):
        if not self.ad.get().strip():
            raise ValueError("Açıklama girin.")
        try:
            tutar = D(self.tutar.get())
        except Exception:
            raise ValueError("Tutar sayı olmalıdır.")
        if tutar <= 0:
            raise ValueError("Tutar sıfırdan büyük olmalıdır.")
        donem = None
        if not self.surekli.get():
            donem = self.donem.get().strip()
            donem_dogrula(donem)
        self.app.db.ek_kalem_ekle(self.p.id, donem, EkKalem(
            ad=self.ad.get().strip(), tutar=tutar, tur="odeme" if self.tur.get() == "Ödeme" else "kesinti",
            vergiye_tabi=self.gv.get(), damgaya_tabi=self.dv.get(), sgk_tabi=self.sgk.get()))
        self.ad.set("")
        self.tutar.set("")
        self.listele()

    def sil(self):
        for iid in self.liste.selection():
            self.app.db.ek_kalem_sil(int(iid))
        self.listele()


# =========================================================================== Bordro
class BordroSekmesi(ttk.Frame):
    def __init__(self, ust, app: Uygulama):
        super().__init__(ust, padding=6)
        self.app = app
        self.sonuclar = []
        self.kayitli = False

        ust_cubuk = ttk.Frame(self)
        ust_cubuk.pack(fill="x")
        bugun = date.today()
        ttk.Label(ust_cubuk, text="Dönem:").pack(side="left")
        self.yil = tk.StringVar(value=str(bugun.year))
        ttk.Spinbox(ust_cubuk, from_=2020, to=2100, textvariable=self.yil, width=6).pack(side="left", padx=4)
        self.ay = tk.StringVar(value=AYLAR[bugun.month - 1])
        ttk.Combobox(ust_cubuk, textvariable=self.ay, values=AYLAR, state="readonly", width=9).pack(side="left")
        ttk.Button(ust_cubuk, text="Hesapla", command=self.hesapla).pack(side="left", padx=(10, 2))
        ttk.Button(ust_cubuk, text="Kayıtlı Bordroyu Aç", command=self.kayitli_ac).pack(side="left", padx=2)
        ttk.Button(ust_cubuk, text="Bordroyu Kaydet", command=self.kaydet).pack(side="left", padx=2)
        self.kilit_btn = ttk.Button(ust_cubuk, text="Dönemi Kilitle", command=self.kilit)
        self.kilit_btn.pack(side="left", padx=2)
        self.durum = ttk.Label(ust_cubuk, text="", foreground="#1d4ed8")
        self.durum.pack(side="left", padx=10)

        self.uyari = ttk.Label(self, style="Uyari.TLabel", wraplength=1100)
        self.uyari.pack(fill="x", pady=(6, 0))

        sutunlar = ("tc", "adsoyad", "birim", "statu", "brut", "kesinti", "net")
        orta = ttk.Frame(self)
        orta.pack(fill="both", expand=True, pady=6)
        self.liste = ttk.Treeview(orta, columns=sutunlar, show="headings")
        for s, b, w in zip(sutunlar, ("T.C. No", "Ad Soyad", "Birim", "Statü", "Brüt", "Kesinti", "Net"),
                           (100, 180, 160, 55, 110, 110, 110)):
            self.liste.heading(s, text=b)
            self.liste.column(s, width=w, anchor="e" if s in ("brut", "kesinti", "net") else "w")
        kay = ttk.Scrollbar(orta, orient="vertical", command=self.liste.yview)
        self.liste.configure(yscrollcommand=kay.set)
        self.liste.pack(side="left", fill="both", expand=True)
        kay.pack(side="left", fill="y")
        self.liste.bind("<Double-1>", self.detay)

        self.toplam = ttk.Label(self, style="Toplam.TLabel")
        self.toplam.pack(fill="x")

        cikti = ttk.LabelFrame(self, text="Çıktılar (listede görünen bordro üzerinden)", padding=6)
        cikti.pack(fill="x", pady=(6, 0))
        for metin, komut in [("Kişi Bordrosu PDF (seçili)", lambda: self.kisi_pdf(True)),
                             ("Kişi Bordroları PDF (tümü)", lambda: self.kisi_pdf(False)),
                             ("Toplu Bordro PDF", self.toplu_pdf), ("İcmal PDF", self.icmal_pdf),
                             ("Toplu Bordro + İcmal Excel", self.excel),
                             ("Banka Listesi Excel", self.banka_excel), ("Banka Listesi CSV", self.banka_csv)]:
            ttk.Button(cikti, text=metin, command=komut).pack(side="left", padx=2)
        self.uyari_guncelle()

    @property
    def donem(self) -> str:
        return f"{int(self.yil.get()):04d}-{AYLAR.index(self.ay.get()) + 1:02d}"

    def uyari_guncelle(self):
        if self.app.db.ayar("parametreler_dogrulandi") != "1":
            self.uyari.configure(text="⚠ Katsayı ve oranlar henüz doğrulanmadı. 'Parametreler ve Ayarlar' "
                                      "sekmesinde değerleri Hazine ve Maliye Bakanlığı genelgesiyle "
                                      "karşılaştırıp onay kutusunu işaretleyin.")
        else:
            self.uyari.configure(text="")

    def _goster(self, sonuclar, kayitli: bool):
        self.sonuclar, self.kayitli = sonuclar, kayitli
        self.liste.delete(*self.liste.get_children())
        for i, s in enumerate(sonuclar):
            p = s.personel
            self.liste.insert("", "end", iid=str(i), values=(p.tc, p.ad_soyad, p.birim, p.statu, tl(s.brut),
                                                             tl(s.kesinti_toplami), tl(s.net)))
        top = lambda f: tl(sum((f(s) for s in sonuclar), D(0)))
        self.toplam.configure(text=f"{len(sonuclar)} personel   |   Brüt: {top(lambda s: s.brut)}   |   "
                                   f"Kesinti: {top(lambda s: s.kesinti_toplami)}   |   "
                                   f"Net: {top(lambda s: s.net)}   |   "
                                   f"Kurum payları: {top(lambda s: s.isveren_toplami)}")
        self._durum_guncelle()

    def _durum_guncelle(self):
        if not self.sonuclar:
            self.durum.configure(text="")
            return
        d = self.sonuclar[0].donem
        kilitli = self.app.db.donem_kilitli(d)
        durum = "KİLİTLİ" if kilitli else ("Kayıtlı" if self.kayitli else "Önizleme — henüz kaydedilmedi")
        self.durum.configure(text=f"{donem_adi(d)}: {durum}")
        self.kilit_btn.configure(text="Kilidi Aç" if kilitli else "Dönemi Kilitle")

    @hata_goster
    def hesapla(self):
        d = self.donem
        if self.app.db.donem_kilitli(d):
            if messagebox.askyesno(UYGULAMA_ADI, f"{donem_adi(d)} kilitli. Kayıtlı bordro açılsın mı?"):
                self.kayitli_ac()
            return
        sonuclar = self.app.db.donem_hesapla(d)
        if not sonuclar:
            messagebox.showinfo(UYGULAMA_ADI, "Aktif personel yok. Önce Personel sekmesinden personel ekleyin.")
        self._goster(sonuclar, kayitli=False)

    @hata_goster
    def kayitli_ac(self):
        sonuclar = self.app.db.kayitli_bordro(self.donem)
        if not sonuclar:
            kayitlar = self.app.db.kayitli_donemler()
            raise ValueError(f"{donem_adi(self.donem)} için kayıtlı bordro yok."
                             + (f"\nKayıtlı dönemler: {', '.join(kayitlar)}" if kayitlar else ""))
        self._goster(sonuclar, kayitli=True)

    @hata_goster
    def kaydet(self):
        if not self.sonuclar:
            raise ValueError("Önce 'Hesapla' ile bordroyu oluşturun.")
        d = self.sonuclar[0].donem
        if self.kayitli:
            raise ValueError("Bu bordro zaten kayıtlı. Değişiklik yaptıysanız önce yeniden hesaplayın.")
        if self.app.db.kayitli_bordro(d) and not messagebox.askyesno(
                UYGULAMA_ADI, f"{donem_adi(d)} için kayıtlı bordro var. Üzerine yazılsın mı?"):
            return
        self.app.db.bordro_kaydet(d, self.sonuclar)
        self.kayitli = True
        self._durum_guncelle()
        messagebox.showinfo(UYGULAMA_ADI, f"{donem_adi(d)} bordrosu kaydedildi.\n\nSonraki ayların kümülatif "
                                          f"gelir vergisi matrahı bu kayıttan hesaplanır.")

    @hata_goster
    def kilit(self):
        if not self.sonuclar:
            raise ValueError("Önce bir dönem açın.")
        d = self.sonuclar[0].donem
        if self.app.db.donem_kilitli(d):
            if messagebox.askyesno(UYGULAMA_ADI, f"{donem_adi(d)} kilidi açılsın mı?"):
                self.app.db.donem_kilitle(d, False)
        else:
            if not self.kayitli:
                raise ValueError("Kilitlemeden önce bordroyu kaydedin.")
            self.app.db.donem_kilitle(d, True)
        self._durum_guncelle()

    def detay(self, _=None):
        sec = self.liste.selection()
        if sec:
            DetayPenceresi(self, self.sonuclar[int(sec[0])])

    # --- çıktılar ---
    def _hazir(self):
        if not self.sonuclar:
            raise ValueError("Önce bordroyu hesaplayın veya kayıtlı bordroyu açın.")
        if not self.kayitli:
            return messagebox.askyesno(UYGULAMA_ADI, "Bu bordro henüz kaydedilmedi (önizleme).\n"
                                                     "Yine de çıktı alınsın mı?")
        return True

    def _dosya(self, ad, uzanti, tur):
        yol = filedialog.asksaveasfilename(initialfile=f"{ad}_{self.sonuclar[0].donem}{uzanti}",
                                           defaultextension=uzanti, filetypes=[(tur, f"*{uzanti}")])
        return yol

    def _kurum(self):
        return self.app.db.ayar("kurum_adi"), self.app.db.ayar("birim_adi")

    def _bitti(self, yol):
        if messagebox.askyesno(UYGULAMA_ADI, f"Dosya oluşturuldu:\n{yol}\n\nAçılsın mı?"):
            _klasor_ac(yol)

    @hata_goster
    def kisi_pdf(self, secili: bool):
        if not self._hazir():
            return
        liste = self.sonuclar
        if secili:
            sec = self.liste.selection()
            if not sec:
                raise ValueError("Listeden bir personel seçin.")
            liste = [self.sonuclar[int(sec[0])]]
            ad = f"bordro_{liste[0].personel.ad_soyad.replace(' ', '_')}"
        else:
            ad = "kisi_bordrolari"
        yol = self._dosya(ad, ".pdf", "PDF")
        if yol:
            raporlar.kisi_bordrosu_pdf(liste, yol, *self._kurum())
            self._bitti(yol)

    @hata_goster
    def toplu_pdf(self):
        if self._hazir() and (yol := self._dosya("toplu_bordro", ".pdf", "PDF")):
            raporlar.toplu_bordro_pdf(self.sonuclar, yol, *self._kurum())
            self._bitti(yol)

    @hata_goster
    def icmal_pdf(self):
        if self._hazir() and (yol := self._dosya("icmal", ".pdf", "PDF")):
            raporlar.icmal_pdf(self.sonuclar, yol, *self._kurum())
            self._bitti(yol)

    @hata_goster
    def excel(self):
        if self._hazir() and (yol := self._dosya("toplu_bordro", ".xlsx", "Excel")):
            raporlar.toplu_bordro_excel(self.sonuclar, yol, self._kurum()[0])
            self._bitti(yol)

    def _iban_kontrol(self):
        eksik = raporlar.eksik_iban(self.sonuclar)
        if eksik:
            return messagebox.askyesno(UYGULAMA_ADI, "IBAN'ı girilmemiş personel var:\n" + "\n".join(eksik[:15])
                                       + "\n\nYine de liste oluşturulsun mu?")
        return True

    @hata_goster
    def banka_excel(self):
        if self._hazir() and self._iban_kontrol() and (yol := self._dosya("banka_listesi", ".xlsx", "Excel")):
            raporlar.banka_listesi_excel(self.sonuclar, yol, self._kurum()[0])
            self._bitti(yol)

    @hata_goster
    def banka_csv(self):
        if self._hazir() and self._iban_kontrol() and (yol := self._dosya("banka_listesi", ".csv", "CSV")):
            raporlar.banka_listesi_csv(self.sonuclar, yol)
            self._bitti(yol)


class DetayPenceresi(tk.Toplevel):
    def __init__(self, ust, s):
        super().__init__(ust)
        self.title(f"{s.personel.ad_soyad} — {donem_adi(s.donem)}")
        self.geometry("620x560")
        t = ttk.Treeview(self, columns=("ad", "tutar"), show="tree headings")
        t.heading("ad", text="Kalem")
        t.heading("tutar", text="Tutar")
        t.column("#0", width=110)
        t.column("ad", width=320)
        t.column("tutar", width=130, anchor="e")
        t.pack(fill="both", expand=True, padx=8, pady=8)
        for baslik, liste, toplam in (("Ödemeler", s.odemeler, s.brut), ("Kesintiler", s.kesintiler,
                                                                         s.kesinti_toplami),
                                      ("Kurum Payları", s.isveren, s.isveren_toplami)):
            ana = t.insert("", "end", text=baslik, values=("Toplam", tl(toplam)), open=True)
            for x in liste:
                t.insert(ana, "end", values=(x.ad, tl(x.tutar)))
        t.insert("", "end", text="NET", values=("Net ödenecek", tl(s.net)))
        t.insert("", "end", text="Matrahlar", values=("Gelir vergisi matrahı (bu ay)", tl(s.gv_matrahi)))
        t.insert("", "end", text="", values=("Kümülatif gelir vergisi matrahı", tl(s.kumulatif_matrah)))
        t.insert("", "end", text="", values=("SGK/GSS prim matrahı", tl(s.sgk_matrahi)))
        ttk.Button(self, text="Kapat", command=self.destroy).pack(pady=(0, 8))


# =========================================================================== Parametreler
class ParametreSekmesi(ttk.Frame):
    def __init__(self, ust, app: Uygulama):
        super().__init__(ust, padding=6)
        self.app = app
        sol = ttk.Frame(self)
        sol.pack(side="left", fill="both", expand=True)
        sag = ttk.Frame(self, padding=(10, 0, 0, 0))
        sag.pack(side="left", fill="y")

        # Kurum
        kf = ttk.LabelFrame(sol, text="Kurum Bilgileri (bordro başlığında yazar)", padding=6)
        kf.pack(fill="x")
        kf.columnconfigure(1, weight=1)
        self.kurum = tk.StringVar(value=app.db.ayar("kurum_adi"))
        self.birim = tk.StringVar(value=app.db.ayar("birim_adi"))
        _form_satiri(kf, 0, "Kurum adı", ttk.Entry(kf, textvariable=self.kurum))
        _form_satiri(kf, 1, "Birim / hastane adı", ttk.Entry(kf, textvariable=self.birim))
        ttk.Button(kf, text="Kaydet", command=self.kurum_kaydet).grid(row=2, column=1, sticky="e", pady=(4, 0))

        # Katsayılar
        pf = ttk.LabelFrame(sol, text="Katsayı ve Oranlar", padding=6)
        pf.pack(fill="both", expand=True, pady=6)
        ust_c = ttk.Frame(pf)
        ust_c.pack(fill="x")
        ttk.Label(ust_c, text="Geçerlilik başlangıcı (YYYY-AA):").pack(side="left")
        self.gecerlilik = tk.StringVar()
        self.gecerlilik_cb = ttk.Combobox(ust_c, textvariable=self.gecerlilik, state="readonly", width=10)
        self.gecerlilik_cb.pack(side="left", padx=4)
        self.gecerlilik_cb.bind("<<ComboboxSelected>>", lambda e: self.parametre_yukle())
        ttk.Button(ust_c, text="Kaydet", command=self.parametre_kaydet).pack(side="left", padx=2)
        ttk.Button(ust_c, text="Yeni Dönem Olarak Kopyala...", command=self.yeni_donem).pack(side="left", padx=2)
        ttk.Button(ust_c, text="Sil", command=self.parametre_sil).pack(side="left", padx=2)

        kap = ttk.Frame(pf)
        kap.pack(fill="both", expand=True, pady=(6, 0))
        tuval = tk.Canvas(kap, highlightthickness=0)
        kay = ttk.Scrollbar(kap, orient="vertical", command=tuval.yview)
        ic = ttk.Frame(tuval)
        ic.bind("<Configure>", lambda e: tuval.configure(scrollregion=tuval.bbox("all")))
        tuval.create_window((0, 0), window=ic, anchor="nw")
        tuval.configure(yscrollcommand=kay.set)
        tuval.pack(side="left", fill="both", expand=True)
        kay.pack(side="left", fill="y")
        self.param_deg: dict[str, tk.StringVar] = {}
        for r, (anahtar, (aciklama, _)) in enumerate(PARAMETRE_TANIMLARI.items()):
            self.param_deg[anahtar] = tk.StringVar()
            ttk.Label(ic, text=aciklama).grid(row=r, column=0, sticky="w", padx=(0, 8), pady=1)
            ttk.Entry(ic, textvariable=self.param_deg[anahtar], width=14).grid(row=r, column=1, pady=1)

        self.dogrulandi = tk.BooleanVar(value=app.db.ayar("parametreler_dogrulandi") == "1")
        ttk.Checkbutton(sol, text="Katsayı, oran ve vergi dilimlerini resmi genelge/tebliğ ile karşılaştırdım; "
                                  "doğrudur.", variable=self.dogrulandi, command=self.dogrulama).pack(anchor="w")

        # Vergi dilimleri
        vf = ttk.LabelFrame(sag, text="Gelir Vergisi Tarifesi (ücret)", padding=6)
        vf.pack(fill="x")
        ust_v = ttk.Frame(vf)
        ust_v.grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(ust_v, text="Yıl:").pack(side="left")
        self.vergi_yili = tk.StringVar()
        self.vergi_cb = ttk.Combobox(ust_v, textvariable=self.vergi_yili, width=6)
        self.vergi_cb.pack(side="left", padx=4)
        self.vergi_cb.bind("<<ComboboxSelected>>", lambda e: self.dilim_yukle())
        ttk.Label(vf, text="Kümülatif üst sınır (TL)").grid(row=1, column=1)
        ttk.Label(vf, text="Oran %").grid(row=1, column=2)
        self.dilim_deg = []
        for i in range(6):
            u, o = tk.StringVar(), tk.StringVar()
            ttk.Label(vf, text=f"{i + 1}. dilim").grid(row=i + 2, column=0, sticky="w")
            ttk.Entry(vf, textvariable=u, width=14).grid(row=i + 2, column=1, padx=2, pady=1)
            ttk.Entry(vf, textvariable=o, width=6).grid(row=i + 2, column=2, pady=1)
            self.dilim_deg.append((u, o))
        ttk.Label(vf, text="Son dilimin üst sınırını boş bırakın.", foreground="#555").grid(
            row=8, column=0, columnspan=3, sticky="w")
        ttk.Button(vf, text="Tarifeyi Kaydet", command=self.dilim_kaydet).grid(row=9, column=0, columnspan=3,
                                                                              sticky="e", pady=(4, 0))

        # Gösterge tablosu
        gf = ttk.LabelFrame(sag, text="Gösterge Tablosu (657 md. 43)", padding=6)
        gf.pack(fill="both", expand=True, pady=6)
        self.gosterge_liste = ttk.Treeview(gf, columns=("d", "k", "g"), show="headings", height=8)
        for s, b in zip(("d", "k", "g"), ("Derece", "Kademe", "Gösterge")):
            self.gosterge_liste.heading(s, text=b)
            self.gosterge_liste.column(s, width=70, anchor="center")
        self.gosterge_liste.pack(fill="both", expand=True)
        self.gosterge_liste.bind("<<TreeviewSelect>>", self.gosterge_secildi)
        gd = ttk.Frame(gf)
        gd.pack(fill="x", pady=(4, 0))
        self.g_d, self.g_k, self.g_g = tk.StringVar(), tk.StringVar(), tk.StringVar()
        for etiket, v in (("D", self.g_d), ("K", self.g_k), ("G", self.g_g)):
            ttk.Label(gd, text=etiket).pack(side="left")
            ttk.Entry(gd, textvariable=v, width=6).pack(side="left", padx=(1, 4))
        ttk.Button(gd, text="Kaydet", command=self.gosterge_kaydet).pack(side="left")

        self.yenile()

    def yenile(self):
        donemler = self.app.db.parametre_donemleri()
        self.gecerlilik_cb.configure(values=donemler)
        if donemler and self.gecerlilik.get() not in donemler:
            self.gecerlilik.set(donemler[0])
        self.parametre_yukle()
        yillar = [str(y) for y in self.app.db.dilim_yillari()]
        self.vergi_cb.configure(values=yillar)
        if yillar and not self.vergi_yili.get():
            self.vergi_yili.set(yillar[0])
        self.dilim_yukle()
        self.gosterge_liste.delete(*self.gosterge_liste.get_children())
        for d, k, g in self.app.db.gostergeler():
            self.gosterge_liste.insert("", "end", values=(d, k, g))

    def parametre_yukle(self):
        if not self.gecerlilik.get():
            return
        degerler = self.app.db.parametre_seti(self.gecerlilik.get())
        for anahtar, v in self.param_deg.items():
            v.set(degerler.get(anahtar, PARAMETRE_TANIMLARI[anahtar][1]))

    @hata_goster
    def kurum_kaydet(self):
        self.app.db.ayar_yaz("kurum_adi", self.kurum.get().strip())
        self.app.db.ayar_yaz("birim_adi", self.birim.get().strip())
        messagebox.showinfo(UYGULAMA_ADI, "Kurum bilgileri kaydedildi.")

    def _param_degerleri(self) -> dict:
        degerler = {}
        for anahtar, v in self.param_deg.items():
            try:
                degerler[anahtar] = D(v.get().strip() or "0")
            except Exception:
                raise ValueError(f"'{PARAMETRE_TANIMLARI[anahtar][0]}' sayı olmalıdır.")
        return degerler

    @hata_goster
    def parametre_kaydet(self):
        if not self.gecerlilik.get():
            raise ValueError("Önce bir geçerlilik dönemi oluşturun.")
        self.app.db.parametre_kaydet(self.gecerlilik.get(), self._param_degerleri())
        self._dogrulamayi_kaldir()
        messagebox.showinfo(UYGULAMA_ADI, f"{self.gecerlilik.get()} parametreleri kaydedildi.")

    @hata_goster
    def yeni_donem(self):
        d = simpledialog.askstring(UYGULAMA_ADI, "Yeni parametrelerin geçerli olacağı ilk ay (YYYY-AA):\n"
                                                 "Örn. Ocak 2027 katsayıları için 2027-01", parent=self)
        if not d:
            return
        d = d.strip()
        donem_dogrula(d)
        if d in self.app.db.parametre_donemleri():
            raise ValueError(f"{d} için parametre seti zaten var.")
        self.app.db.parametre_kaydet(d, self._param_degerleri())
        self.gecerlilik.set(d)
        self.yenile()
        self._dogrulamayi_kaldir()
        messagebox.showinfo(UYGULAMA_ADI, f"{d} seti mevcut değerlerden kopyalandı. Yeni katsayıları girip "
                                          f"'Kaydet'e basın.")

    @hata_goster
    def parametre_sil(self):
        d = self.gecerlilik.get()
        if len(self.app.db.parametre_donemleri()) <= 1:
            raise ValueError("Son parametre seti silinemez.")
        if messagebox.askyesno(UYGULAMA_ADI, f"{d} parametre seti silinsin mi?"):
            self.app.db.parametre_sil(d)
            self.gecerlilik.set("")
            self.yenile()

    def dilim_yukle(self):
        try:
            yil = int(self.vergi_yili.get())
            dilimler = self.app.db.dilimler(yil) if str(yil) in self.vergi_cb["values"] else []
        except ValueError:
            dilimler = []
        for i, (u, o) in enumerate(self.dilim_deg):
            if i < len(dilimler):
                ust, oran = dilimler[i]
                u.set("" if ust is None else str(ust))
                o.set(str(oran))
            else:
                u.set("")
                o.set("")

    @hata_goster
    def dilim_kaydet(self):
        try:
            yil = int(self.vergi_yili.get())
        except ValueError:
            raise ValueError("Yıl girin (örn. 2027).")
        dilimler = []
        for u, o in self.dilim_deg:
            if not o.get().strip():
                continue
            try:
                dilimler.append((D(u.get()) if u.get().strip() else None, D(o.get())))
            except Exception:
                raise ValueError("Dilim sınırları ve oranlar sayı olmalıdır.")
        if not dilimler or dilimler[-1][0] is not None:
            raise ValueError("Son dilimin üst sınırı boş olmalıdır.")
        if any(ust is None for ust, _ in dilimler[:-1]):
            raise ValueError("Yalnızca son dilimin üst sınırı boş olabilir.")
        sinirlar = [ust for ust, _ in dilimler[:-1]]
        if sinirlar != sorted(sinirlar):
            raise ValueError("Dilim üst sınırları küçükten büyüğe sıralı olmalıdır.")
        self.app.db.dilim_kaydet(yil, dilimler)
        self._dogrulamayi_kaldir()
        self.yenile()
        messagebox.showinfo(UYGULAMA_ADI, f"{yil} gelir vergisi tarifesi kaydedildi.")

    def gosterge_secildi(self, _=None):
        sec = self.gosterge_liste.selection()
        if sec:
            d, k, g = self.gosterge_liste.item(sec[0], "values")
            self.g_d.set(d)
            self.g_k.set(k)
            self.g_g.set(g)

    @hata_goster
    def gosterge_kaydet(self):
        try:
            d, k, g = int(self.g_d.get()), int(self.g_k.get()), int(self.g_g.get())
        except ValueError:
            raise ValueError("Derece, kademe ve gösterge tam sayı olmalıdır.")
        self.app.db.gosterge_kaydet(d, k, g)
        self.yenile()

    def dogrulama(self):
        self.app.db.ayar_yaz("parametreler_dogrulandi", "1" if self.dogrulandi.get() else "0")
        self.app.bordro_sekmesi.uyari_guncelle()

    def _dogrulamayi_kaldir(self):
        """Parametre değişince onay kutusu yeniden işaretlenmelidir."""
        self.dogrulandi.set(False)
        self.dogrulama()


def calistir():
    """Açılışta oluşan hatayı hata.log'a yazar ve gösterir; .exe penceresiz olduğu için
    aksi halde program sessizce kapanırdı."""
    try:
        Uygulama().mainloop()
    except Exception:
        import traceback
        yol = os.path.join(veri_klasoru(), "hata.log")
        with open(yol, "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.now():%Y-%m-%d %H:%M} ---\n{traceback.format_exc()}")
        kok = tk.Tk()
        kok.withdraw()
        messagebox.showerror(UYGULAMA_ADI, f"Program açılamadı.\nAyrıntılar: {yol}\n\n"
                                           f"{traceback.format_exc(limit=1)}")
        kok.destroy()
