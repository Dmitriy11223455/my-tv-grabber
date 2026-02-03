import asyncio
import random
from playwright.async_api import async_playwright

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def get_all_channels_from_site(page):
    """Автоматически собирает все ссылки на каналы с главной страницы"""
    print(">>> Сбор списка всех каналов...")
    await page.goto("https://smotrettv.com", wait_until="domcontentloaded")
    
    # Собираем ссылки из разных категорий
    found_channels = {}
    # Селектор ищет ссылки в сетке каналов
    links = await page.query_selector_all("a.channel-item, .channels-list a, a[href*='/public/'], a[href*='/entertainment/'], a[href*='/news/']")
    
    for link in links:
        name = await link.inner_text()
        url = await link.get_attribute("href")
        if url and name.strip():
            full_url = url if url.startswith("http") else f"https://smotrettv.com{url}"
            # Убираем дубликаты и пустые названия
            clean_name = name.strip().split('\n')[0]
            found_channels[clean_name] = full_url
            
    print(f"[OK] Найдено каналов для обработки: {len(found_channels)}")
    return found_channels

async def get_tokens_and_make_playlist():
    playlist_streams = [] 

    async with async_playwright() as p:
        print(">>> Запуск браузера...")
        browser = await p.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox"
        ])
        
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1280, 'height': 720},
            extra_http_headers={"Referer": "https://smotrettv.com"}
        )
        
        page = await context.new_page()

        # ШАГ 1: Динамически получаем список всех каналов
        CHANNELS = await get_all_channels_from_site(page)

        # ШАГ 2: Обходим каждый найденный канал
        for name, channel_url in CHANNELS.items():
            print(f"[*] Граббинг: {name}...")
            current_stream_url = None

            async def handle_request(request):
                nonlocal current_stream_url
                url = request.url
                if ".m3u8" in url and ("token=" in url or "mediavitrina" in url):
                    if not current_stream_url:
                        current_stream_url = url

            context.on("request", handle_request)
            
            try:
                await page.goto(channel_url, wait_until="load", timeout=60000)
                await asyncio.sleep(5) # Ждем подгрузки плеера
                
                # Кликаем в область плеера, чтобы инициировать поток
                await page.mouse.click(640, 360)
                
                # Ждем появления ссылки
                for _ in range(10):
                    if current_stream_url: break
                    await asyncio.sleep(1)

                if current_stream_url:
                    playlist_streams.append((name, current_stream_url))
                    print(f"   [OK] Ссылка поймана")
                else:
                    # Попытка через пробел (Play)
                    await page.keyboard.press("Space")
                    await asyncio.sleep(3)
                    if current_stream_url:
                        playlist_streams.append((name, current_stream_url))
                        print(f"   [OK] Ссылка поймана через Space")
                    else:
                        print(f"   [!] Поток не обнаружен")

            except Exception as e:
                print(f"   [!] Ошибка на {name}: {e}")

            context.remove_listener("request", handle_request)
            # Небольшая пауза, чтобы сайт не забанил за слишком частые запросы
            await asyncio.sleep(random.uniform(1, 2))

        # Запись итогового плейлиста
        if playlist_streams:
            with open("all_channels_playlist.m3u", "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for name, link in playlist_streams: 
                    f.write(f'#EXTINF:-1, {name}\n{link}\n')
            print(f"\n>>> Готово! Собрано каналов: {len(playlist_streams)}")
            print("Результат сохранен в all_channels_playlist.m3u")
        else:
            print("\n[!] Не удалось собрать ни одной ссылки.")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())

