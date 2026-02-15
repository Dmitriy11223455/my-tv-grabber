import asyncio
import datetime
import os
import random
from playwright.async_api import async_playwright

# Актуальный Chrome User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

async def scroll_page(page):
    """Прокрутка страницы для подгрузки всех каналов и радио"""
    print(">>> Прокрутка страницы вниз...", flush=True)
    for _ in range(5):
        await page.mouse.wheel(0, 2000)
        await asyncio.sleep(2)

async def get_all_channels_from_site(page):
    print(">>> [1/3] Поиск списка каналов и радио (со скроллом)...", flush=True)
    try:
        await page.goto("https://smotrettv.com", wait_until="commit", timeout=60000)
        await asyncio.sleep(5)
        await scroll_page(page)
        
        found_links = {}
        links = await page.query_selector_all("a")
        for link in links:
            try:
                url = await link.get_attribute("href")
                name = await link.inner_text()
                if url and name:
                    clean_name = name.strip().split('\n')[0].upper()
                    # Собираем ТВ разделы и раздел Радио (entertainment/public/news)
                    if len(clean_name) > 1 and any(x in url for x in ['/public/', '/news/', '/sport/', '/entertainment/']):
                        full_url = url if url.startswith("http") else f"https://smotrettv.com{url}"
                        if clean_name not in found_links:
                            found_links[clean_name] = full_url
            except: continue
        
        print(f"    [+] Найдено всего объектов: {len(found_links)}", flush=True)
        return found_links
    except Exception as e:
        print(f"[!] Ошибка главной: {e}", flush=True)
        return {}

async def get_tokens_and_make_playlist():
    # --- МОЙ ГАРАНТИРОВАННЫЙ СЛОВАРЬ (Россия 1 и Радио) ---
    MY_CHANNELS = {
        "РОССИЯ 1": "https://smotrettv.com/tv/public/784-rossija-1.html",
        "ПЕРВЫЙ КАНАЛ": "https://smotrettv.com/tv/public/1003-pervyj-kanal.html",
        "ВЕСТИ ФМ": "https://smotrettv.com/radio/198-vesti-fm.html",
        "РАДИО РЕКОРД": "https://smotrettv.com/radio/203-radio-rekord.html",
        "АВТОРАДИО": "https://smotrettv.com/radio/205-avtoradio.html",
        "НОВОЕ РАДИО": "https://smotrettv.com/radio/199-novoe-radio.html",
        "ЕВРОПА ПЛЮС": "https://smotrettv.com/radio/197-evropa-pljus.html",
        "COMEDY RADIO": "https://smotrettv.com/radio/289-comedy-radio.html",
        "РАДИО МОНТЕ-КАРЛО": "https://smotrettv.com/radio/204-radio-monte-karlo.html",
        "РАДИО ШАНСОН": "https://smotrettv.com/radio/259-radio-shanson.html",
        "МАРУСЯ FM": "https://smotrettv.com/radio/196-marusja-fm.html",
        "ВЕСТИ ФМ": "https://smotrettv.com/radio/198-vesti-fm.html",
        "РАДИО ВАНЯ": "https://smotrettv.com/radio/201-radio-vanja.html",
        "РУССКОЕ РАДИО": "https://smotrettv.com/radio/195-russkoe-radio.html",
        "РАДИО РОССИИ": "https://smotrettv.com/radio/269-radio-rossii.html",
        "РАДИО ENERGY": "https://smotrettv.com/radio/206-radio-energy.html",
        "DFM": "https://smotrettv.com/radio/267-dfm.html",
        "РЕТРО FM": "https://smotrettv.com/radio/202-retro-fm.html",
        "ДОРОЖНОЕ РАДИО": "https://smotrettv.com/radio/200-dorozhnoe-radio.html"
    }

    async with async_playwright() as p:
        print(">>> [2/3] Запуск браузера...", flush=True)
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-blink-features=AutomationControlled'])
        context = await browser.new_context(user_agent=USER_AGENT, viewport={'width': 1280, 'height': 720}, locale="ru-RU")
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        temp_page = await context.new_page()
        SCRAPED = await get_all_channels_from_site(temp_page)
        await temp_page.close()

        # Объединяем словарь и найденное
        for name, url in SCRAPED.items():
            if name not in MY_CHANNELS:
                MY_CHANNELS[name] = url

        print(f"\n>>> [3/3] Сбор ссылок (Лимит: 70)...", flush=True)
        results = []
        
        for name, url in list(MY_CHANNELS.items())[:70]:
            ch_page = await context.new_page()
            captured_urls = []

            async def handle_request(request):
                u = request.url
                # Ловим m3u8 для ТВ и mp3/aac/stream для Радио
                if any(ext in u for ext in [".m3u8", ".mp3", ".aac", "stream"]) and not any(x in u for x in ["ads", "log", "yandex"]):
                    captured_urls.append(u)

            ch_page.on("request", handle_request)
            print(f"[*] {name:.<25}", end=" ", flush=True)

            try:
                await ch_page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await asyncio.sleep(random.uniform(8, 12))
                
                # Клик по плееру
                await ch_page.mouse.click(640, 360)

                for _ in range(12):
                    if captured_urls: break
                    await asyncio.sleep(1)
                if captured_urls:
                    # Для ТВ ищем v4/720p, для Радио берем прямую ссылку mp3
                    wifi_v = [u for u in captured_urls if any(x in u for x in ["v4", "720", "mid", ".mp3", ".aac"])]
                    final_link = wifi_v[0] if wifi_v else max(captured_urls, key=len)
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
                f.write(f"# Обновлено: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
                
                for n, l in results:
                    f.write(f'#EXTINF:-1, {n}\n')
                    # Фикс заголовков для Mediavitrina (Россия 1) и стабильности
                    if "mediavitrina" in l or "РОССИЯ 1" in n:
                        h = f"|Referer=https://player.mediavitrina.ru{USER_AGENT}"
                    else:
                        h = f"|Referer=https://smotrettv.com{USER_AGENT}"
                    f.write(f"{l}{h}\n\n")
            
            print(f"\n>>> ГОТОВО! Создан {filename}. Каналов: {len(results)}")

        await browser.close()

if name == "main":
    asyncio.run(get_tokens_and_make_playlist())


































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































