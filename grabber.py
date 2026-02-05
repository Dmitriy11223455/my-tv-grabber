import asyncio
import random
from playwright.async_api import async_playwright

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def get_all_channels_from_site(page):
    """Сборщик всех ссылок с главной страницы"""
    print(">>> Сбор списка каналов...")
    try:
        await page.goto("https://smotrettv.com", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        
        # Подгружаем ленивый контент
        for _ in range(3):
            await page.mouse.wheel(0, 2000)
            await asyncio.sleep(1)

        found_channels = {}
        # Ищем карточки каналов
        links = await page.query_selector_all("a.short-item")
        
        for link in links:
            name = await link.get_attribute("title")
            url = await link.get_attribute("href")
            
            if url and name:
                full_url = url if url.startswith("http") else f"https://smotrettv.com{url}"
                found_channels[name.strip()] = full_url
            
        return found_channels
    except Exception as e:
        print(f"[!] Ошибка сбора: {e}")
        return {}

async def get_tokens_and_make_playlist():
    async with async_playwright() as p:
        print(">>> Запуск браузера...")
        browser = await p.chromium.launch(headless=True)
        
        # Исправлено: удален permissions=["autoplay"], вызывавший ошибку
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1280, 'height': 720}
        )
        page = await context.new_page()
        
        # Блокируем картинки для экономии трафика и времени
        await page.route("**/*.{png,jpg,jpeg,gif,webp,svg}", lambda route: route.abort())

        CHANNELS = await get_all_channels_from_site(page)
        
        if not CHANNELS:
            print("[!] Список каналов пуст.")
            await browser.close()
            return

        print(f"[OK] Найдено каналов: {len(CHANNELS)}")
        
        playlist_results = []

        for name, url in CHANNELS.items():
            print(f"[*] Граббинг: {name}")
            stream_url = None

            async def catch_m3u8(request):
                nonlocal stream_url
                u = request.url
                if ".m3u8" in u and not any(x in u for x in ["ads", "telemetree", "analyt"]):
                    stream_url = u

            page.on("request", catch_m3u8)
            
            try:
                # 1. Первый заход (прогрев)
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(4)
                
                # 2. Перезагрузка (имитация второго ручного запуска для качества)
                await page.reload(wait_until="domcontentloaded")
                await asyncio.sleep(5)
                
                # Клик по плееру
                await page.mouse.click(640, 360)
                
                # Проверка фреймов
                for frame in page.frames:
                    try:
                        v = await frame.query_selector("video")
                        if v: await v.click()
                    except: pass
                
                # Ожидание ссылки
                for _ in range(15):
                    if stream_url: break
                    await asyncio.sleep(1)
                
                if stream_url:
                    playlist_results.append((name, stream_url))
                    print(f"   + Поймал!")
                else:
                    print(f"   - Не найден")
            except Exception as e:
                print(f"   ! Ошибка на канале: {e}")
            
            page.remove_listener("request", catch_m3u8)
            await asyncio.sleep(1)

        # Сохранение результата
        if playlist_results:
            with open("playlist.m3u", "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for n, l in playlist_results:
                    # Формат с Referer для работы на ТВ и в браузерных плеерах
                    f.write(f'#EXTINF:-1, {n}\n{l}|Referer=https://smotrettv.com&User-Agent={USER_AGENT}\n')
            print(f"\n>>> Успех! Собрано {len(playlist_results)} каналов. Файл playlist.m3u обновлен.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())





