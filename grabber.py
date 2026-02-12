import asyncio
import datetime
import sys
import os
from playwright.async_api import async_playwright

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

async def get_all_channels_from_site(page):
    print(">>> [1/3] Поиск списка каналов...", flush=True)
    try:
        # Используем domcontentloaded, так как networkidle часто виснет в облаке
        await page.goto("https://smotrettv.com", wait_until="domcontentloaded", timeout=90000)
        await asyncio.sleep(10) # Ждем прогрузки JS-скриптов
        
        found_channels = {}
        links = await page.query_selector_all("a")
        for link in links:
            try:
                url = await link.get_attribute("href")
                name = await link.inner_text()
                if url and name:
                    clean_name = name.strip().split('\n')[0].upper()
                    # Фильтр для сбора только ТВ каналов
                    if len(clean_name) > 1 and any(x in url for x in ['/public/', '/news/', '/sport/', '/entertainment/']):
                        full_url = url if url.startswith("http") else f"https://smotrettv.com{url}"
                        if clean_name not in found_channels:
                            found_channels[clean_name] = full_url
            except: continue
        
        print(f"    [+] Найдено каналов: {len(found_channels)}", flush=True)
        return found_channels
    except Exception as e:
        print(f"[!] Ошибка главной (Timeout/Block): {e}", flush=True)
        return {}

async def get_tokens_and_make_playlist():
    async with async_playwright() as p:
        print(">>> [2/3] Инициализация браузера (Stealth Mode)...", flush=True)
        
        # Запуск с маскировкой под обычного пользователя
        browser = await p.chromium.launch(headless=True, args=[
            '--no-sandbox', 
            '--disable-setuid-sandbox',
            '--disable-blink-features=AutomationControlled',
            '--disable-web-security'
        ])
        
        # Создаем контекст с эмуляцией реального экрана
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1920, 'height': 1080},
            locale="ru-RU"
        )
        
        # Инъекция скрипта для скрытия признаков автоматизации
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru']});
        """)

        temp_page = await context.new_page()
        CHANNELS = await get_all_channels_from_site(temp_page)
        await temp_page.close()

        if not CHANNELS:
            print("[!] Каналы не найдены. Сайт заблокировал доступ боту.")
            await browser.close()
            return

        print(f"\n>>> [3/3] Сбор ссылок (Первый и Россия 1 в приоритете)...", flush=True)
        results = []
        
        # Берем первые 25 каналов для надежности
        channel_list = list(CHANNELS.items())[:25]
        
        for name, url in channel_list:
            ch_page = await context.new_page()
            stream_data = {"url": None}

            async def handle_request(request):
                u = request.url
                # Ищем m3u8 и отсекаем мусор
                if ".m3u8" in u and not any(x in u for x in ["ads", "log", "stat", "yandex", "metrika", "telemetry"]):
                    # Ловим ссылки с токенами или мастер-плейлисты
                    if any(k in u for k in ["token", "master", "playlist", "index", "chunklist"]):
                        stream_data["url"] = u

            ch_page.on("request", handle_request)
            print(f"[*] {name:.<25}", end=" ", flush=True)

            try:
                await ch_page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(10) # Даем плееру время на инициализацию
                
                # Клик для активации видео
                await ch_page.mouse.click(640, 360)
                
                # Ждем появление ссылки в сетевых запросах
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

        # Сохранение плейлиста с "лекарством" от буферизации
        if results:
            filename = "playlist.m3u"
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write("#EXTM3U\n")
                    f.write(f"# Сгенерировано: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
                    for n, l in results:
                        # Добавление Referer и User-Agent критично для стабильности потока
                        f.write(f'#EXTINF:-1, {n}\n')
                        f.write(f'{l}|Referer=https://smotrettv.com{USER_AGENT}\n\n')
                print(f"\n>>> УСПЕХ! Создан {filename}. Найдено: {len(results)}")
            except Exception as e:
                print(f"\n[!] Ошибка записи плейлиста: {e}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())






















