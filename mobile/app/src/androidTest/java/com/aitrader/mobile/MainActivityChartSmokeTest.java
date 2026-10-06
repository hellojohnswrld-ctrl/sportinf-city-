package com.aitrader.mobile;

import static org.junit.Assert.assertTrue;

import android.webkit.WebView;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Test;
import org.junit.runner.RunWith;

import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

@RunWith(AndroidJUnit4.class)
public class MainActivityChartSmokeTest {
    @Test
    public void launchesAndInitializesLocalTradingViewChart() throws Exception {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            CountDownLatch ready = new CountDownLatch(1);
            AtomicReference<String> result = new AtomicReference<>("");

            scenario.onActivity(activity -> {
                WebView webView = activity.chartView;
                webView.evaluateJavascript(
                        "(typeof LightweightCharts)+ '|' + (typeof window.setChartData)+ '|' + document.getElementById('status').textContent",
                        value -> {
                            result.set(value);
                            ready.countDown();
                        });
            });

            assertTrue("WebView chart did not initialize", ready.await(10, TimeUnit.SECONDS));
            String value = result.get();
            assertTrue("Lightweight Charts library missing: " + value, value.contains("object"));
            assertTrue("setChartData bridge missing: " + value, value.contains("function"));
        }
    }

    @Test
    public void chartAcceptsM1DataAndUpdatesStatus() throws Exception {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            CountDownLatch ready = new CountDownLatch(1);
            AtomicReference<String> result = new AtomicReference<>("");

            scenario.onActivity(activity -> {
                WebView webView = activity.chartView;
                String js =
                        "(function(){"
                        + "if(typeof LightweightCharts!=='object'||typeof window.setChartData!=='function') return 'NOT_READY';"
                        + "window.setChartData({"
                        + "chart:[{t:1730000000,o:100,h:102,l:99,c:101},{t:1730000060,o:101,h:103,l:100,c:102}],"
                        + "forecastDirection:'BUY',forecastConfidence:82,forecastUpper:105,forecastLower:98,forecastPrice:104"
                        + "});"
                        + "return document.getElementById('status').textContent;"
                        + "})()";
                webView.evaluateJavascript(js, value -> {
                    result.set(value);
                    ready.countDown();
                });
            });

            assertTrue("Chart data call timed out", ready.await(10, TimeUnit.SECONDS));
            assertTrue("Chart did not accept live-style data: " + result.get(), result.get().contains("BUY"));
            assertTrue("Chart status did not show confidence: " + result.get(), result.get().contains("82"));
        }
    }
}
