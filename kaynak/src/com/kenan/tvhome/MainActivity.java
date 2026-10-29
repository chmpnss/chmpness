package com.kenan.tvhome;

import android.animation.ArgbEvaluator;
import android.animation.ValueAnimator;
import android.app.Activity;
import android.app.ActivityManager;
import android.app.AlertDialog;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Outline;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.os.StatFs;
import android.provider.Settings;
import android.text.TextUtils;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewOutlineProvider;
import android.view.animation.OvershootInterpolator;
import android.widget.FrameLayout;
import android.widget.GridLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.File;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.Date;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Talkies tarzinda reklamsiz Android TV ana ekrani (Android 10 uyumlu).
 * Sol ust: hava + saat + tarih. Sag ust: RAM/depolama gostergeleri + yuvarlak dugmeler.
 * Ortada buzlu cam dock (7 uygulama), altinda tum uygulamalar.
 * Arka plan: duvar kagidi + odaklanan uygulamanin renginde parilti.
 */
public class MainActivity extends Activity {

    static final String SETTINGS_PKG = "#settings";
    static final String[] DEFAULT_ORDER = {
            "com.turkcell.ott", "com.google.android.youtube.tv", "com.netflix.ninja",
            "com.disney.disneyplus", "com.apple.atve.androidtv.appletv", "com.trt.tabii.android",
            "com.spotify.tv.android", "com.plexapp.android", "org.jellyfin.androidtv",
            "com.google.android.youtube.tvmusic", "com.android.vending"};
    static final Set<String> DEFAULT_HIDDEN = new HashSet<>(Arrays.asList(
            "com.android.gallery3d", "com.android.camera2", "com.droidlogic.imageplayer",
            "com.google.android.videos", "com.google.android.tv.remote.service",
            "com.droidlogic.readlog", "com.sdmc.facTest", "com.google.android.play.games"));
    static final int DOCK = 7;
    static final int TOP_H = 196;
    static final int COLS = 6;

    static class AppItem {
        String pkg, label;
        Drawable banner, icon;
        Intent intent;
        int tint, glow;
    }

    final Handler h = new Handler(Looper.getMainLooper());
    SharedPreferences sp;
    float density;
    Typeface light, regular, medium;

    ImageView wallpaper;
    View glow;
    int glowColor = 0x00000000;
    ValueAnimator glowAnim;
    ScrollView scroll;
    LinearLayout dockRow;
    GridLayout grid;
    TextView weather, clock, date, allLabel, ramText, diskText;
    ProgressBar ramBar, diskBar;
    final List<AppItem> apps = new ArrayList<>();
    final List<View> tiles = new ArrayList<>();
    AppItem focused;
    BroadcastReceiver pkgReceiver;

    int dp(float v) { return Math.round(v * density); }

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        density = getResources().getDisplayMetrics().density;
        sp = getSharedPreferences("home", MODE_PRIVATE);
        light = Typeface.create("sans-serif-light", Typeface.NORMAL);
        regular = Typeface.create("sans-serif", Typeface.NORMAL);
        medium = Typeface.create("sans-serif-medium", Typeface.NORMAL);
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
        setContentView(buildUi());
        if (getIntent() != null && getIntent().getBooleanExtra("greet", false)) greet();
        handleVoiceExtras(getIntent());
        loadApps();

        pkgReceiver = new BroadcastReceiver() {
            @Override public void onReceive(Context c, Intent i) { loadApps(); }
        };
        IntentFilter f = new IntentFilter();
        f.addAction(Intent.ACTION_PACKAGE_ADDED);
        f.addAction(Intent.ACTION_PACKAGE_REMOVED);
        f.addAction(Intent.ACTION_PACKAGE_CHANGED);
        f.addDataScheme("package");
        registerReceiver(pkgReceiver, f);
    }

    @Override protected void onDestroy() {
        try { unregisterReceiver(pkgReceiver); } catch (Exception ignored) { }
        h.removeCallbacksAndMessages(null);
        super.onDestroy();
    }

    @Override protected void onResume() {
        super.onResume();
        h.removeCallbacks(bounceBack);
        tick.run();
        weatherTick.run();
        Updater.check(this, false);
    }

    long lastKey = 0;

    @Override public boolean dispatchKeyEvent(KeyEvent e) {
        lastKey = System.currentTimeMillis();
        return super.dispatchKeyEvent(e);
    }

    /** Acilista uretici yazilimi TV+'i kendiliginden acarsa ana ekrani geri getir. */
    final Runnable bounceBack = new Runnable() {
        @Override public void run() {
            try {
                startActivity(new Intent(MainActivity.this, MainActivity.class)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_REORDER_TO_FRONT));
                android.util.Log.i("TVHOME", "acilis: ana ekran geri getirildi");
            } catch (Exception e) { android.util.Log.w("TVHOME", "bounce " + e); }
            final ActivityManager am = (ActivityManager) getSystemService(ACTIVITY_SERVICE);
            for (long d : new long[]{3000, 15000, 40000}) {
                h.postDelayed(new Runnable() { @Override public void run() {
                    try { am.killBackgroundProcesses("com.turkcell.ott"); } catch (Exception ignored) { }
                } }, d);
            }
        }
    };

    boolean userCaused() {
        long now = System.currentTimeMillis();
        long ul = sp.getLong("lastUserLaunch", 0);
        return now - lastKey < 4000 || now - ul < 8000;
    }

    @Override protected void onPause() {
        super.onPause();
        if (android.os.SystemClock.elapsedRealtime() < 150_000 && !userCaused()) {
            h.removeCallbacks(bounceBack);
            h.postDelayed(bounceBack, 250);
        }
        h.removeCallbacks(tick);
        h.removeCallbacks(weatherTick);
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        if (intent != null && intent.getBooleanExtra("greet", false)) greet();
        handleVoiceExtras(intent);
        if (!tiles.isEmpty()) {
            scroll.smoothScrollTo(0, 0);
            tiles.get(0).requestFocus();
        }
    }

    @Override public void onBackPressed() { closePanel(); }

    // ================================================================ UI

    View buildUi() {
        FrameLayout root = new FrameLayout(this);
        rootView = root;
        root.setClipChildren(true); // kaydirilan uygulamalar ustteki saatin altina tasmasin
        root.setBackgroundColor(0xFF0A0A0C);

        wallpaper = new ImageView(this);
        wallpaper.setScaleType(ImageView.ScaleType.CENTER_CROP);
        final Bitmap wp = loadWallpaper();
        if (wp != null) {
            wallpaper.setImageBitmap(wp);
            syncSystemWallpaper(wp);
        }
        root.addView(wallpaper, match());

        View dim = new View(this);
        dim.setBackground(new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
                new int[]{0x40000000, 0x66000000, 0xE0000000}));
        root.addView(dim, match());

        glow = new View(this);
        root.addView(glow, match());
        setGlow(0x00000000);

        scroll = new ScrollView(this);
        scroll.setVerticalScrollBarEnabled(false);
        scroll.setOverScrollMode(View.OVER_SCROLL_NEVER);
        scroll.setClipChildren(true);
        scroll.setClipToPadding(true);
        scroll.setDescendantFocusability(ViewGroup.FOCUS_AFTER_DESCENDANTS);

        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setClipChildren(false);
        content.setClipToPadding(false);
        content.setPadding(dp(52), dp(18), dp(52), dp(40));

        // --- buzlu cam dock
        FrameLayout band = new FrameLayout(this);
        band.setClipChildren(false);
        band.setClipToPadding(false);
        GradientDrawable frost = new GradientDrawable();
        frost.setCornerRadius(dp(26));
        frost.setColor(0x24FFFFFF);
        frost.setStroke(Math.max(1, dp(0.75f)), 0x30FFFFFF);
        band.setBackground(frost);
        band.setPadding(dp(18), dp(18), dp(18), dp(18));
        dockRow = new LinearLayout(this);
        dockRow.setOrientation(LinearLayout.HORIZONTAL);
        dockRow.setClipChildren(false);
        dockRow.setClipToPadding(false);
        dockRow.setGravity(Gravity.CENTER);
        band.addView(dockRow, new FrameLayout.LayoutParams(-1, -2));
        LinearLayout.LayoutParams bl = new LinearLayout.LayoutParams(-1, -2);
        bl.bottomMargin = dp(30);
        content.addView(band, bl);

        allLabel = text(12, 0x99FFFFFF, medium);
        allLabel.setText("TÜM UYGULAMALAR");
        allLabel.setLetterSpacing(0.14f);
        LinearLayout.LayoutParams al = new LinearLayout.LayoutParams(-2, -2);
        al.leftMargin = dp(4);
        al.bottomMargin = dp(14);
        content.addView(allLabel, al);

        grid = new GridLayout(this);
        grid.setColumnCount(COLS);
        grid.setClipChildren(false);
        grid.setClipToPadding(false);
        content.addView(grid, new LinearLayout.LayoutParams(-1, -2));

        scroll.addView(content, new ScrollView.LayoutParams(-1, -2));
        scroll.setVerticalFadingEdgeEnabled(true);
        scroll.setFadingEdgeLength(dp(28));
        FrameLayout.LayoutParams sl = match();
        sl.topMargin = dp(TOP_H);
        root.addView(scroll, sl);

        // ust bolum sabit: kaydirinca yarim kalmaz
        View top = buildTopBar();
        topBarView = top;
        top.setPadding(dp(52), dp(28), dp(52), 0);
        root.addView(top, new FrameLayout.LayoutParams(-1, dp(TOP_H), Gravity.TOP));
        return root;
    }

    View buildTopBar() {
        FrameLayout top = new FrameLayout(this);
        top.setClipChildren(false);
        top.setClipToPadding(false);

        LinearLayout left = new LinearLayout(this);
        left.setOrientation(LinearLayout.VERTICAL);
        weather = text(14, 0xCCFFFFFF, medium);
        weather.setLetterSpacing(0.12f);
        weather.setText(sp.getString("weather", ""));
        clock = text(76, Color.WHITE, light);
        clock.setSingleLine(true);
        clock.setLetterSpacing(-0.02f);
        date = text(15, 0xCCFFFFFF, medium);
        date.setLetterSpacing(0.12f);
        left.addView(weather);
        LinearLayout.LayoutParams cl = new LinearLayout.LayoutParams(dp(520), -2);
        cl.topMargin = dp(8);
        left.addView(clock, cl);
        LinearLayout.LayoutParams dl = new LinearLayout.LayoutParams(-2, -2);
        dl.topMargin = dp(8);
        left.addView(date, dl);
        top.addView(left, new FrameLayout.LayoutParams(-2, -2, Gravity.START | Gravity.TOP));

        LinearLayout right = new LinearLayout(this);
        right.setOrientation(LinearLayout.HORIZONTAL);
        right.setGravity(Gravity.CENTER_VERTICAL);
        right.setClipChildren(false);
        right.setClipToPadding(false);
        right.setPadding(dp(8), dp(8), dp(8), dp(8));

        LinearLayout meters = new LinearLayout(this);
        meters.setOrientation(LinearLayout.VERTICAL);
        ramText = text(10, 0x99FFFFFF, medium);
        ramText.setLetterSpacing(0.1f);
        ramBar = meter();
        diskText = text(10, 0x99FFFFFF, medium);
        diskText.setLetterSpacing(0.1f);
        diskBar = meter();
        meters.addView(ramText);
        LinearLayout.LayoutParams ml = new LinearLayout.LayoutParams(dp(132), dp(3));
        ml.topMargin = dp(4);
        ml.bottomMargin = dp(8);
        meters.addView(ramBar, ml);
        meters.addView(diskText);
        LinearLayout.LayoutParams ml2 = new LinearLayout.LayoutParams(dp(132), dp(3));
        ml2.topMargin = dp(4);
        meters.addView(diskBar, ml2);
        LinearLayout.LayoutParams mlp = new LinearLayout.LayoutParams(-2, -2);
        mlp.rightMargin = dp(18);
        right.addView(meters, mlp);

        right.addView(roundButton("add", null, "Uygulama ekle"));
        right.addView(roundButton("clean", null, "Arka plandaki uygulamaları kapat"));
        right.addView(roundButton("wifi", new Intent(Settings.ACTION_WIFI_SETTINGS), "Wi-Fi"));
        right.addView(roundButton("gear", new Intent(Settings.ACTION_SETTINGS), "Ayarlar"));
        top.addView(right, new FrameLayout.LayoutParams(-2, -2, Gravity.END | Gravity.TOP));
        hint = text(12, 0xE6FFFFFF, medium);
        hint.setLetterSpacing(0.06f);
        hint.setAlpha(0f);
        FrameLayout.LayoutParams hl = new FrameLayout.LayoutParams(-2, -2, Gravity.END | Gravity.TOP);
        hl.topMargin = dp(60);
        top.addView(hint, hl);
        return top;
    }

    ProgressBar meter() {
        ProgressBar p = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        p.setMax(100);
        GradientDrawable track = new GradientDrawable();
        track.setColor(0x33FFFFFF);
        track.setCornerRadius(dp(2));
        GradientDrawable fill = new GradientDrawable();
        fill.setColor(0xE6FFFFFF);
        fill.setCornerRadius(dp(2));
        android.graphics.drawable.ClipDrawable clip =
                new android.graphics.drawable.ClipDrawable(fill, Gravity.START, android.graphics.drawable.ClipDrawable.HORIZONTAL);
        android.graphics.drawable.LayerDrawable ld =
                new android.graphics.drawable.LayerDrawable(new Drawable[]{track, clip});
        ld.setId(0, android.R.id.background);
        ld.setId(1, android.R.id.progress);
        p.setProgressDrawable(ld);
        p.setFocusable(false);
        return p;
    }

    TextView hint;

    View roundButton(final String kind, final Intent intent, final String label) {
        final FrameLayout b = new FrameLayout(this);
        b.setFocusable(true);
        b.setClickable(true);
        final GradientDrawable bg = new GradientDrawable();
        bg.setShape(GradientDrawable.OVAL);
        bg.setColor(0x26FFFFFF);
        b.setBackground(bg);
        IconView icon = new IconView(this, kind);
        b.addView(icon, new FrameLayout.LayoutParams(dp(20), dp(20), Gravity.CENTER));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(44), dp(44));
        lp.leftMargin = dp(10);
        b.setLayoutParams(lp);
        b.setOnFocusChangeListener(new View.OnFocusChangeListener() {
            @Override public void onFocusChange(View v, boolean has) {
                bg.setColor(has ? 0xFFFFFFFF : 0x26FFFFFF);
                ((IconView) b.getChildAt(0)).setColor(has ? 0xFF111111 : 0xFFFFFFFF);
                v.animate().scaleX(has ? 1.12f : 1f).scaleY(has ? 1.12f : 1f)
                        .setInterpolator(new OvershootInterpolator(2f)).setDuration(220).start();
                if (has) {
                    scroll.smoothScrollTo(0, 0);
                    hint.setText(label);
                }
                hint.animate().alpha(has ? 1f : 0f).setDuration(160).start();
            }
        });
        b.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                if (intent == null) {
                    if (kind.equals("add")) addMenu(); else cleanBackground();
                    return;
                }
                try { startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); } catch (Exception ignored) { }
            }
        });
        return b;
    }

    /** Basit vektor ikonlar (wifi, disli). */
    static class IconView extends View {
        final String kind;
        final android.graphics.Paint p = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
        IconView(Context c, String k) {
            super(c);
            kind = k;
            p.setColor(Color.WHITE);
            p.setStyle(android.graphics.Paint.Style.STROKE);
            p.setStrokeCap(android.graphics.Paint.Cap.ROUND);
        }
        void setColor(int c) { p.setColor(c); invalidate(); }
        @Override protected void onDraw(Canvas c) {
            float w = getWidth(), hh = getHeight();
            p.setStrokeWidth(w * 0.1f);
            if (kind.equals("add")) {
                c.drawLine(w * 0.5f, hh * 0.2f, w * 0.5f, hh * 0.8f, p);
                c.drawLine(w * 0.2f, hh * 0.5f, w * 0.8f, hh * 0.5f, p);
            } else if (kind.equals("clean")) {
                float cx = w / 2, cy = hh / 2;
                c.drawLine(w * 0.2f, hh * 0.3f, w * 0.8f, hh * 0.3f, p);
                c.drawLine(w * 0.3f, hh * 0.52f, w * 0.7f, hh * 0.52f, p);
                c.drawLine(w * 0.4f, hh * 0.74f, w * 0.6f, hh * 0.74f, p);
            } else if (kind.equals("wifi")) {
                float cx = w / 2, cy = hh * 0.85f;
                for (int i = 1; i <= 3; i++) {
                    float r = w * 0.27f * i;
                    android.graphics.RectF o = new android.graphics.RectF(cx - r, cy - r, cx + r, cy + r);
                    if (i < 3 || true) c.drawArc(o, 225, 90, false, p);
                }
                p.setStyle(android.graphics.Paint.Style.FILL);
                c.drawCircle(cx, cy - w * 0.02f, w * 0.08f, p);
                p.setStyle(android.graphics.Paint.Style.STROKE);
            } else {
                float cx = w / 2, cy = hh / 2;
                c.drawCircle(cx, cy, w * 0.24f, p);
                p.setStrokeWidth(w * 0.16f);
                p.setStrokeCap(android.graphics.Paint.Cap.BUTT);
                for (int i = 0; i < 8; i++) {
                    double a = Math.PI / 4 * i;
                    c.drawLine(cx + (float) Math.cos(a) * w * 0.32f, cy + (float) Math.sin(a) * w * 0.32f,
                            cx + (float) Math.cos(a) * w * 0.46f, cy + (float) Math.sin(a) * w * 0.46f, p);
                }
                p.setStrokeCap(android.graphics.Paint.Cap.ROUND);
            }
        }
    }

    FrameLayout.LayoutParams match() { return new FrameLayout.LayoutParams(-1, -1); }

    TextView text(float size, int color, Typeface tf) {
        TextView t = new TextView(this);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, size);
        t.setTextColor(color);
        t.setTypeface(tf);
        t.setIncludeFontPadding(false);
        return t;
    }

    void rounded(View v, final float r) {
        v.setOutlineProvider(new ViewOutlineProvider() {
            @Override public void getOutline(View view, Outline o) {
                o.setRoundRect(0, 0, view.getWidth(), view.getHeight(), r * density);
            }
        });
        v.setClipToOutline(true);
    }

    Bitmap loadWallpaper() {
        try {
            File dir = getExternalFilesDir(null);
            if (dir != null) {
                File f = new File(dir, "arkaplan.jpg");
                if (f.exists()) return BitmapFactory.decodeFile(f.getAbsolutePath());
            }
        } catch (Exception ignored) { }
        File keep = new File(getFilesDir(), "arkaplan.jpg");
        try (InputStream in = getAssets().open("arkaplan.jpg")) {
            // uygulamayla gelen resmi kutuya kopyala; sonraki (resimsiz) guncellemeler de kullanir
            java.io.FileOutputStream out = new java.io.FileOutputStream(keep);
            byte[] buf = new byte[16384];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
            out.close();
        } catch (Exception ignored) { }
        if (keep.exists()) return BitmapFactory.decodeFile(keep.getAbsolutePath());
        return null;
    }

    // ================================================================ parilti

    void setGlow(int color) {
        GradientDrawable g = new GradientDrawable();
        g.setGradientType(GradientDrawable.RADIAL_GRADIENT);
        g.setGradientCenter(0.5f, 1.05f);
        g.setGradientRadius(getResources().getDisplayMetrics().widthPixels * 0.62f);
        g.setColors(new int[]{color, (color & 0x00FFFFFF) | 0x40000000, 0x00000000});
        glow.setBackground(g);
    }

    void animateGlow(int to) {
        if (glowAnim != null) glowAnim.cancel();
        final int from = glowColor;
        glowAnim = ValueAnimator.ofObject(new ArgbEvaluator(), from, to);
        glowAnim.setDuration(450);
        glowAnim.addUpdateListener(new ValueAnimator.AnimatorUpdateListener() {
            @Override public void onAnimationUpdate(ValueAnimator a) {
                glowColor = (Integer) a.getAnimatedValue();
                setGlow(glowColor);
            }
        });
        glowAnim.start();
    }

    // ================================================================ uygulamalar

    void loadApps() {
        new Thread(new Runnable() {
            @Override public void run() {
                final List<AppItem> list = queryApps();
                h.post(new Runnable() { @Override public void run() { showApps(list); } });
            }
        }).start();
    }

    List<AppItem> queryApps() {
        PackageManager pm = getPackageManager();
        Map<String, AppItem> map = new HashMap<>();
        collect(pm, map, Intent.CATEGORY_LEANBACK_LAUNCHER);
        collect(pm, map, Intent.CATEGORY_LAUNCHER);

        AppItem s = new AppItem();
        s.pkg = SETTINGS_PKG;
        s.label = "Ayarlar";
        s.intent = new Intent(Settings.ACTION_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        try { s.icon = pm.getApplicationIcon("com.android.tv.settings"); } catch (Exception e) {
            s.icon = getResources().getDrawable(android.R.drawable.ic_menu_preferences, null);
        }
        map.put(s.pkg, s);

        Set<String> hidden = sp.getStringSet("hidden", DEFAULT_HIDDEN);
        List<String> order = savedOrder();
        final Map<String, Integer> rank = new HashMap<>();
        for (int i = 0; i < order.size(); i++) rank.put(order.get(i), i);

        List<AppItem> out = new ArrayList<>();
        for (AppItem a : map.values()) if (!hidden.contains(a.pkg)) out.add(a);
        Collections.sort(out, new Comparator<AppItem>() {
            @Override public int compare(AppItem x, AppItem y) {
                Integer rx = rank.get(x.pkg), ry = rank.get(y.pkg);
                if (x.pkg.equals(SETTINGS_PKG) && rx == null) return 1;
                if (y.pkg.equals(SETTINGS_PKG) && ry == null) return -1;
                if (rx != null && ry != null) return rx - ry;
                if (rx != null) return -1;
                if (ry != null) return 1;
                return x.label.compareToIgnoreCase(y.label);
            }
        });
        for (AppItem a : out) prepareArt(a);
        return out;
    }

    void collect(PackageManager pm, Map<String, AppItem> map, String category) {
        Intent q = new Intent(Intent.ACTION_MAIN).addCategory(category);
        for (ResolveInfo r : pm.queryIntentActivities(q, 0)) {
            String pkg = r.activityInfo.packageName;
            if (pkg.equals(getPackageName()) || map.containsKey(pkg)) continue;
            if (pkg.equals("com.android.tv.settings")) continue;
            AppItem a = new AppItem();
            a.pkg = pkg;
            a.label = String.valueOf(r.loadLabel(pm));
            Intent li = pm.getLeanbackLaunchIntentForPackage(pkg);
            if (li == null) li = pm.getLaunchIntentForPackage(pkg);
            if (li == null) continue;
            a.intent = li.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED);
            try {
                ApplicationInfo ai = pm.getApplicationInfo(pkg, 0);
                a.banner = r.activityInfo.loadBanner(pm);
                if (a.banner == null) a.banner = ai.loadBanner(pm);
            } catch (Exception ignored) { }
            a.icon = r.loadIcon(pm);
            map.put(pkg, a);
        }
    }

    List<String> savedOrder() {
        String s = sp.getString("order", null);
        if (s == null) return new ArrayList<>(Arrays.asList(DEFAULT_ORDER));
        return new ArrayList<>(Arrays.asList(s.split(",")));
    }

    void saveOrder() {
        StringBuilder b = new StringBuilder();
        for (AppItem a : apps) { if (b.length() > 0) b.append(','); b.append(a.pkg); }
        sp.edit().putString("order", b.toString()).apply();
    }

    /** Karo zemin rengi (ortalama) ve parilti rengi (en canli renk). */
    void prepareArt(AppItem a) {
        Drawable src = a.banner != null ? a.banner : a.icon;
        if (src == null) return;
        Bitmap small = Bitmap.createBitmap(48, 27, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(small);
        Drawable d = src.getConstantState() != null ? src.getConstantState().newDrawable().mutate() : src;
        if (a.banner != null) d.setBounds(0, 0, 48, 27); else d.setBounds(10, 0, 38, 27);
        d.draw(c);
        int[] px = new int[48 * 27];
        small.getPixels(px, 0, 48, 0, 0, 48, 27);
        long r = 0, g = 0, bl = 0, n = 0;
        double wr = 0, wg = 0, wb = 0, wsum = 0;
        float[] hsv = new float[3];
        for (int p : px) {
            if (Color.alpha(p) < 128) continue;
            r += Color.red(p); g += Color.green(p); bl += Color.blue(p); n++;
            Color.colorToHSV(p, hsv);
            double w = hsv[1] * hsv[1] * hsv[2];
            wr += Color.red(p) * w; wg += Color.green(p) * w; wb += Color.blue(p) * w; wsum += w;
        }
        if (n == 0) n = 1;
        a.tint = Color.rgb((int) (r / n * 0.5), (int) (g / n * 0.5), (int) (bl / n * 0.5));
        int vivid;
        if (wsum > n * 0.05) vivid = Color.rgb((int) (wr / wsum), (int) (wg / wsum), (int) (wb / wsum));
        else vivid = 0xFF8E8E93;
        Color.colorToHSV(vivid, hsv);
        if (wsum > n * 0.05) { hsv[1] = Math.max(hsv[1], 0.7f); hsv[2] = 0.95f; }
        a.glow = (Color.HSVToColor(hsv) & 0x00FFFFFF) | 0xB3000000;
    }

    void showApps(List<AppItem> list) {
        String keep = focused != null ? focused.pkg : null;
        apps.clear();
        apps.addAll(list);
        dockRow.removeAllViews();
        grid.removeAllViews();
        tiles.clear();
        int target = 0;
        for (int i = 0; i < apps.size(); i++) {
            AppItem a = apps.get(i);
            if (i < DOCK) {
                View t = buildTile(a, i, dp(106), dp(60));
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(dp(106), dp(60));
                if (i > 0) lp.leftMargin = dp(14);
                dockRow.addView(t, lp);
                tiles.add(t);
            } else {
                int gi = i - DOCK;
                View cell = buildTile(a, i, dp(129), dp(73));
                GridLayout.LayoutParams lp = new GridLayout.LayoutParams();
                lp.width = dp(129);
                lp.height = dp(73);
                lp.rightMargin = (gi % COLS == COLS - 1) ? 0 : dp(16);
                lp.bottomMargin = dp(18);
                grid.addView(cell, lp);
                tiles.add(cell);
            }
            if (a.pkg.equals(keep)) target = i;
        }
        allLabel.setVisibility(apps.size() > DOCK ? View.VISIBLE : View.GONE);
        if (!tiles.isEmpty()) {
            final int t = Math.min(target, tiles.size() - 1);
            tiles.get(t).post(new Runnable() { @Override public void run() { tiles.get(t).requestFocus(); } });
        }
    }

    View buildTile(final AppItem a, final int index, int w, int hgt) {
        final FrameLayout tile = new FrameLayout(this);
        tile.setFocusable(true);
        tile.setClickable(true);
        rounded(tile, 12);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(a.banner != null ? 0xFF1C1C1E : (a.tint == 0 ? 0xFF2C2C2E : lighten(a.tint)));
        tile.setBackground(bg);

        ImageView img = new ImageView(this);
        if (a.banner != null) {
            img.setScaleType(ImageView.ScaleType.CENTER_CROP);
            img.setImageDrawable(a.banner);
            tile.addView(img, new FrameLayout.LayoutParams(-1, -1));
        } else {
            img.setScaleType(ImageView.ScaleType.FIT_CENTER);
            img.setImageDrawable(a.icon);
            int s = Math.round(hgt * 0.6f);
            tile.addView(img, new FrameLayout.LayoutParams(s, s, Gravity.CENTER));
        }

        // beyaz odak halkasi
        final GradientDrawable ring = new GradientDrawable();
        ring.setCornerRadius(dp(12));
        ring.setColor(0x00000000);
        ring.setStroke(dp(2.5f), 0xFFFFFFFF);
        final View ringView = new View(this);
        ringView.setBackground(ring);
        ringView.setAlpha(0f);
        tile.addView(ringView, new FrameLayout.LayoutParams(-1, -1));

        tile.setOnFocusChangeListener(new View.OnFocusChangeListener() {
            @Override public void onFocusChange(View v, boolean has) {
                float s = has ? 1.12f : 1f;
                v.animate().scaleX(s).scaleY(s).translationZ(has ? dp(14) : 0)
                        .setInterpolator(new OvershootInterpolator(1.6f)).setDuration(260).start();
                ringView.animate().alpha(has ? 1f : 0f).setDuration(160).start();
                if (has) onTileFocused(a, index, v);
            }
        });
        tile.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) { launch(a, v); }
        });
        tile.setOnLongClickListener(new View.OnLongClickListener() {
            @Override public boolean onLongClick(View v) { editMenu(a); return true; }
        });
        tile.setOnKeyListener(new View.OnKeyListener() {
            @Override public boolean onKey(View v, int code, KeyEvent e) {
                if (code == KeyEvent.KEYCODE_MENU && e.getAction() == KeyEvent.ACTION_UP) {
                    editMenu(a);
                    return true;
                }
                return false;
            }
        });
        return tile;
    }

    static int lighten(int c) {
        return Color.rgb(Math.min(255, Color.red(c) + 40), Math.min(255, Color.green(c) + 40),
                Math.min(255, Color.blue(c) + 40));
    }

    void onTileFocused(AppItem a, int index, View v) {
        focused = a;
        if (index < DOCK) {
            scroll.smoothScrollTo(0, 0);
        } else {
            View content = (View) grid.getParent();
            int y = content.getPaddingTop() + grid.getTop() + v.getTop() - dp(26);
            scroll.smoothScrollTo(0, Math.max(0, y));
        }
        animateGlow(a.glow);
    }

    void launch(AppItem a, View v) {
        try {
            sp.edit().putLong("lastUserLaunch", System.currentTimeMillis()).apply();
            startActivity(a.intent);
        } catch (Exception ignored) { }
    }

    // ================================================================ duzenleme

    void editMenu(final AppItem a) {
        final int i = apps.indexOf(a);
        final List<String> opts = new ArrayList<>();
        if (i >= DOCK) opts.add("Dock'a ekle");
        else opts.add("Dock'tan çıkar");
        opts.addAll(Arrays.asList("Sola taşı", "Sağa taşı", "Başa taşı"));
        if (!a.pkg.equals(SETTINGS_PKG)) {
            opts.add("Gizle");
            opts.add("Uygulama bilgisi");
            opts.add("Kaldır");
        }
        Set<String> hidden = sp.getStringSet("hidden", DEFAULT_HIDDEN);
        if (!hidden.isEmpty()) opts.add("Gizlenenleri geri getir (" + hidden.size() + ")");

        new PanelBuilder()
                .setTitle(a.label)
                .setItems(opts.toArray(new String[0]), new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) {
                        String o = opts.get(w);
                        if (o.equals("Dock'a ekle")) move(i, DOCK - 1);
                        else if (o.equals("Dock'tan çıkar")) move(i, DOCK);
                        else if (o.equals("Sola taşı")) move(i, i - 1);
                        else if (o.equals("Sağa taşı")) move(i, i + 1);
                        else if (o.equals("Başa taşı")) move(i, 0);
                        else if (o.equals("Gizle")) {
                            Set<String> hs = new HashSet<>(sp.getStringSet("hidden", DEFAULT_HIDDEN));
                            hs.add(a.pkg);
                            sp.edit().putStringSet("hidden", hs).apply();
                            focused = i + 1 < apps.size() ? apps.get(i + 1) : null;
                            loadApps();
                        } else if (o.equals("Uygulama bilgisi")) {
                            try {
                                startActivity(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                                        Uri.parse("package:" + a.pkg)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
                            } catch (Exception ignored) { }
                        } else if (o.equals("Kaldır")) {
                            try {
                                startActivity(new Intent(Intent.ACTION_DELETE,
                                        Uri.parse("package:" + a.pkg)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
                            } catch (Exception ignored) { }
                        } else if (o.startsWith("Gizlenenleri")) {
                            sp.edit().putStringSet("hidden", new HashSet<String>()).apply();
                            loadApps();
                        }
                    }
                })
                .show();
    }

    void move(int from, int to) {
        if (from < 0 || from >= apps.size()) return;
        to = Math.max(0, Math.min(apps.size() - 1, to));
        if (to == from) return;
        AppItem a = apps.remove(from);
        apps.add(to, a);
        saveOrder();
        focused = a;
        showApps(new ArrayList<>(apps));
    }

    // ================================================================ saat, gostergeler, hava

    final Runnable tick = new Runnable() {
        @Override public void run() {
            Locale tr = new Locale("tr", "TR");
            Date now = new Date();
            clock.setText(new SimpleDateFormat("HH:mm", tr).format(now));
            date.setText(new SimpleDateFormat("EEEE  d MMMM", tr).format(now).toUpperCase(tr));
            updateMeters();
            h.removeCallbacks(this);
            h.postDelayed(this, 60_000 - (System.currentTimeMillis() % 60_000) + 200);
        }
    };

    void updateMeters() {
        try {
            ActivityManager am = (ActivityManager) getSystemService(ACTIVITY_SERVICE);
            ActivityManager.MemoryInfo mi = new ActivityManager.MemoryInfo();
            am.getMemoryInfo(mi);
            int used = (int) (100 - mi.availMem * 100 / mi.totalMem);
            ramBar.setProgress(used);
            ramText.setText(String.format(Locale.US, "RAM  %.1f/%.1f GB",
                    (mi.totalMem - mi.availMem) / 1e9, mi.totalMem / 1e9));
            StatFs fs = new StatFs(Environment.getDataDirectory().getPath());
            long tot = fs.getTotalBytes(), free = fs.getAvailableBytes();
            diskBar.setProgress((int) (100 - free * 100 / tot));
            diskText.setText(String.format(Locale.US, "DEPOLAMA  %.1f/%.1f GB", (tot - free) / 1e9, tot / 1e9));
        } catch (Exception ignored) { }
    }

    final Runnable weatherTick = new Runnable() {
        @Override public void run() {
            fetchWeather();
            h.removeCallbacks(this);
            h.postDelayed(this, 30 * 60_000);
        }
    };

    // Kisisel ayarlar uygulamanin icinde degil, yalnizca kutuda (SharedPreferences) saklanir.
    String cfg(String k, String def) {
        String v = sp.getString("cfg_" + k, def);
        if (v != null && v.startsWith("b64:")) {
            try { v = new String(android.util.Base64.decode(v.substring(4), android.util.Base64.DEFAULT), "UTF-8"); }
            catch (Exception ignored) { }
        }
        return v;
    }
    double lat() { return Double.parseDouble(cfg("lat", "41.0082")); }
    double lon() { return Double.parseDouble(cfg("lon", "28.9784")); }
    String place() { return cfg("place", ""); }
    String placeSuffix() { return place().isEmpty() ? "" : "   ●   " + place(); }

    void fetchWeather() {
        new Thread(new Runnable() {
            @Override public void run() {
                String s = null;
                try { s = fetchMgm(); } catch (Exception e) {
                    android.util.Log.w("TVHOME", "MGM hata: " + e);
                }
                if (s == null) {
                    try { s = fetchOpenMeteo(); } catch (Exception e) {
                        android.util.Log.w("TVHOME", "Open-Meteo hata: " + e);
                    }
                }
                if (s == null) return;
                final String fs = s;
                sp.edit().putString("weather", fs).apply();
                h.post(new Runnable() { @Override public void run() { weather.setText(fs); } });
            }
        }).start();
    }

    String httpGet(String url, boolean mgm) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
        c.setConnectTimeout(8000);
        c.setReadTimeout(8000);
        if (mgm) {
            c.setRequestProperty("Origin", "https://www.mgm.gov.tr");
            c.setRequestProperty("Referer", "https://www.mgm.gov.tr/");
            c.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 10) AnaEkran/1.0");
            c.setRequestProperty("Accept", "application/json");
        }
        int code = c.getResponseCode();
        if (code != 200) throw new Exception("HTTP " + code + " " + url);
        BufferedReader br = new BufferedReader(new InputStreamReader(c.getInputStream(), "UTF-8"));
        StringBuilder sb = new StringBuilder();
        String l;
        while ((l = br.readLine()) != null) sb.append(l);
        br.close();
        return sb.toString();
    }

    /** MGM (Meteoroloji Genel Mudurlugu) secili ilce icin anlik durum. */
    String fetchMgm() throws Exception {
        int ist = sp.getInt("mgmIst", 0);
        if (ist == 0) {
            String m = httpGet("https://servis.mgm.gov.tr/web/merkezler?il=" + Uri.encode(cfg("mgm_il", "Istanbul")) + "&ilce=" + Uri.encode(cfg("mgm_ilce", "")), true);
            android.util.Log.i("TVHOME", "MGM merkez: " + m);
            org.json.JSONArray arr = new org.json.JSONArray(m);
            JSONObject o = arr.getJSONObject(0);
            ist = o.optInt("sondurumIstNo", 0);
            if (ist == 0) throw new Exception("istasyon yok");
            sp.edit().putInt("mgmIst", ist).apply();
        }
        String r = httpGet("https://servis.mgm.gov.tr/web/sondurumlar?istno=" + ist, true);
        android.util.Log.i("TVHOME", "MGM son durum: " + r);
        org.json.JSONArray arr = new org.json.JSONArray(r);
        JSONObject o = arr.getJSONObject(0);
        double t = o.optDouble("sicaklik", -9999);
        if (t < -100) throw new Exception("sicaklik yok");
        String d = hadise(o.optString("hadiseKodu", ""));
        return Math.round(t) + "°" + (d.isEmpty() ? "" : "  " + d) + placeSuffix();
    }

    String fetchOpenMeteo() throws Exception {
        String r = httpGet("https://api.open-meteo.com/v1/forecast?latitude=" + lat() + "&longitude=" + lon()
                + "&current=temperature_2m,weather_code&timezone=auto", false);
        JSONObject cur = new JSONObject(r).getJSONObject("current");
        long t = Math.round(cur.getDouble("temperature_2m"));
        return t + "°  " + wmo(cur.getInt("weather_code")) + placeSuffix();
    }

    static String hadise(String k) {
        switch (k) {
            case "A": return "AÇIK";
            case "AB": return "AZ BULUTLU";
            case "PB": return "PARÇALI BULUTLU";
            case "CB": return "ÇOK BULUTLU";
            case "KB": return "KAPALI";
            case "HY": return "HAFİF YAĞMURLU";
            case "Y": return "YAĞMURLU";
            case "KY": return "KUVVETLİ YAĞMURLU";
            case "KKY": return "KARLA KARIŞIK YAĞMURLU";
            case "HKY": return "HAFİF KAR YAĞIŞLI";
            case "K": return "KAR YAĞIŞLI";
            case "YKY": return "YOĞUN KAR YAĞIŞLI";
            case "HSY": return "HAFİF SAĞANAK";
            case "SY": return "SAĞANAK";
            case "KSY": return "KUVVETLİ SAĞANAK";
            case "MSY": return "YER YER SAĞANAK";
            case "DY": return "DOLU";
            case "GSY": return "GÖK GÜRÜLTÜLÜ SAĞANAK";
            case "KGSY": return "KUVVETLİ GÖK GÜRÜLTÜLÜ SAĞANAK";
            case "SIS": return "SİSLİ";
            case "PUS": return "PUSLU";
            case "DMN": return "DUMANLI";
            case "KF": return "TOZ VEYA KUM FIRTINASI";
            case "R": return "RÜZGARLI";
            case "GKR": return "GÜNEYLİ KUVVETLİ RÜZGAR";
            case "KKR": return "KUZEYLİ KUVVETLİ RÜZGAR";
            case "SCK": return "SICAK";
            case "SGK": return "SOĞUK";
            case "HHY": return "YAĞIŞLI";
            default: return "";
        }
    }

    static String wmo(int c) {
        if (c == 0) return "AÇIK";
        if (c <= 2) return "PARÇALI BULUTLU";
        if (c == 3) return "KAPALI";
        if (c == 45 || c == 48) return "SİSLİ";
        if (c >= 51 && c <= 57) return "ÇİSELEME";
        if (c >= 61 && c <= 67) return "YAĞMURLU";
        if (c >= 71 && c <= 77) return "KARLI";
        if (c >= 80 && c <= 82) return "SAĞANAK";
        if (c >= 85 && c <= 86) return "KAR SAĞANAĞI";
        if (c >= 95) return "FIRTINA";
        return "";
    }

    // ================================================================ temizlik

    /** Arka plandaki (gorunmeyen) uygulama sureclerini kapatir. Kumanda uygulamasi ve sistem haric. */
    static int killBackground(Context ctx) {
        ActivityManager am = (ActivityManager) ctx.getSystemService(ACTIVITY_SERVICE);
        int n = 0;
        for (ApplicationInfo ai : ctx.getPackageManager().getInstalledApplications(0)) {
            String p = ai.packageName;
            if (p.equals(ctx.getPackageName()) || p.equals("android")) continue;
            if (p.startsWith("com.android.") || p.startsWith("com.droidlogic") || p.startsWith("com.sdmc")) continue;
            if (p.equals("com.google.android.gms") || p.equals("com.google.android.gsf")) continue;
            if (p.startsWith("zank.remote")) continue; // telefondan kumanda
            if (p.equals("com.google.android.inputmethod.latin")) continue; // klavye
            try { am.killBackgroundProcesses(p); n++; } catch (Exception ignored) { }
        }
        return n;
    }

    void cleanBackground() {
        final ActivityManager am = (ActivityManager) getSystemService(ACTIVITY_SERVICE);
        final ActivityManager.MemoryInfo before = new ActivityManager.MemoryInfo();
        am.getMemoryInfo(before);
        killBackground(this);
        showToast("Kapatılıyor…");
        h.postDelayed(new Runnable() {
            @Override public void run() {
                ActivityManager.MemoryInfo after = new ActivityManager.MemoryInfo();
                am.getMemoryInfo(after);
                long freed = Math.max(0, (after.availMem - before.availMem) / (1024 * 1024));
                showToast("Arka plandaki uygulamalar kapatıldı  ·  " + freed + " MB boşaldı");
                updateMeters();
            }
        }, 1500);
    }

    TextView toast;

    void showToast(String msg) {
        if (toast == null) {
            toast = text(15, Color.WHITE, medium);
            GradientDrawable bg = new GradientDrawable();
            bg.setColor(0xCC1C1C1E);
            bg.setCornerRadius(dp(22));
            toast.setBackground(bg);
            toast.setPadding(dp(22), dp(12), dp(22), dp(12));
            FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(-2, -2, Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
            lp.bottomMargin = dp(36);
            ((FrameLayout) scroll.getParent()).addView(toast, lp);
            toast.setAlpha(0f);
        }
        toast.setText(msg);
        toast.animate().cancel();
        toast.animate().alpha(1f).setDuration(180).start();
        h.removeCallbacks(hideToast);
        h.postDelayed(hideToast, 3500);
    }

    final Runnable hideToast = new Runnable() {
        @Override public void run() { if (toast != null) toast.animate().alpha(0f).setDuration(300).start(); }
    };

    // ================================================================ acilis selami

    android.speech.tts.TextToSpeech tts;
    // Turkce ses Ingilizce "Hi" demesi icin okunusuyla yazildi
    String greetSpoken() { return cfg("greet_spoken", ""); }
    String greetShown() { return cfg("greet_shown", ""); }
    static final String[] MALE_VOICES = {"tr-tr-x-mfm", "tr-tr-x-tmc"};

    void greet() {
        if (greetSpoken().isEmpty()) return;
        if (tts != null) { try { tts.shutdown(); } catch (Exception ignored) { } }
        tts = new android.speech.tts.TextToSpeech(this, new android.speech.tts.TextToSpeech.OnInitListener() {
            @Override public void onInit(int status) {
                if (status != android.speech.tts.TextToSpeech.SUCCESS) {
                    android.util.Log.w("TVHOME", "TTS init failed " + status);
                    return;
                }
                Locale tr = new Locale("tr", "TR");
                int lang = tts.setLanguage(tr);
                android.util.Log.i("TVHOME", "setLanguage tr = " + lang);
                android.speech.tts.Voice chosen = null;
                int best = 999;
                try {
                    for (android.speech.tts.Voice v : tts.getVoices()) {
                        if (!"tr".equals(v.getLocale().getLanguage())) continue;
                        android.util.Log.i("TVHOME", "voice " + v.getName() + " net=" + v.isNetworkConnectionRequired()
                                + " feat=" + v.getFeatures());
                        int m = indexOf(MALE_VOICES, v.getName());
                        if (m == 99) continue;
                        boolean installed = !v.getFeatures().contains("notInstalled");
                        // puan: kurulu yerel ses en iyi, sonra internet sesi, sonra kurulu olmayan yerel
                        int score = m * 10 + (installed && !v.isNetworkConnectionRequired() ? 0
                                : v.isNetworkConnectionRequired() ? 3 : 6);
                        if (score < best) { best = score; chosen = v; }
                    }
                } catch (Exception ignored) { }
                String saved = sp.getString("voiceName", null);
                if (saved != null) {
                    try {
                        for (android.speech.tts.Voice v : tts.getVoices())
                            if (v.getName().equals(saved)) chosen = v;
                    } catch (Exception ignored) { }
                }
                if (chosen != null) {
                    tts.setVoice(chosen);
                    tts.setPitch(sp.getFloat("voicePitch", 0.9f));
                    android.util.Log.i("TVHOME", "chosen " + chosen.getName());
                } else {
                    tts.setPitch(0.7f);
                }
                tts.setOnUtteranceProgressListener(new android.speech.tts.UtteranceProgressListener() {
                    @Override public void onStart(String id) { android.util.Log.i("TVHOME", "speak start " + id); }
                    @Override public void onDone(String id) { android.util.Log.i("TVHOME", "speak done " + id); }
                    @Override public void onError(String id) { onError(id, -1); }
                    @Override public void onError(String id, int code) {
                        android.util.Log.w("TVHOME", "speak error " + id + " " + code);
                        if (!"retry".equals(id)) {
                            // secilen ses calismadiysa varsayilan Turkce sesle, kalin tonla tekrar dene
                            tts.setLanguage(new Locale("tr", "TR"));
                            tts.setPitch(0.7f);
                            tts.speak(greetSpoken(),
                                    android.speech.tts.TextToSpeech.QUEUE_FLUSH, null, "retry");
                        }
                    }
                });
                tts.setSpeechRate(0.95f);
                h.postDelayed(new Runnable() {
                    @Override public void run() {
                        tts.speak(greetSpoken(),
                                android.speech.tts.TextToSpeech.QUEUE_FLUSH, null, "greet");
                        showToast(greetShown() + " 👋");
                    }
                }, waitNet());
            }
        }, "com.google.android.tts");
    }

    /** adb ile: --ez voicetest true  (sesleri sirayla dinlet)  /  --es setvoice <ad> --ef pitch 0.8 */
    void handleVoiceExtras(Intent in) {
        if (in == null) return;
        if (in.getExtras() != null) {
            SharedPreferences.Editor ed = sp.edit();
            boolean any = false;
            for (String k : in.getExtras().keySet()) {
                if (k.startsWith("cfg_")) {
                    String v = String.valueOf(in.getExtras().get(k));
                    if (v.startsWith("b64:")) {
                        try { v = new String(android.util.Base64.decode(v.substring(4), android.util.Base64.DEFAULT), "UTF-8"); }
                        catch (Exception ignored) { }
                    }
                    ed.putString(k, v);
                    any = true;
                }
            }
            if (any) {
                ed.remove("mgmIst").apply();
                fetchWeather();
            }
        }
        if (in.getBooleanExtra("checkupdate", false)) Updater.check(this, true);
        if (in.hasExtra("setvoice")) {
            sp.edit().putString("voiceName", in.getStringExtra("setvoice"))
                    .putFloat("voicePitch", in.getFloatExtra("pitch", 0.9f)).apply();
            greet();
        }
        if (in.getBooleanExtra("voicetest", false)) voiceTest();
    }

    void voiceTest() {
        final android.speech.tts.TextToSpeech[] t = new android.speech.tts.TextToSpeech[1];
        t[0] = new android.speech.tts.TextToSpeech(this, new android.speech.tts.TextToSpeech.OnInitListener() {
            @Override public void onInit(int status) {
                if (status != android.speech.tts.TextToSpeech.SUCCESS) return;
                final List<android.speech.tts.Voice> list = new ArrayList<>();
                try {
                    for (android.speech.tts.Voice v : t[0].getVoices())
                        if ("tr".equals(v.getLocale().getLanguage()) && v.getName().contains("-x-")
                                && !v.isNetworkConnectionRequired()) list.add(v);
                } catch (Exception ignored) { }
                Collections.sort(list, new Comparator<android.speech.tts.Voice>() {
                    @Override public int compare(android.speech.tts.Voice a, android.speech.tts.Voice b) {
                        return a.getName().compareTo(b.getName());
                    }
                });
                String[] nums = {"Bir", "İki", "Üç", "Dört", "Beş", "Altı", "Yedi", "Sekiz"};
                for (int i = 0; i < list.size() && i < nums.length; i++) {
                    final android.speech.tts.Voice v = list.get(i);
                    final int n = i + 1;
                    final String word = nums[i];
                    h.postDelayed(new Runnable() {
                        @Override public void run() {
                            t[0].setVoice(v);
                            t[0].setPitch(1.0f);
                            android.util.Log.i("TVHOME", "test " + n + " = " + v.getName());
                            showToast("Ses " + n);
                            t[0].speak("Ses " + word + ". Merhaba", android.speech.tts.TextToSpeech.QUEUE_FLUSH, null, "t" + n);
                        }
                    }, 1000 + i * 4500L);
                }
            }
        }, "com.google.android.tts");
    }

    /** Acilista internet gelene kadar biraz bekle (en fazla ~12 sn). */
    long waitNet() {
        try {
            android.net.ConnectivityManager cm = (android.net.ConnectivityManager) getSystemService(CONNECTIVITY_SERVICE);
            android.net.NetworkInfo ni = cm.getActiveNetworkInfo();
            if (ni != null && ni.isConnected()) return 800;
        } catch (Exception ignored) { }
        return 6000;
    }

    static int indexOf(String[] arr, String name) {
        for (int i = 0; i < arr.length; i++) if (name.startsWith(arr[i])) return i;
        return 99;
    }

    // ================================================================ uygulama ekle

    void addMenu() {
        final List<String> opts = new ArrayList<>();
        opts.add("Ana şeride (dock) uygulama ekle");
        opts.add("Play Store'dan yeni uygulama yükle");
        opts.add("Dosyadan / USB'den APK yükle");
        opts.add("Ana ekran güncellemelerini denetle  (sürüm " + Updater.myVersion(this) + ")");
        final Set<String> hidden = sp.getStringSet("hidden", DEFAULT_HIDDEN);
        if (!hidden.isEmpty()) opts.add("Gizlenen uygulamaları geri getir (" + hidden.size() + ")");
        new PanelBuilder()
                .setTitle("Uygulama ekle")
                .setItems(opts.toArray(new String[0]), new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) {
                        String o = opts.get(w);
                        if (o.startsWith("Ana şeride")) pickForDock();
                        else if (o.startsWith("Play Store")) openPkg("com.android.vending", "Play Store bulunamadı");
                        else if (o.startsWith("Dosyadan")) {
                            showToast("APK dosyasını dosya yöneticisinde seçin");
                            openPkg("com.alphainventor.filemanager", "Dosya yöneticisi bulunamadı");
                        } else if (o.startsWith("Ana ekran güncellemelerini")) {
                            Updater.check(MainActivity.this, true);
                        } else if (o.startsWith("Gizlenen")) {
                            sp.edit().putStringSet("hidden", new HashSet<String>()).apply();
                            loadApps();
                            showToast("Gizlenen uygulamalar geri geldi");
                        }
                    }
                }).show();
    }

    void openPkg(String pkg, String err) {
        PackageManager pm = getPackageManager();
        Intent i = pm.getLeanbackLaunchIntentForPackage(pkg);
        if (i == null) i = pm.getLaunchIntentForPackage(pkg);
        if (i == null) { showToast(err); return; }
        try { startActivity(i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); } catch (Exception e) { showToast(err); }
    }

    void pickForDock() {
        final List<AppItem> rest = new ArrayList<>();
        for (int i = DOCK; i < apps.size(); i++) rest.add(apps.get(i));
        if (rest.isEmpty()) { showToast("Eklenecek başka uygulama yok"); return; }
        String[] names = new String[rest.size()];
        for (int i = 0; i < rest.size(); i++) names[i] = rest.get(i).label;
        new PanelBuilder()
                .setTitle("Ana şeride eklenecek uygulama")
                .setItems(names, new DialogInterface.OnClickListener() {
                    @Override public void onClick(DialogInterface d, int w) {
                        AppItem a = rest.get(w);
                        move(apps.indexOf(a), DOCK - 1);
                        showToast(a.label + " ana şeride eklendi");
                    }
                }).show();
    }

    // ================================================================ koyu menu paneli

    FrameLayout rootView;
    View panel;
    View panelTop, topBarView;

    class PanelBuilder {
        String title;
        String[] items;
        DialogInterface.OnClickListener cb;
        PanelBuilder setTitle(String t) { title = t; return this; }
        PanelBuilder setItems(String[] i, DialogInterface.OnClickListener c) { items = i; cb = c; return this; }
        void show() { showPanel(title, items, cb); }
    }

    void showPanel(String title, final String[] items, final DialogInterface.OnClickListener cb) {
        closePanel();
        final View prevFocus = getCurrentFocus();
        FrameLayout dim = new FrameLayout(this);
        dim.setBackgroundColor(0xB3000000);
        dim.setClickable(true);

        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(0xF21C1C1E);
        bg.setCornerRadius(dp(22));
        bg.setStroke(Math.max(1, dp(0.75f)), 0x33FFFFFF);
        card.setBackground(bg);
        card.setPadding(dp(14), dp(18), dp(14), dp(14));

        TextView t = text(18, Color.WHITE, medium);
        t.setText(title);
        t.setPadding(dp(12), 0, dp(12), dp(12));
        card.addView(t);

        LinearLayout list = new LinearLayout(this);
        list.setOrientation(LinearLayout.VERTICAL);
        View first = null;
        for (int i = 0; i < items.length; i++) {
            final int which = i;
            final TextView row = text(15, 0xE6FFFFFF, regular);
            row.setText(items[i]);
            row.setSingleLine(true);
            row.setEllipsize(TextUtils.TruncateAt.END);
            row.setPadding(dp(14), dp(11), dp(14), dp(11));
            row.setFocusable(true);
            row.setClickable(true);
            final GradientDrawable rb = new GradientDrawable();
            rb.setCornerRadius(dp(12));
            rb.setColor(0x00000000);
            row.setBackground(rb);
            row.setOnFocusChangeListener(new View.OnFocusChangeListener() {
                @Override public void onFocusChange(View v, boolean has) {
                    rb.setColor(has ? 0xFFFFFFFF : 0x00000000);
                    row.setTextColor(has ? 0xFF111111 : 0xE6FFFFFF);
                }
            });
            row.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View v) {
                    closePanel();
                    cb.onClick(null, which);
                }
            });
            list.addView(row, new LinearLayout.LayoutParams(-1, -2));
            if (first == null) first = row;
        }
        ScrollView sv = new ScrollView(this);
        sv.setVerticalScrollBarEnabled(false);
        sv.addView(list);
        int maxH = getResources().getDisplayMetrics().heightPixels - dp(170);
        list.measure(View.MeasureSpec.makeMeasureSpec(dp(400), View.MeasureSpec.EXACTLY), View.MeasureSpec.UNSPECIFIED);
        int h0 = Math.min(maxH, list.getMeasuredHeight());
        card.addView(sv, new LinearLayout.LayoutParams(-1, h0));

        dim.addView(card, new FrameLayout.LayoutParams(dp(430), -2, Gravity.CENTER));
        scroll.setDescendantFocusability(ViewGroup.FOCUS_BLOCK_DESCENDANTS);
        panelTop = topBarView;
        if (panelTop instanceof ViewGroup) ((ViewGroup) panelTop).setDescendantFocusability(ViewGroup.FOCUS_BLOCK_DESCENDANTS);
        rootView.addView(dim, match());
        panel = dim;
        panel.setTag(prevFocus);
        dim.setAlpha(0f);
        dim.animate().alpha(1f).setDuration(160).start();
        if (first != null) first.requestFocus();
    }

    void closePanel() {
        if (panel == null) return;
        View prev = (View) panel.getTag();
        rootView.removeView(panel);
        panel = null;
        scroll.setDescendantFocusability(ViewGroup.FOCUS_AFTER_DESCENDANTS);
        if (panelTop instanceof ViewGroup) ((ViewGroup) panelTop).setDescendantFocusability(ViewGroup.FOCUS_AFTER_DESCENDANTS);
        if (prev != null && prev.isAttachedToWindow()) prev.requestFocus();
    }

    /** Ayarlar gibi ekranlar arkada sistem duvar kagidini gosterir; ayni resmi oraya da koy. */
    void syncSystemWallpaper(final Bitmap wp) {
        final int sig = wp.getWidth() * 31 + wp.getHeight() * 17 + wp.getPixel(wp.getWidth() / 2, wp.getHeight() / 2);
        if (sp.getInt("sysWallpaperSig", 0) == sig) return;
        new Thread(new Runnable() {
            @Override public void run() {
                try {
                    android.app.WallpaperManager.getInstance(MainActivity.this).setBitmap(wp);
                    sp.edit().putInt("sysWallpaperSig", sig).apply();
                    android.util.Log.i("TVHOME", "system wallpaper set");
                } catch (Exception e) {
                    android.util.Log.w("TVHOME", "wallpaper failed " + e);
                }
            }
        }).start();
    }
}
