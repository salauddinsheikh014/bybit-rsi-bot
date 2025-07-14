import asyncio
import aiohttp
import pandas as pd
import os

# === Environment Variables ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET")

# === Settings ===
SYMBOLS = ["DOGEUSDT", "PEPEUSDT", "BONKUSDT", "WIFUSDT", "SHIBUSDT", "FLOKIUSDT", "ELONUSDT"]
RSI_PERIOD = 6
RSI_THRESHOLD = 35
INTERVAL = "240"  # 4h candle
LIMIT = 100
CHECK_INTERVAL = 15  # seconds
alert_sent = {symbol: False for symbol in SYMBOLS}

# === Telegram Send ===
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

# === Bybit Candle Fetch ===
async def fetch_kline(session, symbol):
    url = "https://api.bybit.com/v5/market/kline"
    params = {
        "category": "linear",
        "symbol": symbol,
        "interval": INTERVAL,
        "limit": str(LIMIT)
    }
    try:
        async with session.get(url, params=params, timeout=10) as resp:
            data = await resp.json()
            if "result" in data and "list" in data["result"]:
                closes = [float(k[4]) for k in data["result"]["list"]]
                return symbol, pd.Series(closes[::-1])
    except Exception as e:
        print(f"❌ {symbol}: {e}")
    return symbol, pd.Series(dtype=float)

# === Startup Report ===
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

# === RSI Monitor Loop ===
async def monitor_loop():
    while True:
        async with aiohttp.ClientSession() as session:
            tasks = [fetch_kline(session, s) for s in SYMBOLS]
            results = await asyncio.gather(*tasks)
            for symbol, series in results:
                rsi = calculate_rsi(series)
                if rsi:
                    print(f"{symbol} - RSI: {rsi:.2f}")
                    if rsi < RSI_THRESHOLD and not alert_sent[symbol]:
                        await send_telegram(
                            f"⚠️ RSI Alert!\nPair: {symbol}\nRSI({RSI_PERIOD}): {rsi:.2f}\nTimeframe: 4h"
                        )
                        alert_sent[symbol] = True
                    elif rsi >= RSI_THRESHOLD:
                        alert_sent[symbol] = False
        await asyncio.sleep(CHECK_INTERVAL)

# === Entry Point ===
async def main():
    await startup_report()
    await monitor_loop()

if __name__ == "__main__":
    asyncio.run(main())
