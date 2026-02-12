import asyncio
import datetime
import sys
import os
import random
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

# Реалистичный User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

async def get_all_channels_from_site(page):
    print(">>> [1/3] Поиск списка каналов (Stealth Bypass)...", flush=True)
    try:
        # Применяем Stealth-маскировку к странице
        await stealth_async(page)
        
        # Переход с ожиданием первичной отрисовки
        await page.goto("https://smotrettv.com", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(10) # Даем Cloudflare время "пропустить" нас
        
        found_channels = {}
        links = await page.query_selector_all("a")
        
        for link in links:
            try:
                url = await link.get_attribute("href")
                name = await link.inner_text()
                if url and name:
                    clean_name = name.strip().split('\n')[0].upper()
                    # Фильтруем ссылки на плееры каналов
                    if any(x in url for x in ['/public/', '/news/', '/sport/', '/entertainment/']):
                        if len(clean_name) > 1:
                            full_url = url if url.startswith("http") else f"https://smotrettv.com{url}"
                            if clean_name not in found_channels:
                                found_channels[clean_name] = full_url
            except: continue
            
        if not found_channels:
            print("[!] Список пуст. Делаю скриншот проверки Cloudflare...", flush=True)
            await page.screenshot(path="fail_cloudflare_check.png")
            
        print(f"    [+] Найдено каналов: {len(found_channels)}", flush=True)
        return found_channels
    except Exception as e:
        print(f"[!] Ошибка: {e}", flush=True)
        return {}

async def get_tokens_and_make_playlist():
    async with async_playwright() as p:
        print(">>> [2/3] Запуск браузера (Ultra Stealth)...", flush=True)
        
        browser = await p.chromium.launch(headless=True, args=[
            '--no-sandbox', 
            '--disable-setuid-sandbox',
            '--disable-blink-features=AutomationControlled',
            '--use-fake-ui-for-media-stream'
        ])
        
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1280, 'height': 720},
            locale="ru-RU",
            timezone_id="Europe/Moscow"
        )

        temp_page = await context.new_page()
        CHANNELS = await get_all_channels_from_site(temp_page)
        await temp_page.close()

        if not CHANNELS:
            await browser.close()
            return

        print(f"\n>>> [3/3] Сбор ссылок (обход буферизации)...", flush=True)
        results = []
        
        for name, url in list(CHANNELS.items())[:20]:
            ch_page = await context.new_page()
            await stealth_async(ch_page) # Маскируем каждую страницу канала
            
            stream_data = {"url": None}

            async def handle_request(request):
                u = request.url
                if ".m3u8" in u and not any(x in u for x in ["ads", "log", "stat", "yandex"]):
                    if any(k in u for k in ["token", "master", "index", "playlist"]):
                        stream_data["url"] = u

            ch_page.on("request", handle_request)
            print(f"[*] {name:.<25}", end=" ", flush=True)

            try:
                await ch_page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(random.uniform(8, 12))
                
                # Имитируем активность для запуска плеера
                await ch_page.mouse.move(640, 360, steps=5)
                await ch_page.mouse.click(640, 360)
                
                for _ in range(15):
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

        # Создание плейлиста с параметрами для плеера
        if results:
            with open("playlist.m3u", "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                f.write(f"# Обновлено: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
                for n, l in results:
                    # Добавляем Referer и User-Agent (устраняет тормоза на Первом и России 1)
                    f.write(f'#EXTINF:-1, {n}\n')
                    f.write(f'{l}|Referer=https://smotrettv.com{USER_AGENT}\n\n')
            print(f"\n>>> ГОТОВО! Плейлист обновлен. Найдено: {len(results)}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())











































































































