package com.aitrader.mobile;

import android.app.Activity;
import android.content.SharedPreferences;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.Typeface;
import android.os.Bundle;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

public class MainActivity extends Activity {
    static final String APP_VERSION = "1.1.0";
    static final String API_BASE_URL = "https://ai-liquidity-trader-bridge.onrender.com";
    static final String DEFAULT_SYMBOL = "";
    static final String PREFS = "ai_liquidity_trader";

    LinearLayout root;
    TextView state, strength, forecast, entry, guardian, connection, symbolView;
    EditText symbolInput, tokenInput;
    LiveChartView chartView;
    ScheduledExecutorService executor;
    SharedPreferences prefs;

    int dp(int n) { return (int)(n * getResources().getDisplayMetrics().density + .5f); }

    TextView text(String value, float size, int color) {
        TextView t = new TextView(this);
        t.setText(value); t.setTextSize(size); t.setTextColor(color);
        t.setPadding(dp(12), dp(8), dp(12), dp(8));
        return t;
    }

    TextView card(String title, String value) {
        TextView t = text(title + "\n" + value, 16, Color.WHITE);
        t.setBackgroundColor(Color.rgb(17,23,34));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, dp(5), 0, dp(5)); root.addView(t, lp); return t;
    }

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        build();
        startPolling();
    }

    void build() {
        ScrollView scroll = new ScrollView(this);
        root = new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(14), dp(18), dp(14), dp(20)); root.setBackgroundColor(Color.rgb(8,11,16));

        TextView title = text("AI LIQUIDITY TRADER", 24, Color.WHITE); title.setTypeface(Typeface.DEFAULT, Typeface.BOLD); root.addView(title);
        root.addView(text("LIVE MT5 MOBILE COMMAND CENTER • V4.12", 12, Color.LTGRAY));
        connection = text("● CONNECTING",12,Color.YELLOW); root.addView(connection);

        LinearLayout config = new LinearLayout(this); config.setOrientation(LinearLayout.HORIZONTAL);
        symbolInput = new EditText(this); symbolInput.setHint("Symbol e.g. XAUUSD"); symbolInput.setText(prefs.getString("symbol", DEFAULT_SYMBOL)); symbolInput.setTextColor(Color.WHITE); symbolInput.setHintTextColor(Color.GRAY);
        tokenInput = new EditText(this); tokenInput.setHint("Private bridge token"); tokenInput.setText(prefs.getString("token", "")); tokenInput.setTextColor(Color.WHITE); tokenInput.setHintTextColor(Color.GRAY); tokenInput.setInputType(0x00000081);
        config.addView(symbolInput, new LinearLayout.LayoutParams(0, dp(54), 0.34f)); config.addView(tokenInput, new LinearLayout.LayoutParams(0, dp(54), 0.66f)); root.addView(config);
        Button connect = new Button(this); connect.setText("CONNECT LIVE MT5"); connect.setOnClickListener(v -> { saveConfig(); pollOnce(); }); root.addView(connect);

        symbolView = card("SYMBOL", "--");
        state = card("SIGNAL", "WAIT"); strength = card("STRENGTH", "-- / 100");
        forecast = card("15-MIN FORECAST", "--"); entry = card("ENTRY / SL / TP", "--"); guardian = card("GUARDIAN / MARGIN", "--");
        chartView = new LiveChartView(); LinearLayout.LayoutParams chartLp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(260)); chartLp.setMargins(0,dp(8),0,dp(8)); root.addView(chartView, chartLp);
        root.addView(text("Auto-trading remains OFF. MT5 remains the trading engine; this app receives its live state and chart data.",12,Color.LTGRAY));

        scroll.addView(root); setContentView(scroll);
    }

    void saveConfig() { prefs.edit().putString("symbol", symbolInput.getText().toString().trim()).putString("token", tokenInput.getText().toString().trim()).apply(); }
    String symbol() { return symbolInput.getText().toString().trim(); }
    String token() { return tokenInput.getText().toString().trim(); }

    void startPolling() {
        executor = Executors.newSingleThreadScheduledExecutor();
        executor.scheduleAtFixedRate(this::pollOnce, 1, 2, TimeUnit.SECONDS);
    }

    void pollOnce() {
        String sym=symbol(); String tok=token();
        if (sym.isEmpty() || tok.isEmpty()) { runOnUiThread(() -> connection.setText("● SET SYMBOL + PRIVATE TOKEN")); return; }
        try {
            URL u = new URL(API_BASE_URL + "/v1/mobile/state?symbol=" + java.net.URLEncoder.encode(sym, "UTF-8"));
            HttpURLConnection c=(HttpURLConnection)u.openConnection(); c.setRequestProperty("Authorization","Bearer "+tok); c.setConnectTimeout(5000); c.setReadTimeout(5000);
            BufferedReader r=new BufferedReader(new InputStreamReader(c.getInputStream())); StringBuilder b=new StringBuilder(); String line; while((line=r.readLine())!=null)b.append(line);
            JSONObject j=new JSONObject(b.toString()); runOnUiThread(() -> render(j)); c.disconnect();
        } catch(Exception e) { runOnUiThread(() -> connection.setText("● BRIDGE OFFLINE / NO MT5 DATA")); }
    }

    void render(JSONObject j) {
        String s=j.optString("state","WAIT"); symbolView.setText("SYMBOL\n"+j.optString("symbol","--"));
        connection.setText("● LIVE MT5 • "+j.optString("symbol","MT5")); connection.setTextColor(Color.rgb(53,208,127));
        state.setText("SIGNAL\n"+s); state.setTextColor(s.equals("BUY")?Color.rgb(53,208,127):s.equals("SELL")?Color.rgb(255,92,102):Color.rgb(255,209,102));
        strength.setText("STRENGTH\n"+j.optInt("strength",0)+" / 100");
        forecast.setText("15-MIN FORECAST\n"+j.optString("forecastDirection","NEUTRAL")+" • "+j.optInt("forecastConfidence",0)+"/100 • "+j.optInt("forecastMinutes",15)+" MIN");
        entry.setText("ENTRY / SL / TP\n"+num(j,"entry")+" | SL "+num(j,"sl")+" | TP1 "+num(j,"tp1")+" | TP2 "+num(j,"tp2"));
        guardian.setText("GUARDIAN / MARGIN\n"+j.optString("guardian","--")+" • Margin "+j.optString("marginLevel","--")+" • Equity "+j.optString("equity","--"));
        chartView.setData(j);
    }

    String num(JSONObject j,String k){ double v=j.optDouble(k,Double.NaN); return Double.isNaN(v)?"--":String.valueOf(v); }
    @Override protected void onDestroy(){ if(executor!=null)executor.shutdownNow(); super.onDestroy(); }

    class LiveChartView extends View {
        Paint p=new Paint(Paint.ANTI_ALIAS_FLAG); Paint line=new Paint(Paint.ANTI_ALIAS_FLAG);
        List<Double> prices=new ArrayList<>(); String direction="NEUTRAL"; double upper,lower,target; int confidence;
        LiveChartView(){ super(MainActivity.this); setBackgroundColor(Color.rgb(12,17,25)); }
        void setData(JSONObject j){ prices.clear(); try{ JSONArray a=j.optJSONArray("chart"); if(a!=null) for(int i=0;i<a.length();i++) prices.add(a.getJSONObject(i).optDouble("p")); }catch(Exception ignored){} direction=j.optString("forecastDirection","NEUTRAL"); upper=j.optDouble("forecastUpper",0); lower=j.optDouble("forecastLower",0); target=j.optDouble("forecastPrice",0); confidence=j.optInt("forecastConfidence",0); invalidate(); }
        @Override protected void onDraw(Canvas c){
            super.onDraw(c);
            if(prices.size()<2){p.setColor(Color.LTGRAY); p.setTextSize(dp(12)); c.drawText("Waiting for live MT5 chart data…",dp(14),dp(32),p); return;}
            double min=prices.get(0),max=prices.get(0); for(double v:prices){min=Math.min(min,v);max=Math.max(max,v);} if(upper>0)max=Math.max(max,upper); if(lower>0)min=Math.min(min,lower);
            double pad=(max-min)*0.08; if(pad<=0)pad=1; min-=pad;max+=pad; float w=getWidth(),h=getHeight();
            line.setStyle(Paint.Style.STROKE); line.setStrokeWidth(dp(2)); line.setColor(direction.equals("BULLISH")?Color.rgb(53,208,127):direction.equals("BEARISH")?Color.rgb(255,92,102):Color.rgb(255,209,102));
            Path path=new Path(); for(int i=0;i<prices.size();i++){float x=(w-20)*i/(float)(prices.size()-1)+10;float y=(float)(h-20-(prices.get(i)-min)/(max-min)*(h-40));if(i==0)path.moveTo(x,y);else path.lineTo(x,y);} c.drawPath(path,line);
            if(!direction.equals("NEUTRAL")&&upper>0&&lower>0){p.setColor(direction.equals("BULLISH")?Color.argb(45,53,208,127):Color.argb(45,255,92,102));float y1=(float)(h-20-(upper-min)/(max-min)*(h-40));float y2=(float)(h-20-(lower-min)/(max-min)*(h-40));c.drawRect(10,Math.min(y1,y2),w-10,Math.max(y1,y2),p);line.setColor(Color.LTGRAY);line.setStrokeWidth(1);float yt=(float)(h-20-(target-min)/(max-min)*(h-40));c.drawLine(10,yt,w-10,yt,line);}
            p.setColor(Color.WHITE);p.setTextSize(dp(12));c.drawText("LIVE M1 • "+direction+" "+confidence+"%",dp(12),dp(18),p);
        }
    }
}