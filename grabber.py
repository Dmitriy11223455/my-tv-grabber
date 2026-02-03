import asyncio
import random
from playwright.async_api import async_playwright

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def get_all_channels_from_site(page):
    """Собирает только реальные каналы, игнорируя рубрики меню"""
    print(">>> Сбор списка каналов с главной страницы...")
    try:
        await page.goto("https://smotrettv.com", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        found_channels = {}
        # Селектор ищет ссылки внутри карточек каналов
        links = await page.query_selector_all("a.channel-item, .channels-list a")
        
        for link in links:
            url = await link.get_attribute("href")
            name_elem = await link.query_selector(".channel-name, span, b")
            name = await name_elem.inner_text() if name_elem else ""
            
            if url and name.strip() and ("/public/" in url or "/entertainment/" in url or "/news/" in url):
                full_url = url if url.startswith("http") else f"https://smotrettv.com{url}"
                found_channels[name.strip()] = full_url
                
        print(f"[OK] Найдено каналов для обработки: {len(found_channels)}")
        return found_channels
    except Exception as e:
        print(f"[!] Ошибка при сканировании главной: {e}")
        return {}

async def get_tokens_and_make_playlist():
    playlist_streams = [] 

    async with async_playwright() as p:
        print(">>> Запуск браузера...")
        browser = await p.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox"
        ])
        
        # Создаем контекст с подменой User-Agent
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()

        # Получаем актуальный список каналов
        CHANNELS = await get_all_channels_from_site(page)

        for name, channel_url in CHANNELS.items():
            print(f"[*] Граббинг: {name}...")
            current_stream_url = None

            # Обработчик сетевых запросов
            async def handle_request(request):
                nonlocal current_stream_url
                u = request.url
                # Ищем m3u8 с токенами или ссылками на медиавитрину
                if ".m3u8" in u and ("token=" in u or "mediavitrina" in u or "index" in u):
                    if not current_stream_url:
                        current_stream_url = u

            page.on("request", handle_request)
            
            try:
                # Переход на страницу канала
                await page.goto(channel_url, wait_until="domcontentloaded", timeout=60000)
                
                # Ждем появления плеера и пытаемся его "активировать"
                await asyncio.sleep(8) 
                
                # Клик по центру страницы (активация плеера)
                await page.mouse.click(640, 360)
                
                # Пробуем нажать во всех фреймах (плеер часто в iframe)
                for frame in page.frames:
                    try:
                        await frame.click("body", timeout=1000)
                    except:
                        continue

                # Ожидание ссылки до 15 секунд
                for _ in range(15):
                    if current_stream_url: break
                    await asyncio.sleep(1)

                if current_stream_url:
                    playlist_streams.append((name, current_stream_url))
                    print(f"   [OK] Ссылка получена")
                else:
                    # Попытка через клавиатуру
                    await page.keyboard.press("Space")
                    await asyncio.sleep(4)
                    if current_stream_url:
                        playlist_streams.append((name, current_stream_url))
                        print(f"   [OK] Ссылка получена (Space)")
                    else:
                        print(f"   [!] Поток не найден")

            except Exception as e:
                print(f"   [!] Ошибка на {name}: {e}")

            page.remove_listener("request", handle_request)
            # Рандомная пауза, чтобы не забанили
            await asyncio.sleep(random.uniform(3, 5))

        # Сохранение в файл
        if playlist_streams:
            filename = "smotrettv_full.m3u"
            with open(filename, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for n, l in playlist_streams: 
                    f.write(f'#EXTINF:-1, {n}\n{l}\n')
            print(f"\n>>> Готово! Собрано каналов: {len(playlist_streams)}")
            print(f"Файл сохранен как: {filename}")
        else:
            print("\n[!] Не удалось поймать ни одного потока.")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())

