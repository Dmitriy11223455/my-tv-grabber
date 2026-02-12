import asyncio
import datetime
import sys
import os
from playwright.async_api import async_playwright

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

async def get_all_channels_from_site(page):
    print(">>> [1/3] Поиск списка каналов...", flush=True)
    try:
        await page.goto("https://smotrettv.com", wait_until="domcontentloaded", timeout=90000)
        await asyncio.sleep(10)
        
        found_channels = {}
        links = await page.query_selector_all("a")
        for link in links:
            try:
                url = await link.get_attribute("href")
                name = await link.inner_text()
                if url and name:
                    clean_name = name.strip().split('\n')[0].upper()
                    if len(clean_name) > 1 and any(x in url for x in ['/public/', '/news/', '/sport/', '/entertainment/']):
                        full_url = url if url.startswith("http") else f"https://smotrettv.com{url}"
                        if clean_name not in found_channels:
                            found_channels[clean_name] = full_url
            except: continue
        
        print(f"    [+] Найдено каналов: {len(found_channels)}", flush=True)
        return found_channels
    except Exception as e:
        print(f"[!] Ошибка главной: {e}", flush=True)
        return {}

async def get_tokens_and_make_playlist():
    async with async_playwright() as p:
        print(">>> [2/3] Инициализация браузера (Stealth Mode)...", flush=True)
        
        browser = await p.chromium.launch(headless=True, args=[
            '--no-sandbox', 
            '--disable-setuid-sandbox',
            '--disable-blink-features=AutomationControlled'
        ])
        
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1920, 'height': 1080},
            locale="ru-RU"
        )
        
        # Маскировка под реального пользователя
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru']});
        """)

        temp_page = await context.new_page()
        CHANNELS = await get_all_channels_from_site(temp_page)
        await temp_page.close()

        if not CHANNELS:
            await browser.close()
            return

        print(f"\n>>> [3/3] Сбор ссылок (активное взаимодействие)...", flush=True)
        results = []
        
        # Берем первые 20 каналов
        channel_list = list(CHANNELS.items())[:20]
        
        for name, url in channel_list:
            ch_page = await context.new_page()
            stream_data = {"url": None}

            async def handle_request(request):
                u = request.url
                if ".m3u8" in u and not any(x in u for x in ["ads", "log", "stat", "yandex", "metrika"]):
                    # Ловим всё: от мастер-плейлистов до чанков с токенами
                    if any(k in u for k in ["token", "master", "playlist", "index", "chunklist", "m3u8"]):
                        stream_data["url"] = u

            ch_page.on("request", handle_request)
            print(f"[*] {name:.<25}", end=" ", flush=True)

            try:
                await ch_page.goto(url, wait_until="domcontentloaded", timeout=60000)
                
                # 1. Скроллим к плееру (важно для инициализации JS)
                await ch_page.mouse.wheel(0, 500)
                await asyncio.sleep(7)
                
                # 2. Пытаемся кликнуть по разным точкам плеера (обход кнопок Play)
                click_points = [(640, 360), (600, 300), (700, 450)]
                for x, y in click_points:
                    if stream_data["url"]: break
                    await ch_page.mouse.click(x, y)
                    await asyncio.sleep(2)

                # 3. Ждем появления ссылки в сети
                for _ in range(12):
                    if stream_data["url"]: break
                    await asyncio.sleep(1)

                if stream_data["url"]:
                    results.append((name, stream_data["url"]))
                    print("OK", flush=True)
                else:
                    print("FAIL", flush=True)
            except:
                print("ERR", flush=True)
            finally:
                await ch_page.close()

        # Сохранение плейлиста с параметрами против буферизации
        if results:
            filename = "playlist.m3u"
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write("#EXTM3U\n")
                    f.write(f"# Обновлено: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
                    for n, l in results:
                        # Referer и User-Agent критически важны для Первого и России 1
                        f.write(f'#EXTINF:-1, {n}\n')
                        f.write(f'{l}|Referer=https://smotrettv.com{USER_AGENT}\n\n')
                print(f"\n>>> ГОТОВО! Файл {filename} создан. Найдено: {len(results)}")
            except Exception as e:
                print(f"\n[!] Ошибка записи: {e}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())























