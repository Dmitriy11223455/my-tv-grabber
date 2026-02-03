import asyncio
import random
from playwright.async_api import async_playwright

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def get_all_channels_from_site(page):
    """Улучшенный сборщик каналов с глубоким поиском ссылок"""
    print(">>> Сбор списка каналов с главной страницы...")
    try:
        await page.goto("https://smotrettv.com", wait_until="networkidle", timeout=60000)
        
        # Прокрутка вниз, чтобы подгрузились все ленивые элементы
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        await asyncio.sleep(2)
        
        found_channels = {}
        # Ищем все ссылки, которые ведут на страницы каналов
        # Фильтруем по характерным путям сайта
        links = await page.query_selector_all("a[href*='/public/'], a[href*='/entertainment/'], a[href*='/news/'], a[href*='/kids/'], a[href*='/movies/']")
        
        for link in links:
            name = await link.inner_text()
            url = await link.get_attribute("href")
            
            if url and len(name.strip()) > 1:
                full_url = url if url.startswith("http") else f"https://smotrettv.com{url}"
                clean_name = name.strip().split('\n')[0] # Берем только первую строку имени
                if full_url not in found_channels.values():
                    found_channels[clean_name] = full_url
            
        return found_channels
    except Exception as e:
        print(f"[!] Ошибка при сборе списка: {e}")
        return {}

async def get_tokens_and_make_playlist():
    playlist_streams = [] 

    async with async_playwright() as p:
        print(">>> Запуск браузера...")
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()

        # Получаем каналы
        CHANNELS = await get_all_channels_from_site(page)
        
        if not CHANNELS:
            print("[!] Список каналов пуст. Проверьте соединение или структуру сайта.")
            await browser.close()
            return

        print(f"[OK] Найдено уникальных каналов: {len(CHANNELS)}")

        for name, channel_url in CHANNELS.items():
            print(f"[*] Обработка: {name}...")
            current_stream_url = None

            async def handle_request(request):
                nonlocal current_stream_url
                url = request.url
                if ".m3u8" in url and ("token=" in url or "mediavitrina" in url or "cache" in url):
                    if not current_stream_url:
                        current_stream_url = url

            context.on("request", handle_request)
            
            try:
                await page.goto(channel_url, wait_until="domcontentloaded", timeout=40000)
                await asyncio.sleep(6) # Ждем плеер
                
                # Кликаем в центр, где обычно кнопка Play
                await page.mouse.click(640, 400)
                
                for _ in range(12):
                    if current_stream_url: break
                    await asyncio.sleep(1)

                if current_stream_url:
                    playlist_streams.append((name, current_stream_url))
                    print(f"   [OK] Поток найден")
                else:
                    print(f"   [ ] Поток не найден")

            except Exception as e:
                print(f"   [!] Ошибка: {e}")

            context.remove_listener("request", handle_request)
            await asyncio.sleep(random.uniform(1, 2))

        if playlist_streams:
            with open("auto_playlist.m3u", "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for name, link in playlist_streams: 
                    f.write(f'#EXTINF:-1, {name}\n{link}\n')
            print(f"\n>>> Успех! Создан файл auto_playlist.m3u ({len(playlist_streams)} шт.)")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())


