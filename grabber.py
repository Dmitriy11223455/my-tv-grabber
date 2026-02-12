import asyncio
import datetime
import sys
import os
import random
from playwright.async_api import async_playwright

USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1"

async def get_all_channels_from_site(page):
    print(">>> [1/3] Поиск списка каналов (Bypass Mode)...", flush=True)
    try:
        # Переход с минимальным ожиданием, чтобы проскочить проверку
        await page.goto("https://smotrettv.com", wait_until="commit", timeout=60000)
        await asyncio.sleep(8)
        
        found_channels = {}
        # Ищем все ссылки
        links = await page.query_selector_all("a")
        
        for link in links:
            try:
                url = await link.get_attribute("href")
                name = await link.inner_text()
                if url and name:
                    clean_name = name.strip().split('\n')[0].upper()
                    # Фильтр только ТВ разделов
                    if any(x in url for x in ['/public/', '/news/', '/sport/', '/entertainment/']):
                        if len(clean_name) > 1:
                            full_url = url if url.startswith("http") else f"https://smotrettv.com{url}"
                            if clean_name not in found_channels:
                                found_channels[clean_name] = full_url
            except: continue
            
        if not found_channels:
            print("[!] Каналов 0. Делаю скриншот главной...", flush=True)
            await page.screenshot(path="fail_main_0_channels.png")
            
        print(f"    [+] Найдено каналов: {len(found_channels)}", flush=True)
        return found_channels
    except Exception as e:
        print(f"[!] Ошибка главной: {e}", flush=True)
        await page.screenshot(path="fail_main_error.png")
        return {}

async def get_tokens_and_make_playlist():
    async with async_playwright() as p:
        print(">>> [2/3] Инициализация браузера...", flush=True)
        
        browser = await p.chromium.launch(headless=True, args=[
            '--no-sandbox', 
            '--disable-setuid-sandbox',
            '--disable-blink-features=AutomationControlled'
        ])
        
        # Эмулируем iPhone для обхода жестких проверок ПК-версии
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 375, 'height': 812},
            is_mobile=True,
            has_touch=True
        )
        
        # Скрываем признаки автоматизации
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        temp_page = await context.new_page()
        CHANNELS = await get_all_channels_from_site(temp_page)
        await temp_page.close()

        if not CHANNELS:
            await browser.close()
            return

        print(f"\n>>> [3/3] Сбор прямых ссылок (лечение буферизации)...", flush=True)
        results = []
        
        # Берем первые 20 каналов
        for name, url in list(CHANNELS.items())[:20]:
            ch_page = await context.new_page()
            stream_data = {"url": None}

            async def handle_request(request):
                u = request.url
                if ".m3u8" in u and not any(x in u for x in ["ads", "log", "stat", "yandex", "metrika"]):
                    if any(k in u for k in ["token", "master", "index", "playlist", "chunklist"]):
                        stream_data["url"] = u

            ch_page.on("request", handle_request)
            print(f"[*] {name:.<25}", end=" ", flush=True)

            try:
                await ch_page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(random.uniform(7, 10))
                
                # Эмуляция тапа по центру экрана (для запуска мобильного плеера)
                await ch_page.mouse.click(187, 406)
                
                for _ in range(15):
                    if stream_data["url"]: break
                    await asyncio.sleep(1)

                if stream_data["url"]:
                    results.append((name, stream_data["url"]))
                    print("OK", flush=True)
                else:
                    safe_n = name.replace(" ", "_").replace("/", "_")
                    await ch_page.screenshot(path=f"fail_{safe_n}.png")
                    print("FAIL (📷 saved)", flush=True)
            except:
                print("ERR", flush=True)
            finally:
                await ch_page.close()

        # Сохранение плейлиста с Headers (обязательно для Первого и России 1)
        if results:
            filename = "playlist.m3u"
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write("#EXTM3U\n")
                    f.write(f"# Сгенерировано: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
                    for n, l in results:
                        # Referer и UA для плеера (лечит буферизацию)
                        f.write(f'#EXTINF:-1, {n}\n')
                        f.write(f'{l}|Referer=https://smotrettv.com{USER_AGENT}\n\n')
                print(f"\n>>> ГОТОВО! Плейлист создан. Найдено: {len(results)}")
            except Exception as e:
                print(f"\n[!] Ошибка записи: {e}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())



























