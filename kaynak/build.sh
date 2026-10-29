set -e
BT=~/sdk/android-11; AJ=~/sdk/android-10/android.jar
cd "$(dirname "$0")"; rm -rf build; mkdir -p build/gen build/classes build/res
$BT/aapt2 compile --dir res -o build/res/
$BT/aapt2 link -o build/unsigned.apk -I $AJ --manifest AndroidManifest.xml --java build/gen build/res/*.flat
javac -nowarn -g:none --release 8 -encoding UTF-8 -cp $AJ -d build/classes $(find src build/gen -name '*.java') 2>&1 | grep -v "^warning\|^Note" || true
java -jar $BT/lib/dx.jar --dex --min-sdk-version=21 --output=build/classes.dex build/classes
cd build && zip -qj unsigned.apk classes.dex && cd ..
$BT/zipalign -f 4 build/unsigned.apk build/aligned.apk
[ -f "$KS" ] || { echo "KS=imza anahtari yolu gerekli"; exit 1; }
$BT/apksigner sign --ks "$KS" --ks-pass pass:"$KS_PASS" --out build/AnaEkran.apk build/aligned.apk
$BT/apksigner verify build/AnaEkran.apk && ls -la build/AnaEkran.apk
