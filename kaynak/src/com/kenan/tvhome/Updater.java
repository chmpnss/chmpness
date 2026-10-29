package com.kenan.tvhome;

import android.app.Activity;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageInstaller;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;

/**
 * Internetten guncelleme: GitHub'daki update.json'a bakar, yeni surum varsa APK'yi indirip
 * Android'in kurulum penceresini acar (kumandayla "Yukle" demek yeterli).
 */
public class Updater {

    static final String BASE = "https://raw.githubusercontent.com/chmpnss/chmpness/tv-ana-ekran/";
    static final long INTERVAL_MS = 6 * 60 * 60 * 1000L; // 6 saatte bir
    static volatile boolean running = false;

    static int myVersion(Context c) {
        try { return c.getPackageManager().getPackageInfo(c.getPackageName(), 0).versionCode; }
        catch (Exception e) { return 0; }
    }

    static void check(final Activity a, final boolean manual) {
        final SharedPreferences sp = a.getSharedPreferences("home", Context.MODE_PRIVATE);
        long last = sp.getLong("updLast", 0);
        if (!manual && System.currentTimeMillis() - last < INTERVAL_MS) return;
        if (running) return;
        running = true;
        final Handler h = new Handler(Looper.getMainLooper());
        if (manual) toast(a, h, "Güncellemeler denetleniyor…");
        new Thread(new Runnable() {
            @Override public void run() {
                try {
                    sp.edit().putLong("updLast", System.currentTimeMillis()).apply();
                    JSONObject j = new JSONObject(get(BASE + "update.json?t=" + System.currentTimeMillis()));
                    int remote = j.getInt("versionCode");
                    int mine = myVersion(a);
                    Log.i("TVHOME", "guncelleme: kutu=" + mine + " sunucu=" + remote);
                    if (remote <= mine) {
                        if (manual) toast(a, h, "Ana ekran güncel (sürüm " + mine + ")");
                        return;
                    }
                    toast(a, h, "Yeni sürüm indiriliyor (" + remote + ")…");
                    File f = new File(a.getCacheDir(), "update.apk");
                    download(BASE + j.getString("apk"), f);
                    String want = j.optString("sha256", "");
                    if (!want.isEmpty() && !want.equalsIgnoreCase(sha256(f))) throw new Exception("sha256 uyusmuyor");
                    final String notes = j.optString("notes", "");
                    install(a, f);
                    if (!notes.isEmpty()) toast(a, h, "Yenilikler: " + notes);
                } catch (Exception e) {
                    Log.w("TVHOME", "guncelleme hata: " + e);
                    if (manual) toast(a, h, "Güncelleme denetlenemedi");
                } finally {
                    running = false;
                }
            }
        }).start();
    }

    static void toast(final Context c, Handler h, final String m) {
        h.post(new Runnable() { @Override public void run() {
            if (c instanceof MainActivity) ((MainActivity) c).showToast(m);
            else Toast.makeText(c, m, Toast.LENGTH_LONG).show();
        } });
    }

    static String get(String url) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(10000);
        c.setReadTimeout(10000);
        c.setUseCaches(false);
        if (c.getResponseCode() != 200) throw new Exception("HTTP " + c.getResponseCode());
        BufferedReader br = new BufferedReader(new InputStreamReader(c.getInputStream(), "UTF-8"));
        StringBuilder sb = new StringBuilder();
        String l;
        while ((l = br.readLine()) != null) sb.append(l);
        br.close();
        return sb.toString();
    }

    static void download(String url, File out) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(15000);
        c.setReadTimeout(30000);
        if (c.getResponseCode() != 200) throw new Exception("HTTP " + c.getResponseCode());
        try (InputStream in = c.getInputStream(); OutputStream o = new FileOutputStream(out)) {
            byte[] b = new byte[32768];
            int n;
            while ((n = in.read(b)) > 0) o.write(b, 0, n);
        }
    }

    static String sha256(File f) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-256");
        try (InputStream in = new FileInputStream(f)) {
            byte[] b = new byte[32768];
            int n;
            while ((n = in.read(b)) > 0) md.update(b, 0, n);
        }
        StringBuilder sb = new StringBuilder();
        for (byte x : md.digest()) sb.append(String.format("%02x", x));
        return sb.toString();
    }

    static void install(Context c, File apk) throws Exception {
        PackageInstaller pi = c.getPackageManager().getPackageInstaller();
        PackageInstaller.SessionParams p = new PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL);
        p.setAppPackageName(c.getPackageName());
        int id = pi.createSession(p);
        PackageInstaller.Session s = pi.openSession(id);
        try (InputStream in = new FileInputStream(apk); OutputStream out = s.openWrite("base.apk", 0, apk.length())) {
            byte[] b = new byte[65536];
            int n;
            while ((n = in.read(b)) > 0) out.write(b, 0, n);
            s.fsync(out);
        }
        Intent i = new Intent(c, Result.class);
        PendingIntent pend = PendingIntent.getBroadcast(c, id, i, PendingIntent.FLAG_UPDATE_CURRENT);
        s.commit(pend.getIntentSender());
        s.close();
    }

    /** Kurulum sonucu: onay gerekiyorsa sistemin "Yukle" penceresini ac. */
    public static class Result extends BroadcastReceiver {
        @Override public void onReceive(Context c, Intent i) {
            int st = i.getIntExtra(PackageInstaller.EXTRA_STATUS, -999);
            Log.i("TVHOME", "kurulum durumu " + st + " " + i.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE));
            if (st == PackageInstaller.STATUS_PENDING_USER_ACTION) {
                Intent confirm = i.getParcelableExtra(Intent.EXTRA_INTENT);
                if (confirm != null) {
                    confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    try { c.startActivity(confirm); } catch (Exception e) { Log.w("TVHOME", "onay acilamadi " + e); }
                }
            }
        }
    }
}
