package com.kenan.tvhome;

import android.app.Service;
import android.app.usage.UsageEvents;
import android.app.usage.UsageStatsManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.SystemClock;

/**
 * Kutu acilisinda uretici yazilimi (SDMC AutoRun) TV+'i kendiliginden aciyor.
 * Acilistan sonraki 2 dakika icinde TV+ kullanici istegi olmadan one gelirse
 * ana ekrani tekrar one getirir. Kullanici TV+'i ana ekrandan acarsa karismaz.
 */
public class BootGuard extends Service {

    static final String[] WATCH = {"com.turkcell.ott"};
    static final long WINDOW_MS = 120_000;

    public static class Boot extends BroadcastReceiver {
        @Override public void onReceive(Context c, Intent i) {
            try { c.startService(new Intent(c, BootGuard.class)); } catch (Exception ignored) { }
            // ana ekrani hemen goster
            try {
                c.startActivity(new Intent(c, MainActivity.class).putExtra("greet", true)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
            } catch (Exception ignored) { }
        }
    }

    final Handler h = new Handler(Looper.getMainLooper());
    long started, lastCheck;

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        started = SystemClock.elapsedRealtime();
        lastCheck = System.currentTimeMillis() - 30_000;
        h.removeCallbacks(tick);
        h.post(tick);
        return START_NOT_STICKY;
    }

    final Runnable tick = new Runnable() {
        @Override public void run() {
            long since = SystemClock.elapsedRealtime() - started;
            if (!cleaned1 && since > 60_000) { cleaned1 = true; clean(); }
            if (since > WINDOW_MS || SystemClock.elapsedRealtime() > 10 * 60_000) { // acilistan 10 dk sonra hic calisma
                clean();
                stopSelf();
                return;
            }
            check();
            h.postDelayed(this, since < 90_000 ? 150 : 600);
        }
    };

    void check() {
        UsageStatsManager usm = (UsageStatsManager) getSystemService(Context.USAGE_STATS_SERVICE);
        if (usm == null) return;
        long now = System.currentTimeMillis();
        UsageEvents ev;
        try { ev = usm.queryEvents(lastCheck, now + 1000); } catch (Exception e) { return; }
        lastCheck = now - 1500;
        long userLaunch = getSharedPreferences("home", MODE_PRIVATE).getLong("lastUserLaunch", 0);
        UsageEvents.Event e = new UsageEvents.Event();
        boolean bounce = false;
        while (ev != null && ev.hasNextEvent()) {
            ev.getNextEvent(e);
            if (e.getEventType() != UsageEvents.Event.MOVE_TO_FOREGROUND) continue;
            for (String p : WATCH) {
                if (p.equals(e.getPackageName()) && e.getTimeStamp() - userLaunch > 8000
                        && e.getTimeStamp() > handled) {
                    handled = e.getTimeStamp();
                    bounce = true;
                }
            }
        }
        if (bounce) {
            final android.app.ActivityManager am = (android.app.ActivityManager) getSystemService(ACTIVITY_SERVICE);
            for (long d : new long[]{2500, 8000, 20000, 45000}) {
                h.postDelayed(new Runnable() { @Override public void run() {
                    try { for (String p : WATCH) am.killBackgroundProcesses(p); } catch (Exception ignored) { }
                } }, d);
            }
            try {
                startActivity(new Intent(this, MainActivity.class)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));
            } catch (Exception ignored) { }
        }
    }

    long handled = 0;
    boolean cleaned1 = false;

    /** Acilista kendiliginden baslayan uygulamalari arka planda kapat. */
    void clean() {
        int n = MainActivity.killBackground(this);
        android.util.Log.i("TVHOME", "boot clean: " + n + " paket");
    }

    @Override public void onDestroy() { h.removeCallbacksAndMessages(null); super.onDestroy(); }

    @Override public IBinder onBind(Intent intent) { return null; }
}
