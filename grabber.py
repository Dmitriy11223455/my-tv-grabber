import asyncio
import datetime
import os
import random
from playwright.async_api import async_playwright

# Актуальный User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

async def scroll_page(page):
    """Прокрутка для подгрузки списка каналов в категориях"""
    for _ in range(4):
        await page.mouse.wheel(0, 2500)
        await asyncio.sleep(1.5)

async def get_all_channels_from_site(page):
    print(">>> [1/3] Глубокий обход всех разделов ТВ...", flush=True)
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
            category_name = section_url.split('/')[-2].upper()
            print(f"    [*] Категория: {category_name}", flush=True)
            await page.goto(section_url, wait_until="commit", timeout=60000)
            await asyncio.sleep(4)
            await scroll_page(page)
            
            links = await page.query_selector_all("a")
            for link in links:
                try:
                    url = await link.get_attribute("href")
                    name = await link.inner_text()
                    if url and name and ".html" in url:
                        # Очистка названия
                        clean = name.strip().split('\n')[0].upper()
                        if len(clean) > 2:
                            full_url = url if url.startswith("http") else f"https://smotrettv.com{url}"
                            if clean not in found: found[clean] = full_url
                except: continue
        except: continue
        
    print(f"    [+] Найдено ТВ каналов всего: {len(found)}", flush=True)
    return found

async def get_tokens_and_make_playlist():
    # ГАРАНТИРОВАННЫЕ КАНАЛЫ (Ссылки исправлены)
    MY_CHANNELS = {
        "РОССИЯ 1": "https://smotrettv.com/784-rossija-1.html",
        "НТВ": "https://smotrettv.com/6-ntv.html",
        "РЕН ТВ": "https://smotrettv.com/316-ren-tv.html",
        "ПЕРВЫЙ КАНАЛ": "https://smotrettv.com/tv/public/1003-pervyj-kanal.html"
    }

    async with async_playwright() as p:
        print(">>> [2/3] Запуск браузера (Stealth Mode)...", flush=True)
        browser = await p.chromium.launch(headless=True, args=[
            '--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled'
        ])
        context = await browser.new_context(user_agent=USER_AGENT, viewport={'width': 1280, 'height': 720})
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        temp_page = await context.new_page()
        SCRAPED = await get_all_channels_from_site(temp_page)
        await temp_page.close()

        # Склеиваем словари (твои каналы всегда первые)
        for name, url in SCRAPED.items():
            if name not in MY_CHANNELS: MY_CHANNELS[name] = url

        print(f"\n>>> [3/3] Сбор прямых ссылок (Лимит: 100)...", flush=True)
        results = []
        
        # Лимит 100, чтобы GitHub Actions не работал слишком долго
        for name, url in list(MY_CHANNELS.items())[:100]:
            ch_page = await context.new_page()
            captured_urls = []

            async def handle_request(request):
                u = request.url
                if ".m3u8" in u and not any(x in u for x in ["ads", "yandex", "metrika", "telemetry"]):
                    captured_urls.append(u)

            ch_page.on("request", handle_request)
            print(f"[*] {name:.<25}", end=" ", flush=True)

            try:
                await ch_page.goto(url, wait_until="commit", timeout=60000)
                await asyncio.sleep(12) 
                
                # Кликаем по плееру (пробиваем федеральную защиту)
                await ch_page.evaluate("window.scrollTo(0, 450)")
                click_points = ["video", "iframe", "canvas", ".vjs-big-play-button", "button[class*='play']"]
                for s in click_points:
                    try:
                        targets = await ch_page.query_selector_all(s)
                        for target in targets:
                            await target.click(force=True, timeout=2000)
                            await asyncio.sleep(1)
                    except: continue
                
                await ch_page.mouse.click(640, 480)

                # Ожидание ссылки
                for _ in range(25):
                    if captured_urls: break
                    await asyncio.sleep(1)

                if captured_urls:
                    # Оптимизация битрейта для стабильности Wi-Fi (v4/720p)
                    wifi_v = [u for u in captured_urls if "v4" in u or "720" in u]
                    final_link = wifi_v[0] if wifi_v else max(captured_urls, key=len)
                    results.append((name, str(final_link)))
                    print("OK", flush=True)
                else:
                    # Запасной метод через JS, если запрос не перехвачен
                    src = await ch_page.evaluate("() => document.querySelector('video') ? document.querySelector('video').src : null")
                    if src and "http" in src:
                        results.append((name, src))
                        print("OK (JS)", flush=True)
                    else:
                        print("FAIL", flush=True)
            except:
                print("ERR", flush=True)
            finally:
                await ch_page.close()

        if results:
            filename = "playlist.m3u"
            with open(filename, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                f.write(f"# Сгенерировано: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
                for n, l in results:
                    f.write(f'#EXTINF:-1, {n}\n')
                    # Фикс заголовков для стабильности (Mediavitrina и др.)
                    if "mediavitrina" in l or any(x in n for x in ["РОССИЯ 1", "НТВ", "РЕН ТВ", "ПЕРВЫЙ"]):
                        h = f"|Referer=https://player.mediavitrina.ru{USER_AGENT}"
                    else:
                        h = f"|Referer=https://smotrettv.com{USER_AGENT}"
                    f.write(f"{l}{h}\n\n")
            print(f"\n>>> ГОТОВО! Плейлист {filename} создан ({len(results)} каналов)")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())




































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































