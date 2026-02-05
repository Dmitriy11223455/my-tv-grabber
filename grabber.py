import asyncio
import random
import datetime
from playwright.async_api import async_playwright

USER_AGENT = "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36"

async def get_all_channels_from_site(page):
    now = lambda: datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now()}] >>> Поиск каналов (Мобильный режим)...")
    try:
        await page.goto("https://smotrettv.com", wait_until="domcontentloaded", timeout=40000)
        await asyncio.sleep(10)
        
        # Собираем все ссылки на каналы через паттерн .html
        links = await page.query_selector_all("a[href*='.html']")
        found_channels = {}
        for el in links:
            url = await el.get_attribute("href")
            name = await el.get_attribute("title") or await el.inner_text()
            if url and name and any(c.isdigit() for c in url):
                full_url = url if url.startswith("http") else f"https://smotrettv.com{url}"
                clean_name = name.strip().split('\n')[0]
                if "smotrettv.com" in full_url and len(clean_name) > 2:
                    found_channels[clean_name] = full_url
        print(f"[{now()}] [OK] Найдено: {len(found_channels)}")
        return found_channels
    except Exception as e:
        print(f"[{now()}] [!] Ошибка: {e}")
        return {}

async def get_tokens_and_make_playlist():
    async with async_playwright() as p:
        now_ts = lambda: datetime.datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now_ts()}] >>> Запуск граббера...")
        
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

        # Блокируем мусор
        await page.route("**/*.{png,jpg,jpeg,gif,webp,svg}", lambda route: route.abort())

        playlist_results = []
        target_list = list(CHANNELS.items())

        for counter, (name, url) in enumerate(target_list, 1):
            print(f"[{now_ts()}] [{counter}/{len(target_list)}] Граббинг: {name}")
            current_stream = None

            async def catch_m3u8(request):
                nonlocal current_stream
                u = request.url
                if ".m3u8" in u and not any(x in u for x in ["ads", "track"]):
                    if any(k in u for k in ["token=", "mediavitrina", "vittv", "p7live", "playlist"]):
                        current_stream = u

            page.on("request", catch_m3u8)
            
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                await asyncio.sleep(8)
                
                # Клик по центру экрана (активация плеера на мобилке)
                await page.mouse.click(225, 350)
                await asyncio.sleep(5)
                
                if current_stream:
                    playlist_results.append((name, current_stream))
                    print(f"   [+] Поток захвачен")
                else:
                    # Вторая попытка клика если не поймали
                    await page.mouse.click(225, 450)
                    await asyncio.sleep(5)
                    if current_stream:
                        playlist_results.append((name, current_stream))
                        print(f"   [+] Поток захвачен со 2-го клика")
            except: pass
            page.remove_listener("request", catch_m3u8)

        if playlist_results:
            with open("playlist.m3u", "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for n, l in playlist_results:
                    f.write(f'#EXTINF:-1, {n}\n{l}|Referer=https://smotrettv.com&User-Agent={USER_AGENT}\n')
            print(f"[{now_ts()}] Готово! Собрано: {len(playlist_results)}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())





