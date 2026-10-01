package com.aitrader.mobile;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.Color;
import android.graphics.Typeface;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import org.json.JSONObject;

public class MainActivity extends Activity {
    static final String APP_VERSION = "1.0.0";

    // Connect these later to the private MT5/VPS bridge and update manifest.
    static final String API_URL = "";
    static final String UPDATE_MANIFEST_URL = "";

    LinearLayout root;
    TextView state, strength, forecast, entry, guardian, update, connection;

    int dp(int n) { return (int)(n * getResources().getDisplayMetrics().density + .5f); }

    TextView text(String value, float size, int color) {
        TextView t = new TextView(this);
        t.setText(value);
        t.setTextSize(size);
        t.setTextColor(color);
        t.setPadding(dp(12), dp(8), dp(12), dp(8));
        return t;
    }

    TextView card(String title, String value) {
        TextView t = text(title + "\n" + value, 17, Color.WHITE);
        t.setBackgroundColor(Color.rgb(17,23,34));
        root.addView(t, new LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        return t;
    }

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        build();
        if (API_URL.isEmpty()) demo();
        else poll();
        checkUpdate();
    }

    void build() {
        ScrollView scroll = new ScrollView(this);
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(14), dp(18), dp(14), dp(20));
        root.setBackgroundColor(Color.rgb(8,11,16));

        TextView title = text("AI LIQUIDITY TRADER", 24, Color.WHITE);
        title.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        root.addView(title);
        root.addView(text("Personal mobile command center • V4.12 engine",12,Color.LTGRAY));

        connection = text("● CONNECTING",12,Color.YELLOW);
        root.addView(connection);

        state = card("SIGNAL","WAIT");
        strength = card("STRENGTH","-- / 100");
        forecast = card("15-MIN FORECAST","--");
        entry = card("ENTRY / SL / TP","--");
        guardian = card("GUARDIAN / MARGIN","--");
        update = card("UPDATE SPACE","Checking…");

        root.addView(text(
            "Auto-trading is OFF. The phone is a monitoring/control interface; the MT5/VPS engine remains the source of trading analysis.",
            12, Color.LTGRAY));

        scroll.addView(root);
        setContentView(scroll);
    }

    void demo() {
        connection.setText("● DEMO / BRIDGE NOT CONNECTED");
        connection.setTextColor(Color.YELLOW);
        state.setText("SIGNAL\nWAIT");
        strength.setText("STRENGTH\n63 / 100");
        forecast.setText("15-MIN FORECAST\nWAIT • 15 MIN");
        entry.setText("ENTRY / SL / TP\nConnect the private MT5 bridge");
        guardian.setText("GUARDIAN / MARGIN\nReady • Auto-trading OFF");
    }

    void poll() {
        new Thread(() -> {
            try {
                HttpURLConnection c = (HttpURLConnection)new URL(API_URL).openConnection();
                c.setConnectTimeout(5000);
                c.setReadTimeout(5000);
                BufferedReader r = new BufferedReader(new InputStreamReader(c.getInputStream()));
                StringBuilder b = new StringBuilder();
                String line;
                while ((line=r.readLine()) != null) b.append(line);
                JSONObject j = new JSONObject(b.toString());
                runOnUiThread(() -> render(j));
            } catch (Exception e) {
                runOnUiThread(() -> connection.setText("● BRIDGE OFFLINE"));
            }
        }).start();
    }

    void render(JSONObject j) {
        String s=j.optString("state","WAIT");
        connection.setText("● LIVE • "+j.optString("symbol","MT5"));
        state.setText("SIGNAL\n"+s);
        state.setTextColor(s.equals("BUY")?Color.rgb(53,208,127):
            s.equals("SELL")?Color.rgb(255,92,102):Color.rgb(255,209,102));
        strength.setText("STRENGTH\n"+j.optInt("strength",0)+" / 100");
        forecast.setText("15-MIN FORECAST\n"+
            j.optString("forecastDirection","WAIT")+" • "+
            j.optInt("forecastConfidence",0)+" / 100");
        entry.setText("ENTRY / SL / TP\n"+
            j.optString("entry","--")+" | SL "+j.optString("sl","--")+
            " | TP1 "+j.optString("tp1","--")+" | TP2 "+j.optString("tp2","--"));
        guardian.setText("GUARDIAN / MARGIN\n"+
            j.optString("guardian","Guardian OK")+" • "+
            j.optString("marginLevel","--"));
    }

    void checkUpdate() {
        if (UPDATE_MANIFEST_URL.isEmpty()) {
            update.setText("UPDATE SPACE\nReady • private update server not connected");
            return;
        }
        new Thread(() -> {
            try {
                BufferedReader r = new BufferedReader(
                    new InputStreamReader(new URL(UPDATE_MANIFEST_URL).openStream()));
                StringBuilder b=new StringBuilder(); String line;
                while((line=r.readLine())!=null)b.append(line);
                JSONObject j=new JSONObject(b.toString());
                String v=j.optString("version",APP_VERSION);
                runOnUiThread(() -> update.setText(
                    "UPDATE SPACE\n"+(v.equals(APP_VERSION)?"Up to date • v":"Update available • v")+v));
            } catch(Exception e) {
                runOnUiThread(() -> update.setText("UPDATE SPACE\nCheck unavailable • v"+APP_VERSION));
            }
        }).start();
    }
}
