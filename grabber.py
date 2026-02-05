import asyncio
import random
import datetime
from playwright.async_api import async_playwright

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def get_all_channels_from_site(page):
    """Сверхнастойчивый сборщик ссылок с обходом таймаутов"""
    now = lambda: datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now()}] >>> Начинаю сканирование главной страницы...")
    
    for attempt in range(1, 4):
        try:
            print(f"[{now()}] Попытка {attempt}/3: Загрузка страницы...")
            # Используем domcontentloaded вместо networkidle, чтобы не ждать рекламу
            await page.goto("https://smotrettv.com", wait_until="domcontentloaded", timeout=40000)
            
            print(f"[{now()}] Ожидаю появления сетки каналов...")
            await page.wait_for_selector("a.short-item", timeout=15000)
            
            # Быстрая прокрутка для подгрузки списка
            for i in range(1, 4):
                await page.mouse.wheel(0, 2500)
                await asyncio.sleep(1)

            found_channels = {}
            elements = await page.query_selector_all("a.short-item")
            
            for el in elements:
                name = await el.get_attribute("title")
                url = await el.get_attribute("href")
                if url and name:
                    full_url = url if url.startswith("http") else f"https://smotrettv.com{url}"
                    name_clean = name.strip()
                    if full_url not in found_channels.values():
                        found_channels[name_clean] = full_url
            
            if found_channels:
                print(f"[{now()}] [OK] Найдено каналов: {len(found_channels)}")
                return found_channels
                
        except Exception as e:
            print(f"[{now()}] [!] Ошибка на попытке {attempt}: {e}")
            await asyncio.sleep(5)
            
    return {}

async def get_tokens_and_make_playlist():
    async with async_playwright() as p:
        now_ts = lambda: datetime.datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now_ts()}] >>> Запуск браузера...")
        
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT, viewport={'width': 1280, 'height': 720})
        page = await context.new_page()
        
        # Сбор списка каналов
        CHANNELS = await get_all_channels_from_site(page)
        
        if not CHANNELS:
            print(f"[{now_ts()}] [!] Список пуст. Возможно, IP GitHub заблокирован. Завершаю.")
            await browser.close()
            return

        # Блокировка тяжелого контента для экономии времени при граббинге
        await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2}", lambda route: route.abort())

        playlist_results = []
        target_list = list(CHANNELS.items())
        total = len(target_list)

        for counter, (name, url) in enumerate(target_list, 1):
            ts = now_ts()
            print(f"\n[{ts}] [{counter}/{total}] ОБРАБОТКА: {name}")
            
            current_stream = None

            async def catch_m3u8(request):
                nonlocal current_stream
                u = request.url
                if ".m3u8" in u and not any(x in u for x in ["ads", "telemetree", "analyt", "track"]):
                    if not current_stream:
                        current_stream = u
                        print(f"   [+] Поймал поток!")

            page.on("request", catch_m3u8)
            
            try:
                # Этап 1: Заход (быстрый переход)
                await page.goto(url, wait_until="commit", timeout=25000)
                await asyncio.sleep(4)
                
                # Этап 2: Прогрев/Перезагрузка
                await page.reload(wait_until="domcontentloaded", timeout=25000)
                await asyncio.sleep(5)
                
                # Этап 3: Клик по плееру
                await page.mouse.click(640, 360)
                
                for frame in page.frames:
                    try:
                        v = await frame.query_selector("video")
                        if v: await v.click()
                    except: pass
                
                # Ожидание ссылки
                for i in range(1, 13):
                    if current_stream: break
                    await asyncio.sleep(1)
                
                if current_stream:
                    playlist_results.append((name, current_stream))
                else:
                    print(f"   [-] Поток не найден.")
                    
            except Exception as e:
                print(f"   [ERROR] Ошибка загрузки: {e}")
            
            page.remove_listener("request", catch_m3u8)
            await asyncio.sleep(1)

        # Сохранение плейлиста
        if playlist_results:
            with open("playlist.m3u", "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for n, l in playlist_results:
                    f.write(f'#EXTINF:-1, {n}\n{l}|Referer=https://smotrettv.com&User-Agent={USER_AGENT}\n')
            print(f"\n[{now_ts()}] >>> ИТОГ: Собрано {len(playlist_results)} каналов.")
        else:
            print(f"\n[{now_ts()}] [!] Ссылки не найдены.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())





