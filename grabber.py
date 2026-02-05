import asyncio
import random
import datetime
from playwright.async_api import async_playwright

USER_AGENT = "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36"

async def get_all_channels_from_site(page):
    now = lambda: datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now()}] >>> Поиск всех каналов...")
    try:
        await page.goto("https://smotrettv.com", wait_until="domcontentloaded", timeout=40000)
        await asyncio.sleep(10)
        
        links = await page.query_selector_all("a[href*='.html']")
        found_channels = {}
        for el in links:
            url = await el.get_attribute("href")
            name = await el.get_attribute("title") or await el.inner_text()
            if url and name and any(c.isdigit() for c in url):
                full_url = url if url.startswith("http") else f"https://smotrettv.com{url}"
                clean_name = name.strip().split('\n')[0]
                if len(clean_name) > 2 and full_url not in found_channels.values():
                    found_channels[clean_name] = full_url
        print(f"[{now()}] [OK] Найдено каналов: {len(found_channels)}")
        return found_channels
    except Exception as e:
        print(f"[{now()}] [!] Ошибка сбора: {e}")
        return {}

async def get_tokens_and_make_playlist():
    async with async_playwright() as p:
        now_ts = lambda: datetime.datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now_ts()}] >>> Запуск граббера (Full Capture)...")
        
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 450, 'height': 900},
            is_mobile=True,
            has_touch=True
        )
        page = await context.new_page()
        
        CHANNELS = await get_all_channels_from_site(page)
        if not CHANNELS: return

        # Блокируем картинки только для экономии времени
        await page.route("**/*.{png,jpg,jpeg,gif,webp,svg}", lambda route: route.abort())

        playlist_results = []
        target_list = list(CHANNELS.items())

        for counter, (name, url) in enumerate(target_list, 1):
            print(f"[{now_ts()}] [{counter}/{len(target_list)}] Граббинг: {name}")
            current_stream = None

            async def catch_m3u8(request):
                nonlocal current_stream
                u = request.url
                # Ловим любой m3u8 длиннее 40 символов (чтобы отсечь пустые манифесты)
                if ".m3u8" in u and len(u) > 40:
                    if not any(x in u for x in ["/ads/", "telemetree", "track", "pixel", "metrics"]):
                        if not current_stream:
                            current_stream = u
                            print(f"   [+] Поток найден: {u[:60]}...")

            page.on("request", catch_m3u8)
            
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                
                # Ждем появления видео или плеера
                try:
                    await page.wait_for_selector("video, .player", timeout=8000)
                except: pass

                # Прокликиваем центр (активация)
                await page.mouse.click(225, 350)
                await asyncio.sleep(8)
                
                # Если не поймали, кликаем чуть ниже (кнопка Play)
                if not current_stream:
                    await page.mouse.click(225, 450)
                    await asyncio.sleep(5)
                
                if current_stream:
                    playlist_results.append((name, current_stream))
                else:
                    print(f"   [-] Ссылка не поймана")
            except: 
                print(f"   [!] Ошибка загрузки")
            
            page.remove_listener("request", catch_m3u8)
            await asyncio.sleep(1)

        if playlist_results:
            with open("playlist.m3u", "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for n, l in playlist_results:
                    f.write(f'#EXTINF:-1, {n}\n{l}|Referer=https://smotrettv.com{USER_AGENT}\n')
            print(f"[{now_ts()}] ГОТОВО! Плейлист на {len(playlist_results)} каналов сохранен.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())






