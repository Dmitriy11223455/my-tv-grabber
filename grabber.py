import asyncio
import random
import datetime
import re
from playwright.async_api import async_playwright

USER_AGENT = "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36"

async def get_all_channels_from_site(page):
    now = lambda: datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now()}] >>> Глубокое сканирование структуры...")
    
    # Попробуем зайти через мобильное зеркало
    target_url = "https://smotret.tv" 
    
    try:
        await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(random.randint(8, 12)) # Долгая пауза для JS
        
        # Попытка вытащить ссылки всеми способами
        found_channels = {}
        
        # 1. Поиск по ссылкам с расширением .html
        links = await page.query_selector_all("a")
        for el in links:
            href = await el.get_attribute("href")
            title = await el.get_attribute("title") or await el.inner_text()
            
            if href and (".html" in href or "/channel/" in href):
                # Фильтруем мусор
                if any(x in href.lower() for x in ["feedback", "about", "contact", "privacy"]): continue
                
                full_url = href if href.startswith("http") else f"https://smotrettv.com{href}"
                name = title.strip().split('\n')[0]
                
                if len(name) > 2 and full_url not in found_channels.values():
                    found_channels[name] = full_url

        print(f"[{now()}] [OK] Найдено каналов: {len(found_channels)}")
        return found_channels
    except Exception as e:
        print(f"[{now()}] [!] Ошибка сканирования: {e}")
        return {}

async def get_tokens_and_make_playlist():
    async with async_playwright() as p:
        now_ts = lambda: datetime.datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now_ts()}] >>> Запуск в Stealth режиме...")
        
        # Добавляем флаги для скрытия автоматизации
        browser = await p.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process"
        ])
        
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 390, 'height': 844}, # iPhone 14 size
            is_mobile=True,
            has_touch=True
        )
        page = await context.new_page()
        
        CHANNELS = await get_all_channels_from_site(page)
        
        if not CHANNELS:
            print(f"[{now_ts()}] [!] Не удалось найти каналы. Сайт обновил защиту.")
            await browser.close()
            return

        playlist_results = []
        # Сократим до 15 каналов для стабильности в GitHub Actions
        items = list(CHANNELS.items())[:20]

        for i, (name, url) in enumerate(items, 1):
            print(f"[{now_ts()}] [{i}/{len(items)}] {name}...")
            current_stream = None

            async def catch_m3u8(request):
                nonlocal current_stream
                u = request.url
                if ".m3u8" in u and len(u) > 60 and not any(x in u for x in ["/ads/", "pixel"]):
                    current_stream = u

            page.on("request", catch_m3u8)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(10)
                
                # Клик по видео (эмуляция тапа)
                await page.mouse.click(200, 300)
                await asyncio.sleep(6)
                
                if current_stream:
                    playlist_results.append((name, current_stream))
                    print("   [+] OK")
            except: pass
            page.remove_listener("request", catch_m3u8)

        if playlist_results:
            with open("playlist.m3u", "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for n, l in playlist_results:
                    f.write(f'#EXTINF:-1, {n}\n{l}|Referer=https://smotrettv.com{USER_AGENT}\n')
            print(f"[{now_ts()}] Плейлист обновлен.")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())






