import re
import time
import asyncio
import requests
from datetime import datetime, timezone
from playwright.async_api import async_playwright

# ==============================
# Конфигурация
# ==============================
URL = "https://hyperion.xyz/vault/0xab8fdae5dd99a4379362c01218cd7aef40758cd8111d11853ce6efd2f82b7cad?poolId=0xd3894aca06d5f42b27c89e6f448114b3ed6a1ba07f992a58b2126c71dd83c127"
THRESHOLD = 1000          # пороговое значение в USDC
CHECK_INTERVAL = 300      # интервал проверки в секундах (5 минут)

TG_TOKEN = "8344264816:AAEgvBxAd8j3D8oIV8tqGYp6qorhY02DTuU"
TG_CHAT_ID = "2135324647"

STATE_FILE = "/tmp/hyperion_cap_state.txt"

# ==============================
# Логика
# ==============================
def parse_money(text: str) -> float:
    m = re.findall(r"\$\s*([0-9][0-9,]*\.?[0-9]*)", text)
    if not m:
        raise ValueError("Не найдено значение $... в тексте блока")
    return float(m[-1].replace(",", ""))

def send_telegram(msg: str):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TG_CHAT_ID, "text": msg, "disable_web_page_preview": True}, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print("Ошибка отправки в Телеграм:", e)

def read_last_state():
    try:
        return open(STATE_FILE).read().strip()
    except FileNotFoundError:
        return ""

def write_last_state(s: str):
    try:
        open(STATE_FILE, "w").write(s)
    except Exception as e:
        print("Не удалось записать state:", e)

async def fetch_available_capacity():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = await browser.new_page()
        await page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
        locator = page.get_by_text("Available Capacity", exact=False).first
        await locator.wait_for(timeout=120_000)
        container = locator.locator("xpath=ancestor::*[self::div or self::section][1]")
        txt = await container.inner_text()
        cap = parse_money(txt)
        await browser.close()
        return cap

async def main_loop():
    print("Старт мониторинга:", URL)
    while True:
        try:
            cap = await fetch_available_capacity()
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            print(f"[{now}] Available Capacity: {cap:.2f} USDC")
            last = read_last_state()
            cur = "above" if cap > THRESHOLD else "below"
            if (last != "above" and cur == "above") or (last == "" and cur == "above"):
                send_telegram(f"🟢 Hyperion: доступная емкость > {THRESHOLD:.0f} USDC\nТекущее: {cap:.2f} USDC\n{URL}")
            write_last_state(cur)
        except Exception as e:
            print("Ошибка мониторинга:", repr(e))
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main_loop())

