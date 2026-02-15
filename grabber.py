import asyncio
import datetime
import os
import random
from playwright.async_api import async_playwright

# Актуальный User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

async def scroll_page(page):
    """Прокрутка для подгрузки списка каналов"""
    for _ in range(3):
        await page.mouse.wheel(0, 2000)
        await asyncio.sleep(1.5)

async def get_all_channels_from_site(page):
    print(">>> [1/3] Обход разделов ТВ (пагинация)...", flush=True)
    # Список разделов БЕЗ РАДИО
    sections = [
        "https://smotrettv.com/tv/public/",
        "https://smotrettv.com/tv/news/",
        "https://smotrettv.com/tv/sport/",
        "https://smotrettv.com/tv/educational/",
        "https://smotrettv.com/tv/entertainment/",
        "https://smotrettv.com/tv/kino/",
        "https://smotrettv.com/tv/music/",
        "https://smotrettv.com/tv/kids/",
        "https://smotrettv.com/tv/regional/",
        "https://smotrettv.com/tv/foreign-tv/"
    ]
    
    found = {}
    for section_url in sections:
        try:
            print(f"    [*] Загрузка: {section_url.split('/')[-2]}", flush=True)
            await page.goto(section_url, wait_until="commit", timeout=60000)
            await asyncio.sleep(4)
            await scroll_page(page)
            
            links = await page.query_selector_all("a")
            for link in links:
                try:
                    url = await link.get_attribute("href")
                    name = await link.inner_text()
                    if url and name and ".html" in url:
                        clean = name.strip().split('\n')[0].upper()
                        if len(clean) > 2:
                            full_url = url if url.startswith("http") else f"https://smotrettv.com{url}"
                            if clean not in found:
                                found[clean] = full_url
                except: continue
        except: continue
        
    print(f"    [+] Найдено ТВ каналов: {len(found)}", flush=True)
    return found

async def get_tokens_and_make_playlist():
    # ТВОИ ГАРАНТИРОВАННЫЕ ССЫЛКИ
    MY_CHANNELS = {
        "РОССИЯ 1": "https://smotrettv.com784-rossija-1.html",
        "НТВ": "https://smotrettv.com790-ntv.html",
        "РЕН ТВ": "https://smotrettv.com316-ren-tv.html",
        "ПЕРВЫЙ КАНАЛ": "https://smotrettv.com1003-pervyj-kanal.html"
    }

    async with async_playwright() as p:
        print(">>> [2/3] Запуск браузера...", flush=True)
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-blink-features=AutomationControlled'])
        context = await browser.new_context(user_agent=USER_AGENT, viewport={'width': 1280, 'height': 720})
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
        
        # Обрабатываем первые 300 каналов
        for name, url in list(MY_CHANNELS.items())[:300]:
            ch_page = await context.new_page()
            captured_urls = []

            async def handle_request(request):
                u = request.url
                if ".m3u8" in u and "token=" in u and not any(x in u for x in ["ads", "yandex", "metrika"]):
                    captured_urls.append(u)

            ch_page.on("request", handle_request)
            print(f"[*] {name:.<25}", end=" ", flush=True)

            try:
                await ch_page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(10)
                
                # Клик по плееру
                await ch_page.evaluate("window.scrollTo(0, 400)")
                for s in ["video", ".vjs-big-play-button", "button[class*='play']", "canvas"]:
                    try:
                        el = await ch_page.wait_for_selector(s, timeout=3000)
                        if el: 
                            await el.click(force=True)
                            break
                    except: continue
                
                for _ in range(15):
                    if captured_urls: break
                    await asyncio.sleep(1)

                if captured_urls:
                    # Выбираем лучший поток (v4/720p или самый длинный)
                    wifi_v = [u for u in captured_urls if "v4" in u or "720" in u]
                    final_link = wifi_v[0] if wifi_v else max(captured_urls, key=len)
                    results.append((name, str(final_link)))
                    print("OK", flush=True)
                else:
                    print("FAIL", flush=True)
            except:
                print("ERR", flush=True)
            finally:
                await ch_page.close()

        if results:
            with open("playlist.m3u", "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                f.write(f"# Обновлено: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
                for n, l in results:
                    f.write(f'#EXTINF:-1, {n}\n')
                    # Фикс заголовков для стабильности Mediavitrina (Россия 1, НТВ и др.)
                    if "mediavitrina" in l or any(x in n for x in ["РОССИЯ 1", "НТВ", "РЕН ТВ", "ПЕРВЫЙ"]):
                        h = f"|Referer=https://player.mediavitrina.ru{USER_AGENT}"
                    else:
                        h = f"|Referer=https://smotrettv.com{USER_AGENT}"
                    f.write(f"{l}{h}\n\n")
            print(f"\n>>> ГОТОВО! Создан playlist.m3u ({len(results)} каналов)")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())





































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































