import asyncio
import random
from playwright.async_api import async_playwright

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def get_all_channels_from_site(page):
    """Сборщик всех ссылок с главной страницы"""
    print(">>> Сбор списка каналов...")
    try:
        await page.goto("https://smotrettv.com/", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        
        for _ in range(3):
            await page.mouse.wheel(0, 2000)
            await asyncio.sleep(1)

        found_channels = {}
        # Универсальный селектор для всех категорий
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
        context = await browser.new_context(user_agent=USER_AGENT, permissions=["autoplay"])
        page = await context.new_page()
        
        # Блокируем только тяжелые картинки, чтобы не ломать логику плеера
        await page.route("**/*.{png,jpg,jpeg,gif,webp,svg}", lambda route: route.abort())

        CHANNELS = await get_all_channels_from_site(page)
        
        if not CHANNELS:
            print("[!] Список пуст.")
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
                # --- ЛОГИКА ПРОГРЕВА (ДЛЯ КАЧЕСТВА) ---
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(4)
                
                # Перезагрузка для "чистого" потока (как второй ручной запуск)
                await page.reload(wait_until="domcontentloaded")
                await asyncio.sleep(5)
                
                # Клик по центру для старта
                await page.mouse.click(640, 400)
                
                # Пробиваем фреймы (для РенТВ, СТС, ТНТ)
                for frame in page.frames:
                    try:
                        v = await frame.query_selector("video")
                        if v: await v.click()
                    except: pass
                
                for _ in range(15):
                    if stream_url: break
                    await asyncio.sleep(1)
                
                if stream_url:
                    playlist_results.append((name, stream_url))
                    print(f"   + Поймал!")
                else:
                    print(f"   - Пропуск")
            except:
                print(f"   ! Ошибка")
            
            page.remove_listener("request", catch_m3u8)
            await asyncio.sleep(1)

        if playlist_results:
            # Сохраняем в основной файл плейлиста
            with open("playlist.m3u", "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for n, l in playlist_results:
                    # Добавляем заголовки для работы на ТВ
                    f.write(f'#EXTINF:-1, {n}\n{l}|Referer=https://smotrettv.com{USER_AGENT}\n')
            print(f"\n>>> Собрано {len(playlist_results)} каналов. Файл playlist.m3u готов.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())





