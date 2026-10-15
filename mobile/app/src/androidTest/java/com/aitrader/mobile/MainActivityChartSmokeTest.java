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
    private String evaluate(ActivityScenario<MainActivity> scenario, String javascript) throws Exception {
        CountDownLatch done = new CountDownLatch(1);
        AtomicReference<String> result = new AtomicReference<>("");
        scenario.onActivity(activity -> activity.chartView.evaluateJavascript(javascript, value -> {
            result.set(value == null ? "" : value);
            done.countDown();
        }));
        assertTrue("WebView JavaScript evaluation timed out", done.await(2, TimeUnit.SECONDS));
        return result.get();
    }

    private String waitForChart(ActivityScenario<MainActivity> scenario) throws Exception {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(10);
        String value = "";
        while (System.nanoTime() < deadline) {
            value = evaluate(scenario,
                    "(typeof LightweightCharts)+'|'+(typeof window.setChartData)+'|'+document.getElementById('status').textContent");
            if (value.contains("object") && value.contains("function")) return value;
            Thread.sleep(150);
        }
        return value;
    }

    @Test
    public void launchesAndInitializesLocalTradingViewChart() throws Exception {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            String value = waitForChart(scenario);
            assertTrue("Lightweight Charts library missing after waiting for WebView load: " + value,
                    value.contains("object"));
            assertTrue("setChartData bridge missing after waiting for WebView load: " + value,
                    value.contains("function"));
        }
    }

    @Test
    public void chartAcceptsM1DataAndUpdatesStatus() throws Exception {
        try (ActivityScenario<MainActivity> scenario = ActivityScenario.launch(MainActivity.class)) {
            String initial = waitForChart(scenario);
            assertTrue("Chart dependencies did not load: " + initial,
                    initial.contains("object") && initial.contains("function"));

            evaluate(scenario,
                    "window.setChartData({"
                    + "chart:[{t:1730000000,o:100,h:102,l:99,c:101},{t:1730000060,o:101,h:103,l:100,c:102}],"
                    + "forecastDirection:'BUY',forecastConfidence:82,forecastUpper:105,forecastLower:98,forecastPrice:104"
                    + "}); 'submitted'");

            long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(10);
            String status = "";
            while (System.nanoTime() < deadline) {
                status = evaluate(scenario, "document.getElementById('status').textContent");
                if (status.contains("BUY") && status.contains("82")) break;
                Thread.sleep(150);
            }
            assertTrue("Chart did not accept live-style data: " + status, status.contains("BUY"));
            assertTrue("Chart status did not show confidence: " + status, status.contains("82"));
        }
    }
}
