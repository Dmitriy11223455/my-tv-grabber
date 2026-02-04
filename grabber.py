import asyncio
import random
from playwright.async_api import async_playwright

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def get_all_channels_from_site(page):
    """Сверхбыстрый сборщик ссылок с отключением лишнего контента"""
    print(">>> Сбор списка каналов...")
    try:
        # Переходим максимально быстро, не дожидаясь загрузки рекламы и картинок
        await page.goto("https://smotrettv.com/", wait_until="commit", timeout=60000)
        await asyncio.sleep(5) # Даем JS немного времени отработать
        
        # Скроллим страницу вниз, чтобы подгрузить все блоки
        for _ in range(3):
            await page.mouse.wheel(0, 2000)
            await asyncio.sleep(1)

        found_channels = {}
        # Собираем абсолютно все ссылки на внутренние страницы каналов
        links = await page.query_selector_all("a[href*='/public/'], a[href*='/entertainment/'], a[href*='/news/'], a[href*='/kids/'], a[href*='/movies/'], a[href*='/sport/']")
        
        for link in links:
            name = await link.inner_text()
            url = await link.get_attribute("href")
            
            if url and len(name.strip()) > 1:
                full_url = url if url.startswith("http") else f"https://smotrettv.com{url}"
                clean_name = name.strip().split('\n')[0] 
                if full_url not in found_channels.values():
                    found_channels[clean_name] = full_url
            
        return found_channels
    except Exception as e:
        print(f"[!] Ошибка: {e}")
        return {}

async def get_tokens_and_make_playlist():
    async with async_playwright() as p:
        print(">>> Запуск браузера...")
        browser = await p.chromium.launch(headless=True)
        
        # Создаем контекст с блокировкой картинок для скорости
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()
        
        # Блокируем картинки и стили для обхода таймаутов
        await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2}", lambda route: route.abort())

        CHANNELS = await get_all_channels_from_site(page)
        
        if not CHANNELS:
            print("[!] Ссылки не найдены. Попробуйте запустить скрипт с VPN (если вы не в РФ) или без (если в РФ).")
            await browser.close()
            return

        print(f"[OK] Найдено каналов: {len(CHANNELS)}")
        
        playlist_results = []
        # Ограничим для теста первыми 20 каналами, чтобы не ждать вечно
        target_list = list(CHANNELS.items())#[:20] 

        for name, url in target_list:
            print(f"[*] Граббинг: {name}")
            stream_url = None

            async def catch_m3u8(request):
                nonlocal stream_url
                if ".m3u8" in request.url and ("token=" in request.url or "mediavitrina" in url):
                    stream_url = request.url

            page.on("request", catch_m3u8)
            
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(7)
                await page.mouse.click(640, 400) # Клик по плееру
                
                for _ in range(10):
                    if stream_url: break
                    await asyncio.sleep(1)
                
                if stream_url:
                    playlist_results.append((name, stream_url))
                    print(f"   + Нашел!")
                else:
                    print(f"   - Нет потока")
            except:
                print(f"   ! Ошибка загрузки")
            
            page.remove_listener("request", catch_m3u8)

        if playlist_results:
            with open(".config_cache_data", "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                f.write(f'{link}|Referer=https://smotrettv.com{USER_AGENT}\n')
                for n, l in playlist_results:
                    f.write(f"#EXTINF:-1, {n}\n{l}\n")
            print(f"\n>>> Готово! Сохранено {len(playlist_results)} каналов в playlist.m3u")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())



