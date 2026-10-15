package com.aitrader.mobile;

import android.Manifest;
import android.app.Activity;
import android.app.ActivityManager;
import android.app.AlertDialog;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.Typeface;
import android.os.Build;
import android.os.Bundle;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import androidx.webkit.WebViewAssetLoader;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

public class MainActivity extends Activity {
    static final String APP_VERSION = "2.3.1";
    static final String API_BASE_URL = "https://ai-liquidity-trader-bridge-v2.onrender.com";
    static final String PREFS = "ai_liquidity_trader";
    static final String KEY_ALIAS = "ai_liquidity_trader_token";
    static final String CHANNEL_ID = "ai_trader_alerts";

    LinearLayout root;
    TextView state, strength, forecast, entry, guardian, account, positions, connection, symbolView, mobileMode;
    EditText symbolInput, tokenInput;
    WebView chartView;
    boolean chartReady=false;
    String pendingChartJson=null;
    ScheduledExecutorService executor;
    SharedPreferences prefs;
    String lastState = "";
    long lastSignalTimestamp = 0;
    volatile boolean pollInFlight = false;

    int dp(int n) { return (int)(n * getResources().getDisplayMetrics().density + .5f); }

    TextView text(String value, float size, int color) {
        TextView t = new TextView(this);
        t.setText(value); t.setTextSize(size); t.setTextColor(color);
        t.setPadding(dp(12), dp(8), dp(12), dp(8));
        return t;
    }

    TextView card(String title, String value) {
        TextView t = text(title + "\n" + value, 15, Color.WHITE);
        t.setBackgroundColor(Color.rgb(17,23,34));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, dp(5), 0, dp(5)); root.addView(t, lp); return t;
    }

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        createNotificationChannel();
        build();
    }

    void build() {
        ScrollView scroll = new ScrollView(this);
        root = new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(14), dp(18), dp(14), dp(20)); root.setBackgroundColor(Color.rgb(8,11,16));

        TextView title = text("AI LIQUIDITY TRADER", 25, Color.WHITE);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD); root.addView(title);
        root.addView(text("LIVE MT5 COMMAND CENTER • V2.0", 12, Color.LTGRAY));
        connection = text("● CONNECTING",12,Color.YELLOW); root.addView(connection);

        LinearLayout config = new LinearLayout(this); config.setOrientation(LinearLayout.HORIZONTAL);
        symbolInput = new EditText(this);
        symbolInput.setHint("Symbol e.g. XAUUSD"); symbolInput.setText(prefs.getString("symbol", ""));
        symbolInput.setTextColor(Color.WHITE); symbolInput.setHintTextColor(Color.GRAY);
        tokenInput = new EditText(this);
        tokenInput.setHint("Private bridge token"); tokenInput.setTextColor(Color.WHITE); tokenInput.setHintTextColor(Color.GRAY);
        tokenInput.setInputType(0x00000081); tokenInput.setText(decrypt(prefs.getString("token", "")));
        config.addView(symbolInput, new LinearLayout.LayoutParams(0, dp(54), 0.34f));
        config.addView(tokenInput, new LinearLayout.LayoutParams(0, dp(54), 0.66f)); root.addView(config);

        Button connect = new Button(this); connect.setText("CONNECT LIVE MT5");
        connect.setOnClickListener(v -> { saveConfig(); if (executor != null) executor.execute(this::pollOnce); }); root.addView(connect);

        LinearLayout controls = new LinearLayout(this); controls.setOrientation(LinearLayout.HORIZONTAL);
        Button enable = new Button(this); enable.setText("ENABLE");
        Button disable = new Button(this); disable.setText("PAUSE");
        Button refresh = new Button(this); refresh.setText("REFRESH");
        Button close = new Button(this); close.setText("CLOSE ALL");
        enable.setOnClickListener(v -> sendCommand("enable_trading"));
        disable.setOnClickListener(v -> sendCommand("disable_trading"));
        refresh.setOnClickListener(v -> sendCommand("refresh"));
        close.setOnClickListener(v -> new AlertDialog.Builder(this).setTitle("Close all EA positions?")
                .setMessage("This sends a close-all command for the selected symbol and EA magic number.")
                .setNegativeButton("Cancel", null).setPositiveButton("CLOSE", (d,w) -> sendCommand("close_all")).show());
        controls.addView(enable,new LinearLayout.LayoutParams(0,dp(52),1));
        controls.addView(disable,new LinearLayout.LayoutParams(0,dp(52),1));
        controls.addView(refresh,new LinearLayout.LayoutParams(0,dp(52),1));
        controls.addView(close,new LinearLayout.LayoutParams(0,dp(52),1));
        root.addView(controls);

        symbolView = card("SYMBOL", "--");
        state = card("SIGNAL", "WAIT");
        strength = card("STRENGTH", "-- / 100");
        forecast = card("15-MIN FORECAST", "--");
        entry = card("ENTRY / SL / TP", "--");
        guardian = card("GUARDIAN / MARGIN", "--");
        account = card("ACCOUNT", "--");
        mobileMode = card("MOBILE TRADE GATE", "PAUSED");
        positions = card("OPEN POSITIONS", "None");

        chartView = new WebView(this);
        chartView.setBackgroundColor(Color.rgb(12,17,25));
        WebSettings ws = chartView.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setLoadWithOverviewMode(true);
        ws.setUseWideViewPort(true);
        final WebViewAssetLoader assetLoader = new WebViewAssetLoader.Builder()
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                .build();
        chartView.setWebViewClient(new WebViewClient() {
            @Override public android.webkit.WebResourceResponse shouldInterceptRequest(WebView view, android.webkit.WebResourceRequest request) {
                return assetLoader.shouldInterceptRequest(request.getUrl());
            }
            @Override public android.webkit.WebResourceResponse shouldInterceptRequest(WebView view, String url) {
                return assetLoader.shouldInterceptRequest(android.net.Uri.parse(url));
            }
            @Override public void onPageFinished(WebView view, String url) {
                chartReady = true;
                if (pendingChartJson != null) {
                    pushChartJson(pendingChartJson);
                    pendingChartJson = null;
                }
            }
        });
        chartView.loadUrl("https://appassets.androidplatform.net/assets/chart.html");
        LinearLayout.LayoutParams chartLp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(360));
        chartLp.setMargins(0,dp(8),0,dp(8)); root.addView(chartView, 1, chartLp);

        root.addView(text("MT5 remains the trading engine. Mobile commands are safety-gated by the EA; trading stays paused until explicitly enabled.",12,Color.LTGRAY));
        scroll.addView(root); setContentView(scroll);
        requestNotificationPermission();
    }

    void saveConfig() {
        prefs.edit().putString("symbol", symbolInput.getText().toString().trim())
                .putString("token", encrypt(tokenInput.getText().toString().trim())).apply();
    }

    String symbol() { return symbolInput.getText().toString().trim(); }
    String token() { return tokenInput.getText().toString().trim(); }

    void startPolling() {
        if (executor != null && !executor.isShutdown()) return;
        executor = Executors.newSingleThreadScheduledExecutor();
        executor.scheduleAtFixedRate(this::pollOnce, 0, 2, TimeUnit.SECONDS);
    }

    void stopPolling() {
        if (executor != null) {
            executor.shutdownNow();
            executor = null;
        }
        pollInFlight = false;
    }

    void pollOnce() {
        if (pollInFlight) return;
        pollInFlight = true;
        try {
            String sym=symbol(), tok=token();
            if (tok.isEmpty()) {
                runOnUiThread(() -> connection.setText("● SET PRIVATE TOKEN"));
                return;
            }
            if (sym.isEmpty()) {
                String resolved = discoverSymbol(tok, "");
                if (resolved == null) return;
                sym = resolved;
            }
            URL u = new URL(API_BASE_URL + "/v1/mobile/state?symbol=" + URLEncoder.encode(sym, "UTF-8"));
            HttpURLConnection c=(HttpURLConnection)u.openConnection();
            c.setRequestProperty("Authorization","Bearer "+tok);
            c.setConnectTimeout(5000); c.setReadTimeout(5000);
            int code=c.getResponseCode();
            if(code<200 || code>=300) {
                c.disconnect();
                if(code==404) {
                    String resolved = discoverSymbol(tok, sym);
                    if(resolved != null && !resolved.equalsIgnoreCase(sym)) {
                        runOnUiThread(() -> symbolInput.setText(resolved));
                        return;
                    }
                }
                final String status=code==401 ? "AUTH ERROR" : (code==404 ? "NO MT5 DATA • CHECK SYMBOL" : "HTTP "+code);
                runOnUiThread(() -> { connection.setText("● "+status); connection.setTextColor(Color.rgb(255,92,102)); });
                return;
            }
            BufferedReader r=new BufferedReader(new InputStreamReader(c.getInputStream()));
            StringBuilder body=new StringBuilder();
            String line; while((line=r.readLine())!=null) body.append(line);
            r.close(); c.disconnect();
            JSONObject j=new JSONObject(body.toString());
            runOnUiThread(() -> render(j));
        } catch(Exception e) {
            runOnUiThread(() -> {
                String msg = e.getMessage()==null ? "network error" : e.getMessage();
                connection.setText("● BRIDGE ERROR • "+msg);
                connection.setTextColor(Color.rgb(255,92,102));
            });
        } finally {
            pollInFlight = false;
        }
    }

    String discoverSymbol(String tok, String requested) {
        try {
            URL u = new URL(API_BASE_URL + "/v1/mobile/symbols");
            HttpURLConnection c = (HttpURLConnection)u.openConnection();
            c.setRequestProperty("Authorization","Bearer "+tok);
            c.setConnectTimeout(5000); c.setReadTimeout(5000);
            int code=c.getResponseCode();
            if(code<200 || code>=300) {
                final String status=code==401 ? "AUTH ERROR" : "SYMBOL DISCOVERY HTTP "+code;
                runOnUiThread(() -> { connection.setText("● "+status); connection.setTextColor(Color.rgb(255,92,102)); });
                c.disconnect(); return null;
            }
            BufferedReader r=new BufferedReader(new InputStreamReader(c.getInputStream()));
            StringBuilder b=new StringBuilder(); String line;
            while((line=r.readLine())!=null)b.append(line);
            c.disconnect();
            JSONArray a=new JSONObject(b.toString()).optJSONArray("symbols");
            if(a==null || a.length()==0) {
                runOnUiThread(() -> { connection.setText("● WAITING FOR MT5 SYMBOL"); connection.setTextColor(Color.YELLOW); });
                return null;
            }
            String q=requested==null?"":requested.trim();
            String exact=null, partial=null; int partialCount=0;
            for(int i=0;i<a.length();i++) {
                String candidate=a.optString(i,"").trim();
                if(candidate.isEmpty()) continue;
                if(candidate.equalsIgnoreCase(q)) exact=candidate;
                if(!q.isEmpty() && candidate.toLowerCase().contains(q.toLowerCase())) {
                    partial=candidate; partialCount++;
                }
            }
            String resolved=exact!=null?exact:(partialCount==1?partial:null);
            if(resolved==null && q.isEmpty()) resolved=a.optString(0,"").trim();
            if(resolved!=null && !resolved.isEmpty()) {
                prefs.edit().putString("symbol",resolved).apply();
                final String chosen=resolved;
                runOnUiThread(() -> { symbolInput.setText(chosen); connection.setText("● SYMBOL AUTO-DETECTED • "+chosen); });
                return resolved;
            }
            final String msg=q.isEmpty() ? "NO MT5 SYMBOLS" : "NO MATCH FOR "+q;
            runOnUiThread(() -> { connection.setText("● "+msg); connection.setTextColor(Color.rgb(255,209,102)); });
            return null;
        } catch(Exception e) {
            runOnUiThread(() -> { connection.setText("● SYMBOL DISCOVERY ERROR"); connection.setTextColor(Color.rgb(255,92,102)); });
            return null;
        }
    }

    void sendCommand(String action) {
        saveConfig(); String sym=symbol(), tok=token();
        if(sym.isEmpty() || tok.isEmpty()) { connection.setText("● SET SYMBOL + PRIVATE TOKEN"); return; }
        ScheduledExecutorService ex = executor;
        if (ex == null || ex.isShutdown()) { connection.setText("● APP NOT ACTIVE"); return; }
        ex.execute(() -> {
            try {
                URL u=new URL(API_BASE_URL+"/v1/mobile/command");
                HttpURLConnection c=(HttpURLConnection)u.openConnection();
                c.setRequestMethod("POST"); c.setDoOutput(true); c.setRequestProperty("Content-Type","application/json");
                c.setRequestProperty("Authorization","Bearer "+tok); c.setConnectTimeout(5000); c.setReadTimeout(5000);
                String body="{\"symbol\":\""+jsonEscape(sym)+"\",\"action\":\""+jsonEscape(action)+"\"}";
                OutputStream out=c.getOutputStream(); out.write(body.getBytes(StandardCharsets.UTF_8)); out.close();
                int code=c.getResponseCode(); c.disconnect();
                runOnUiThread(() -> connection.setText(code>=200&&code<300 ? "● COMMAND QUEUED: "+action : "● COMMAND FAILED"));
            } catch(Exception e) { runOnUiThread(() -> connection.setText("● COMMAND ERROR")); }
        });
    }

    void render(JSONObject j) {
        String s=j.optString("state","WAIT");
        boolean stale=j.optBoolean("stale",false);
        symbolView.setText("SYMBOL\n"+j.optString("symbol","--"));
        connection.setText(stale ? "● STALE MT5 DATA" : "● LIVE MT5 • "+j.optString("symbol","MT5"));
        connection.setTextColor(stale?Color.rgb(255,209,102):Color.rgb(53,208,127));
        state.setText("SIGNAL\n"+s);
        state.setTextColor(s.equals("BUY")?Color.rgb(53,208,127):s.equals("SELL")?Color.rgb(255,92,102):Color.rgb(255,209,102));
        strength.setText("STRENGTH\n"+j.optInt("strength",0)+" / 100");
        forecast.setText("15-MIN FORECAST\n"+j.optString("forecastDirection","NEUTRAL")+" • "+j.optInt("forecastConfidence",0)+"/100 • "+j.optInt("forecastMinutes",15)+" MIN");
        entry.setText("ENTRY / SL / TP\n"+num(j,"entry")+" | SL "+num(j,"sl")+" | TP1 "+num(j,"tp1")+" | TP2 "+num(j,"tp2"));
        guardian.setText("GUARDIAN / MARGIN\n"+j.optString("guardian","--")+" • Margin "+num(j,"marginLevel")+" • Readiness "+j.optInt("readiness",0)+"/100");
        account.setText("ACCOUNT\nEquity "+num(j,"equity")+" • Balance "+num(j,"balance")+" • Free "+num(j,"freeMargin"));
        boolean enabled=j.optBoolean("mobileTradingEnabled",false);
        mobileMode.setText("MOBILE TRADE GATE\n"+(enabled?"ENABLED":"PAUSED"));
        mobileMode.setTextColor(enabled?Color.rgb(255,209,102):Color.LTGRAY);
        renderPositions(j.optJSONArray("positions"));
        renderChart(j);
        long ts=j.optLong("timestamp",0);
        if(ts!=lastSignalTimestamp && !lastState.isEmpty() && !s.equals(lastState)) notifySignal(j);
        lastSignalTimestamp=ts; lastState=s;
    }

    void renderChart(JSONObject j) {
        String payload = j.toString();
        if (!chartReady) { pendingChartJson = payload; return; }
        pushChartJson(payload);
    }

    void pushChartJson(String payload) {
        chartView.evaluateJavascript("window.setChartData("+payload+");", null);
    }

    void renderPositions(JSONArray a) {
        if(a==null || a.length()==0) { positions.setText("OPEN POSITIONS\nNone"); return; }
        StringBuilder b=new StringBuilder("OPEN POSITIONS\n");
        for(int i=0;i<a.length();i++) try {
            JSONObject p=a.getJSONObject(i);
            b.append(p.optString("type","?")).append("  ")
             .append(p.optDouble("volume",0)).append(" lots  ")
             .append("P/L ").append(p.optDouble("profit",0)).append("\n");
        } catch(Exception ignored){}
        positions.setText(b.toString());
    }

    void notifySignal(JSONObject j) {
        if(Build.VERSION.SDK_INT>=33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED) return;
        NotificationManager nm=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);
        String s=j.optString("state","WAIT");
        android.app.Notification.Builder b=Build.VERSION.SDK_INT>=26
                ?new android.app.Notification.Builder(this,CHANNEL_ID)
                :new android.app.Notification.Builder(this);
        b.setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle("AI Liquidity Trader • "+s)
                .setContentText(j.optString("symbol","MT5")+" strength "+j.optInt("strength",0)+"/100")
                .setAutoCancel(true);
        nm.notify((int)(System.currentTimeMillis()&0x7fffffff),b.build());
    }

    void createNotificationChannel() {
        if(Build.VERSION.SDK_INT>=26) {
            NotificationManager nm=getSystemService(NotificationManager.class);
            nm.createNotificationChannel(new NotificationChannel(CHANNEL_ID,"Trading alerts",NotificationManager.IMPORTANCE_DEFAULT));
        }
    }

    void requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 30 && ActivityManager.isRunningInUserTestHarness()) return;
        if(Build.VERSION.SDK_INT>=33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 1001);
    }

    String num(JSONObject j,String k){ double v=j.optDouble(k,Double.NaN); return Double.isNaN(v)?"--":String.valueOf(v); }
    String jsonEscape(String s){ return s.replace("\\","\\\\").replace("\"","\\\""); }

    String encrypt(String plain) {
        if(plain==null || plain.isEmpty()) return "";
        try {
            KeyStore ks=KeyStore.getInstance("AndroidKeyStore"); ks.load(null);
            if(!ks.containsAlias(KEY_ALIAS)) {
                KeyGenerator kg=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");
                kg.init(new KeyGenParameterSpec.Builder(KEY_ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT)
                        .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
                kg.generateKey();
            }
            SecretKey key=((KeyStore.SecretKeyEntry)ks.getEntry(KEY_ALIAS,null)).getSecretKey();
            Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding"); cipher.init(Cipher.ENCRYPT_MODE,key);
            byte[] iv=cipher.getIV(), enc=cipher.doFinal(plain.getBytes(StandardCharsets.UTF_8));
            return android.util.Base64.encodeToString(join(iv,enc),android.util.Base64.NO_WRAP);
        } catch(Exception e){ return ""; }
    }

    String decrypt(String encoded) {
        if(encoded==null || encoded.isEmpty()) return "";
        try {
            byte[] all=android.util.Base64.decode(encoded,android.util.Base64.NO_WRAP);
            byte[] iv=new byte[12], enc=new byte[all.length-12];
            System.arraycopy(all,0,iv,0,12); System.arraycopy(all,12,enc,0,enc.length);
            KeyStore ks=KeyStore.getInstance("AndroidKeyStore"); ks.load(null);
            if(!ks.containsAlias(KEY_ALIAS)) return "";
            SecretKey key=((KeyStore.SecretKeyEntry)ks.getEntry(KEY_ALIAS,null)).getSecretKey();
            Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding"); cipher.init(Cipher.DECRYPT_MODE,key,new GCMParameterSpec(128,iv));
            return new String(cipher.doFinal(enc),StandardCharsets.UTF_8);
        } catch(Exception e){ return ""; }
    }

    byte[] join(byte[] a,byte[] b){ byte[] out=new byte[a.length+b.length]; System.arraycopy(a,0,out,0,a.length); System.arraycopy(b,0,out,a.length,b.length); return out; }

    @Override protected void onResume() {
        super.onResume();
        startPolling();
    }

    @Override protected void onPause() {
        stopPolling();
        super.onPause();
    }

    @Override protected void onDestroy(){ stopPolling(); if(chartView!=null)chartView.destroy(); super.onDestroy(); }
}
