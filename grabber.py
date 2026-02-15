import asyncio
import datetime
import os
import random
from playwright.async_api import async_playwright

# Мобильный User-Agent (его реже блокируют)
USER_AGENT = "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"

async def get_all_channels_from_site(page):
    print(">>> [1/3] Поиск каналов (Mobile Emulation)...", flush=True)
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
            # Ждем 'commit' чтобы не виснуть на тяжелой рекламе
            response = await page.goto(section_url, wait_until="commit", timeout=60000)
            if response.status != 200: continue
            
            await asyncio.sleep(5)
            # Ищем все ссылки, которые ведут на страницы каналов (.html)
            links = await page.query_selector_all("a[href*='.html']")
            for link in links:
                try:
                    url = await link.get_attribute("href")
                    name = await link.inner_text()
                    if url and name and len(name.strip()) > 2:
                        clean = name.strip().split('\n')[0].upper()
                        full_url = url if url.startswith("http") else f"https://smotrettv.com{url}"
                        if clean not in found: found[clean] = full_url
                except: continue
        except: continue
        
    print(f"    [+] Найдено ТВ каналов: {len(found)}", flush=True)
    return found

async def get_tokens_and_make_playlist():
    # Гарантированные ссылки (обновлены пути)
    MY_CHANNELS = {
        "РОССИЯ 1": "https://smotrettv.com784-rossiya-1.html",
        "НТВ": "https://smotrettv.com790-ntv.html",
        "РЕН ТВ": "https://smotrettv.com316-ren-tv.html",
        "ПЕРВЫЙ КАНАЛ": "https://smotrettv.com1003-pervyy-kanal.html"
    }

    async with async_playwright() as p:
        print(">>> [2/3] Запуск браузера (Mobile Mode)...", flush=True)
        # Запуск с имитацией мобильного устройства
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        
        # Эмуляция iPhone 12 для обхода защиты
        device = p.devices['iPhone 12']
        context = await browser.new_context(**device, locale="ru-RU")
        
        # Скрываем следы автоматизации
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        temp_page = await context.new_page()
        SCRAPED = await get_all_channels_from_site(temp_page)
        await temp_page.close()

        # Объединяем словари
        for name, url in SCRAPED.items():
            if name not in MY_CHANNELS: MY_CHANNELS[name] = url

        print(f"\n>>> [3/3] Сбор ссылок (Лимит: 60)...", flush=True)
        results = []
        
        for name, url in list(MY_CHANNELS.items())[:60]:
            ch_page = await context.new_page()
            captured_urls = []

            async def handle_request(request):
                u = request.url
                if ".m3u8" in u and not any(x in u for x in ["ads", "metrika", "telemetry"]):
                    captured_urls.append(u)

            ch_page.on("request", handle_request)
            print(f"[*] {name:.<25}", end=" ", flush=True)

            try:
                await ch_page.goto(url, wait_until="commit", timeout=60000)
                await asyncio.sleep(10)
                
                # Кликаем "вслепую" по центру экрана (активация плеера)
                await ch_page.mouse.click(200, 300) 
                
                for _ in range(20):
                    if captured_urls: break
                    await asyncio.sleep(1)

                if captured_urls:
                    # Выбираем самый стабильный поток
                    final_link = max(captured_urls, key=len)
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
                f.write("#EXTM3U\n\n")
                for n, l in results:
                    f.write(f'#EXTINF:-1, {n}\n')
                    # Для Mediavitrina (Россия 1 и др.) используем правильные мобильные рефереры
                    if "mediavitrina" in l:
                        h = f"|Referer=https://player.mediavitrina.ru{USER_AGENT}"
                    else:
                        h = f"|Referer=https://smotrettv.com{USER_AGENT}"
                    f.write(f"{l}{h}\n\n")
            print(f"\n>>> Плейлист обновлен! ({len(results)} каналов)")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())





































































































































































































































































































































































































































































































































































































































































































































































































































































































































































































