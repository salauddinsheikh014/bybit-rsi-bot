import asyncio
import aiohttp
import pandas as pd
import time

# === Static Config ===
TELEGRAM_TOKEN = "8032193032:AAHH8Hi2CjvQdpe3lAfOb2b0iN5rAiPX8wo"  # ✅ তোমার Token
TELEGRAM_CHAT_ID = "7356643408"  # ✅ তোমার Telegram User ID বা Group Chat ID

BYBIT_API_KEY = "McBIskuBcZDHYH1G0J"  # ✅ তোমার API Key (ভবিষ্যতে ব্যবহারের জন্য)
BYBIT_API_SECRET = "My4U8jfqafyJa5gfgBr6U3sQck7KjRxwdDEV"  # ✅ তোমার API Secret (ভবিষ্যতে ব্যবহারের জন্য)

SYMBOLS = ["DOGEUSDT", "PEPEUSDT", "BONKUSDT", "WIFUSDT", "SHIBUSDT", "FLOKIUSDT"]
RSI_PERIOD = 6
RSI_THRESHOLD = 35
INTERVAL = "240"  # 4h
LIMIT = 100
CHECK_INTERVAL = 15  # seconds
alert_sent = {symbol: False for symbol in SYMBOLS}

# === Telegram ===
async def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as session:
        try:
            await session.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text})
        except Exception as e:
            print("Telegram error:", e)

# === RSI Calculation ===
def calculate_rsi(series: pd.Series, period: int = RSI_PERIOD):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.empty else None

# === Bybit Kline Fetch (linear + spot fallback) ===
async def fetch_kline(session, symbol):
    async def get_kline(category):
        url = "https://api.bybit.com/v5/market/kline"
        params = {
            "category": category,
            "symbol": symbol,
            "interval": INTERVAL,
            "limit": str(LIMIT)
        }
        try:
            async with session.get(url, params=params, timeout=10) as resp:
                data = await resp.json()
                if "result" in data and "list" in data["result"]:
                    kline_list = data["result"]["list"]
                    if len(kline_list) < RSI_PERIOD + 1:
                        print(f"⚠️ {symbol} ({category}): Not enough candles ({len(kline_list)})")
                        return pd.Series(dtype=float)
                    closes = [float(k[4]) for k in kline_list]
                    return pd.Series(closes[::-1])
                else:
                    return None
        except Exception as e:
            print(f"❌ {symbol} ({category}): {e}")
            return None

    # Try linear first, then spot
    for category in ["linear", "spot"]:
        series = await get_kline(category)
        if series is not None:
            return symbol, series

    print(f"⚠️ {symbol}: Could not fetch from linear or spot")
    return symbol, pd.Series(dtype=float)

# === Startup Summary ===
async def startup_report():
    msg = "🤖 RSI Bot Started:\n"
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_kline(session, s) for s in SYMBOLS]
        results = await asyncio.gather(*tasks)
        for symbol, series in results:
            rsi = calculate_rsi(series)
            val = f"{rsi:.2f}" if rsi else "N/A"
            msg += f"• {symbol}: RSI={val}\n"
    msg += "\n⏳ Monitoring 4H RSI..."
    await send_telegram(msg)

# === Monitor Loop ===
async def monitor_loop():
    while True:
        async with aiohttp.ClientSession() as session:
            tasks = [fetch_kline(session, s) for s in SYMBOLS]
            results = await asyncio.gather(*tasks)
            for symbol, series in results:
                rsi = calculate_rsi(series)
                if rsi is not None:
                    print(f"{symbol} - RSI: {rsi:.2f}")
                    if rsi < RSI_THRESHOLD and not alert_sent[symbol]:
                        await send_telegram(
                            f"⚠️ RSI Alert!\nPair: {symbol}\nRSI({RSI_PERIOD}): {rsi:.2f}\nTimeframe: 4h"
                        )
                        alert_sent[symbol] = True
                    elif rsi >= RSI_THRESHOLD:
                        alert_sent[symbol] = False
                else:
                    print(f"{symbol} - RSI: N/A (insufficient data)")
        await asyncio.sleep(CHECK_INTERVAL)

# === Main Entry ===
async def main():
    await startup_report()
    await monitor_loop()

# ✅ Main run
if __name__ == "__main__":
    asyncio.run(main())
