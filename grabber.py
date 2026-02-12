import asyncio
import datetime
import sys
import os
from playwright.async_api import async_playwright

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"

async def get_all_channels_from_site(page):
    print(">>> [1/3] Поиск списка каналов...", flush=True)
    try:
        # Заходим на главную
        await page.goto("https://smotrettv.com", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        
        found_channels = {}
        # Собираем ссылки на каналы
        links = await page.query_selector_all("a")
        for link in links:
            try:
                url = await link.get_attribute("href")
                name = await link.inner_text()
                if url and name:
                    clean_name = name.strip().split('\n')[0].upper()
                    # Фильтр разделов
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
        print(">>> [2/3] Инициализация браузера...", flush=True)
        # Запуск с флагами для обхода детектирования автоматизации
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-blink-features=AutomationControlled'])
        
        # 1. Получаем список каналов
        init_ctx = await browser.new_context(user_agent=USER_AGENT)
        temp_page = await init_ctx.new_page()
        
        CHANNELS = await get_all_channels_from_site(temp_page)
        await init_ctx.close()

        if not CHANNELS:
            await browser.close()
            return

        print(f"\n>>> [3/3] Сбор прямых ссылок...", flush=True)
        results = []
        
        # Обрабатываем первые 20 каналов
        channel_list = list(CHANNELS.items())[:20]
        
        for name, url in channel_list:
            # Создаем контекст для каждого канала
            ch_ctx = await browser.new_context(
                user_agent=USER_AGENT,
                viewport={'width': 1280, 'height': 720}
            )
            ch_page = await ch_ctx.new_page()
            
            stream_data = {"url": None}

            async def handle_request(request):
                u = request.url
                # Ловим m3u8, исключая рекламу и статику
                if ".m3u8" in u and not any(x in u for x in ["ads", "log", "stat", "yandex", "metrika", "telemetry"]):
                    # Приоритет ссылкам с токеном или мастер-плейлистам
                    if any(k in u for k in ["token", "master", "playlist.m3u8", "index-v1"]):
                        stream_data["url"] = u

            ch_page.on("request", handle_request)
            print(f"[*] {name:.<25}", end=" ", flush=True)

            try:
                await ch_page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(5)
                
                # Клик по плееру для запуска трансляции
                await ch_page.mouse.click(640, 360)
                
                # Ждем появления ссылки (до 15 секунд)
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
                await ch_ctx.close()

        # Сохранение плейлиста
        if results:
            filename = "playlist.m3u"
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    f.write("#EXTM3U\n")
                    f.write(f"# Сгенерировано: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
                    for n, l in results:
                        # Добавляем Referer и UA прямо в строку ссылки (поддерживается большинством IPTV плееров)
                        f.write(f'#EXTINF:-1, {n}\n')
                        f.write(f'{l}|Referer=https://smotrettv.com{USER_AGENT}\n\n')
                print(f"\n>>> ГОТОВО! Файл {filename} создан. Найдено: {len(results)}")
            except Exception as e:
                print(f"\n[!] Ошибка при записи файла: {e}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())




















