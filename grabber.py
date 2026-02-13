import asyncio
import datetime
import sys
import os
import random
from playwright.async_api import async_playwright

# Актуальный User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

async def get_all_channels_from_site(page):
    print(">>> [1/3] Поиск списка каналов...", flush=True)
    try:
        await page.goto("https://smotrettv.com", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        
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
        print(">>> [2/3] Запуск браузера...", flush=True)
        
        browser = await p.chromium.launch(headless=True, args=[
            '--no-sandbox', 
            '--disable-blink-features=AutomationControlled'
        ])
        
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1280, 'height': 720},
            locale="ru-RU"
        )
        
        # Скрытие автоматизации
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        temp_page = await context.new_page()
        CHANNELS = await get_all_channels_from_site(temp_page)
        await temp_page.close()

        if not CHANNELS:
            await browser.close()
            return

        print(f"\n>>> [3/3] Сбор ссылок (фикс буферизации для Россия 1/НТВ)...", flush=True)
        results = []
        
        # Обрабатываем каналы
        all_items = list(CHANNELS.items())[:20]
        for name, url in all_items:
            ch_page = await context.new_page()
            # Список для сбора всех найденных m3u8 (чтобы взять последнюю/лучшую)
            captured_urls = []

            async def handle_request(request):
                u = request.url
                if ".m3u8" in u and not any(x in u for x in ["ads", "log", "stat", "yandex", "metrika"]):
                    if any(k in u for k in ["token", "master", "index", "playlist", "chunklist"]):
                        captured_urls.append(u)

            ch_page.on("request", handle_request)
            print(f"[*] {name:.<25}", end=" ", flush=True)

            try:
                await ch_page.goto(url, wait_until="domcontentloaded", timeout=45000)
                
                # Ждем прогрузки плеера (Россия 1 и НТВ требуют больше времени)
                await asyncio.sleep(random.uniform(8, 12))
                
                # Клик для активации (имитируем живого юзера)
                try:
                    await ch_page.mouse.click(640, 360)
                except: pass

                # Ждем появления ссылки
                for _ in range(10):
                    if captured_urls: break
                    await asyncio.sleep(1)

                if captured_urls:
                    # ВАЖНО: Берем ПОСЛЕДНЮЮ ссылку (она обычно основная после рекламы)
                    final_link = captured_urls[-1]
                    results.append((name, final_link))
                    print("OK", flush=True)
                else:
                    print("FAIL", flush=True)
            except:
                print("ERR", flush=True)
            finally:
                await ch_page.close()

        # Сохранение плейлиста
        if results:
            filename = "playlist.m3u"
            with open(filename, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                f.write(f"# Сгенерировано: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
                for n, l in results:
                    f.write(f'#EXTINF:-1, {n}\n')
                    # Формат с пайпом "|" и заголовками для снятия лимитов скорости
                    f.write(f'{l}|Referer=https://smotrettv.com{USER_AGENT}\n\n')
            
            print(f"\n>>> ГОТОВО! Файл {filename} обновлен.")
            print(f">>> Найдено: {len(results)} каналов.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())
























































































































































































































































































































































































































































































































































































































