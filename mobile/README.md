# AI Liquidity Trader Mobile

Private Android companion for the MT5 AI Liquidity Trader.

The mobile app is designed as a permanent update-ready space. The MT5/VPS remains the analysis/trading engine; the Android app displays live state through a private API bridge.

## Mobile display
- BUY / SELL / WAIT
- 15-minute forecast
- strength and confidence
- entry, SL, TP1, TP2
- Guardian and margin state
- update-ready versioning

## Live API contract
The app expects JSON like:
{"symbol":"XAUUSD","state":"BUY","strength":74,"forecastDirection":"BULLISH","forecastConfidence":78,"forecastMinutes":15,"entry":"4254.92","sl":"4287.91","tp1":"4304.44","tp2":"4337.45","guardian":"OK","marginLevel":"512%"}

The API endpoint is intentionally left blank until the private backend is connected.

## Update manifest
A future update endpoint can return:
{"version":"1.1.0","apkUrl":"https://example.com/app.apk","notes":"Mobile update"}

## Build
GitHub Actions builds the APK automatically. Future releases should increment versionCode/versionName.

Build trigger verification: 2026-10-01.
