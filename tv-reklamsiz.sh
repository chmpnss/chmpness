#!/usr/bin/env bash
# tv-reklamsiz.sh — Android TV / Google TV için reklam temizleme ve sade arayüz aracı.
# Bilgisayardan ADB ile TV'ye bağlanır. Hiçbir şeyi silmez: paketler yalnızca
# kullanıcı için devre dışı bırakılır ve "geri-al" komutuyla eski haline döner.

set -euo pipefail

DIZIN="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LISTELER="$DIZIN/listeler"
KAYIT="$DIZIN/.kapatilanlar"          # bu araçla kapatılan paketler (geri alma için)
ADB="${ADB:-adb}"
DNS_SUNUCU="${DNS_SUNUCU:-dns.adguard-dns.com}"

# Önerilen reklamsız başlatıcı (Play Store'da ücretsiz, reklamsız).
BASLATICI_PAKET="com.spocky.projengmenu"
BASLATICI_AD="Projectivy Launcher"

# ---------- görünüm ----------
if [[ -t 1 ]]; then
  K=$'\e[1;31m' Y=$'\e[1;32m' S=$'\e[1;33m' M=$'\e[1;36m' G=$'\e[2m' B=$'\e[1m' N=$'\e[0m'
else
  K='' Y='' S='' M='' G='' B='' N=''
fi
bilgi()  { printf '%s›%s %s\n' "$M" "$N" "$*"; }
tamam()  { printf '%s✔%s %s\n' "$Y" "$N" "$*"; }
uyari()  { printf '%s!%s %s\n' "$S" "$N" "$*"; }
hata()   { printf '%s✖%s %s\n' "$K" "$N" "$*" >&2; }
baslik() { printf '\n%s━━ %s %s\n' "$B" "$*" "$N"; }
onay()   { local c; read -r -p "$1 [e/H] " c; [[ "$c" =~ ^[eEyY] ]]; }

logo() {
  printf '%s' "$M"
  cat <<'EOF'
   ╔══════════════════════════════════════╗
   ║   📺  TV REKLAMSIZ  ·  sade arayüz    ║
   ╚══════════════════════════════════════╝
EOF
  printf '%s' "$N"
}

# ---------- ADB yardımcıları ----------
adb_var_mi() {
  command -v "$ADB" >/dev/null 2>&1 && return
  hata "adb bulunamadı. Kurulum: https://developer.android.com/tools/releases/platform-tools"
  exit 1
}

kabuk() { "$ADB" shell "$@" | tr -d '\r'; }

cihaz_kontrol() {
  adb_var_mi
  if ! "$ADB" get-state >/dev/null 2>&1; then
    hata "Bağlı TV yok. Önce: $0 baglan <TV_IP_ADRESI>"
    exit 1
  fi
}

kurulu_mu() { kabuk pm list packages "$1" | grep -qx "package:$1"; }

# Liste dosyasındaki paket adlarını yazdırır (yorumları atlar).
liste_oku() { sed -e 's/#.*//' -e 's/[[:space:]]*$//' -e '/^[[:space:]]*$/d' "$1" | awk '{print $1}'; }

kayda_ekle() { grep -qx "$1" "$KAYIT" 2>/dev/null || echo "$1" >>"$KAYIT"; }

paket_kapat() {
  local p="$1"
  if ! kurulu_mu "$p"; then
    printf '  %s– %s (yüklü değil)%s\n' "$G" "$p" "$N"
    return
  fi
  if kabuk pm disable-user --user 0 "$p" | grep -q 'disabled'; then
    kayda_ekle "$p"
    printf '  %s✔%s %s\n' "$Y" "$N" "$p"
  else
    printf '  %s✖%s %s (kapatılamadı)\n' "$K" "$N" "$p"
  fi
}

# ---------- komutlar ----------
cmd_baglan() {
  adb_var_mi
  local ip="${1:-}"
  [[ -n "$ip" ]] || { cmd_bul; return; }
  [[ "$ip" == *:* ]] || ip="$ip:5555"
  bilgi "$ip adresine bağlanılıyor… TV'de çıkan izin penceresini onaylayın."
  "$ADB" connect "$ip"
  "$ADB" wait-for-device
  tamam "Bağlandı: $(kabuk getprop ro.product.manufacturer) $(kabuk getprop ro.product.model)" \
        "(Android $(kabuk getprop ro.build.version.release))"
}

# Bilgisayarın yerel ağının ilk üç hanesini bulur (ör. 192.168.1).
yerel_ag() {
  local ip=""
  if command -v ip >/dev/null 2>&1; then
    ip="$(ip -4 -o addr show scope global 2>/dev/null | awk '{sub(/\/.*/, "", $4); print $4; exit}')"
  fi
  if [[ -z "$ip" ]] && command -v ipconfig >/dev/null 2>&1; then
    ip="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"   # macOS
    [[ -n "$ip" ]] || ip="$(ipconfig 2>/dev/null | grep -aE 'IPv4' | grep -oE '([0-9]+\.){3}[0-9]+' | head -n1 || true)"  # Windows
  fi
  [[ -n "$ip" ]] && echo "${ip%.*}"
}

# 1 saniyelik zaman aşımıyla TCP portu açık mı?
port_acik() {
  bash -c "exec 3<>/dev/tcp/$1/$2" 2>/dev/null &
  local p=$!
  ( sleep 1; kill "$p" 2>/dev/null ) &
  local k=$!
  wait "$p" 2>/dev/null; local r=$?
  kill "$k" 2>/dev/null || true
  return "$r"
}

# Google Cast cihazının adını okur (yalnızca destekleyen modellerde).
cast_adi() {
  command -v curl >/dev/null 2>&1 || return 0
  curl -s -m 2 "http://$1:8008/setup/eureka_info?params=name" 2>/dev/null \
    | grep -o '"name":"[^"]*"' | head -n1 | cut -d'"' -f4 || true
}

cmd_bul() {
  adb_var_mi
  local ag="${1:-$(yerel_ag || true)}"
  ag="${ag%.}"
  [[ -n "$ag" ]] || read -r -p "Ağınızın ilk üç hanesi (ör. 192.168.1): " ag
  baslik "$ag.0/24 ağında TV aranıyor"

  # Android 11+ "Kablosuz hata ayıklama" cihazları mDNS ile kendini duyurur.
  "$ADB" mdns services 2>/dev/null | grep -E '_adb' | sed 's/^/  mdns: /' || true

  local gecici; gecici="$(mktemp -d)"
  local i
  for i in $(seq 1 254); do
    { port_acik "$ag.$i" 5555 && echo "$ag.$i" >>"$gecici/adb"; } &
    { port_acik "$ag.$i" 8009 && echo "$ag.$i" >>"$gecici/cast"; } &
    (( i % 64 == 0 )) && wait
  done
  wait

  local adbler castlar
  adbler="$(sort -t. -k4 -n "$gecici/adb" 2>/dev/null || true)"
  castlar="$(sort -t. -k4 -n "$gecici/cast" 2>/dev/null || true)"
  rm -rf "$gecici"

  if [[ -z "$adbler$castlar" ]]; then
    uyari "TV bulunamadı. TV açık ve aynı Wi‑Fi'da mı? Ağ hata ayıklaması açık mı?"
    return 1
  fi

  local ip ad
  for ip in $(printf '%s\n%s\n' "$adbler" "$castlar" | sort -u -t. -k4 -n); do
    [[ -n "$ip" ]] || continue
    ad="$(cast_adi "$ip")"
    if grep -qx "$ip" <<<"$adbler"; then
      printf '  %s📺 %-15s%s %s  %sADB açık ✔%s\n' "$B" "$ip" "$N" "${ad:-Android cihaz}" "$Y" "$N"
    else
      printf '  %s📺 %-15s%s %s  %sADB kapalı (Geliştirici seçeneklerinden açın)%s\n' "$B" "$ip" "$N" "${ad:-Cast cihazı}" "$S" "$N"
    fi
  done

  local sayi; sayi="$(grep -c . <<<"$adbler" || true)"
  if (( sayi == 1 )) && onay "$adbler adresine bağlanılsın mı?"; then
    cmd_baglan "$adbler"
  elif (( sayi > 1 )); then
    bilgi "Bağlanmak için: $0 baglan <ip>"
  fi
}

cmd_tara() {
  cihaz_kontrol
  baslik "Reklam / analiz şüphelisi paketler"
  local bulunan
  bulunan="$(kabuk pm list packages | sed 's/^package://' \
    | grep -Ei 'ad(s|vert)|analytic|recommend|promo|partner|sponsor|tracking|telemetry|feedback' \
    | sort || true)"
  if [[ -z "$bulunan" ]]; then
    tamam "Şüpheli paket bulunamadı."
  else
    printf '%s\n' "$bulunan" | sed 's/^/  • /'
    printf '\n%sBunlar yalnızca isim eşleşmesidir; kapatmadan önce ne olduklarını kontrol edin.%s\n' "$G" "$N"
    printf '%sTek paket kapatmak için: %s kapat <paket>%s\n' "$G" "$0" "$N"
  fi
}

cmd_reklam() {
  cihaz_kontrol
  baslik "Reklam ve öneri servisleri kapatılıyor"
  local dosya
  for dosya in "$LISTELER"/google-tv.txt "$LISTELER"/xiaomi.txt; do
    printf '%s%s%s\n' "$B" "$(basename "$dosya" .txt)" "$N"
    while read -r p; do paket_kapat "$p"; done < <(liste_oku "$dosya")
  done
}

cmd_kapat() {
  cihaz_kontrol
  [[ $# -gt 0 ]] || { hata "Kullanım: $0 kapat <paket> [paket…]"; exit 1; }
  local p; for p in "$@"; do paket_kapat "$p"; done
}

cmd_dns() {
  cihaz_kontrol
  baslik "Reklam engelleyen Özel DNS"
  local surum; surum="$(kabuk getprop ro.build.version.sdk)"
  if (( surum < 28 )); then
    uyari "Özel DNS Android 9 ve üstünde çalışır (bu cihaz API $surum). Atlanıyor."
    return
  fi
  kabuk settings put global private_dns_mode hostname
  kabuk settings put global private_dns_specifier "$DNS_SUNUCU"
  tamam "Özel DNS: $DNS_SUNUCU  (uygulama içi reklamların çoğunu engeller)"
  printf '%sNot: YouTube reklamları DNS ile engellenemez; bunun için SmartTube gibi bir istemci gerekir.%s\n' "$G" "$N"
}

cmd_hiz() {
  cihaz_kontrol
  baslik "Arayüz hızlandırma"
  local a
  for a in window_animation_scale transition_animation_scale animator_duration_scale; do
    kabuk settings put global "$a" 0.5
  done
  tamam "Animasyonlar 0.5x — menüler daha çevik açılır."
}

cmd_baslatici() {
  cihaz_kontrol
  baslik "Sade ve reklamsız ana ekran"
  local apk="${1:-}"
  if [[ -n "$apk" ]]; then
    [[ -f "$apk" ]] || { hata "APK bulunamadı: $apk"; exit 1; }
    bilgi "$apk kuruluyor…"
    local once
    once="$(kabuk pm list packages -3 | sort)"
    "$ADB" install -r "$apk"
    # Yeni gelen paketi bul; zaten kuruluysa (güncelleme) kullanıcıya sor.
    BASLATICI_PAKET="$(comm -13 <(printf '%s\n' "$once") <(kabuk pm list packages -3 | sort) \
      | sed 's/^package://' | head -n1)"
    [[ -n "$BASLATICI_PAKET" ]] || read -r -p "Başlatıcının paket adı: " BASLATICI_PAKET
    kurulu_mu "$BASLATICI_PAKET" || { hata "$BASLATICI_PAKET kurulu değil."; exit 1; }
    BASLATICI_AD="$BASLATICI_PAKET"
  elif ! kurulu_mu "$BASLATICI_PAKET"; then
    bilgi "TV'de $BASLATICI_AD için Play Store sayfası açılıyor — oradan 'Yükle'ye basın."
    kabuk am start -a android.intent.action.VIEW -d "market://details?id=$BASLATICI_PAKET" >/dev/null
    read -r -p "Kurulum bitince Enter'a basın… " _
    kurulu_mu "$BASLATICI_PAKET" || { hata "$BASLATICI_AD hâlâ kurulu değil."; exit 1; }
  fi
  tamam "$BASLATICI_AD kurulu."

  printf '\n%sStok ana ekran, sponsorlu satırların asıl kaynağıdır. Kapatılırsa Home tuşu\n' "$G"
  printf 'doğrudan %s açar. İstediğiniz zaman "%s geri-al" ile geri gelir.%s\n' "$BASLATICI_AD" "$0" "$N"
  if onay "Stok ana ekran kapatılsın mı?"; then
    while read -r p; do paket_kapat "$p"; done < <(liste_oku "$LISTELER/baslatici.txt")
    kabuk input keyevent KEYCODE_HOME
    tamam "Home tuşuna basın: yeni ana ekranınız hazır."
  else
    bilgi "Stok ana ekran açık bırakıldı. $BASLATICI_AD ayarlarından 'Varsayılan başlatıcıyı geçersiz kıl' seçeneğini kullanabilirsiniz."
  fi
}

cmd_hepsi() {
  cmd_reklam
  cmd_dns
  cmd_hiz
  cmd_baslatici "$@"
  baslik "Bitti"
  tamam "TV'niz artık reklamsız ve sade. TV'yi bir kez yeniden başlatmanız önerilir."
}

cmd_geri_al() {
  cihaz_kontrol
  baslik "Değişiklikler geri alınıyor"
  if [[ -s "$KAYIT" ]]; then
    local p
    while read -r p; do
      kabuk pm enable "$p" >/dev/null && printf '  %s↺%s %s\n' "$Y" "$N" "$p"
    done <"$KAYIT"
    rm -f "$KAYIT"
  else
    uyari "Kayıt yok; bu araçla kapatılmış paket bulunmuyor."
  fi
  kabuk settings put global private_dns_mode opportunistic
  kabuk settings delete global private_dns_specifier >/dev/null || true
  local a
  for a in window_animation_scale transition_animation_scale animator_duration_scale; do
    kabuk settings put global "$a" 1
  done
  tamam "Her şey fabrika ayarına döndü."
}

yardim() {
  logo
  cat <<EOF

${B}Kullanım:${N} $0 <komut>

  ${M}bul${N} [192.168.1]     Ağdaki TV'leri bul ve bağlan
  ${M}baglan${N} <ip>        TV'ye kablosuz ADB ile bağlan
  ${M}hepsi${N} [apk]        Tümünü uygula (önerilen)
  ${M}reklam${N}             Reklam/öneri servislerini kapat
  ${M}dns${N}                Reklam engelleyen Özel DNS'i ayarla
  ${M}baslatici${N} [apk]    Reklamsız ana ekran kur (varsayılan: $BASLATICI_AD)
  ${M}hiz${N}                Animasyonları hızlandır
  ${M}tara${N}               Şüpheli reklam/analiz paketlerini listele
  ${M}kapat${N} <paket>      Tek bir paketi kapat
  ${M}geri-al${N}            Tüm değişiklikleri geri al

Komutsuz çalıştırırsanız etkileşimli menü açılır.
EOF
}

menu() {
  logo
  local secim
  while true; do
    cat <<EOF

  ${B}1${N}) TV'yi ağda bul       ${B}5${N}) Arayüzü hızlandır
  ${B}2${N}) ✨ Hepsini uygula     ${B}6${N}) Şüpheli paketleri tara
  ${B}3${N}) Reklamları kapat      ${B}7${N}) Geri al
  ${B}4${N}) Reklamsız DNS         ${B}8${N}) Yeni ana ekran kur
                           ${B}0${N}) Çıkış
EOF
    read -r -p "Seçim: " secim
    case "$secim" in
      1) ( cmd_bul ) ;;  2) ( cmd_hepsi ) ;;   3) ( cmd_reklam ) ;;
      4) ( cmd_dns ) ;;     5) ( cmd_hiz ) ;;     6) ( cmd_tara ) ;;
      7) ( cmd_geri_al ) ;; 8) ( cmd_baslatici ) ;; 0|q) exit 0 ;;
      *) uyari "Geçersiz seçim." ;;
    esac
  done
}

main() {
  local komut="${1:-}"; shift || true
  case "$komut" in
    "")              menu ;;
    bul)             cmd_bul "$@" ;;
    baglan)          cmd_baglan "$@" ;;
    hepsi)           cmd_hepsi "$@" ;;
    reklam)          cmd_reklam ;;
    dns)             cmd_dns ;;
    baslatici)       cmd_baslatici "$@" ;;
    hiz)             cmd_hiz ;;
    tara)            cmd_tara ;;
    kapat)           cmd_kapat "$@" ;;
    geri-al|geri_al) cmd_geri_al ;;
    -h|--help|yardim) yardim ;;
    *) hata "Bilinmeyen komut: $komut"; yardim; exit 1 ;;
  esac
}

main "$@"
