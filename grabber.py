import asyncio
import random
import datetime
from playwright.async_api import async_playwright

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

async def get_all_channels_from_site(page):
    """Сборщик всех ссылок с главной страницы"""
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] >>> Начинаю сканирование главной страницы...")
    try:
        await page.goto("https://smotrettv.com", wait_until="networkidle", timeout=60000)
        
        print(f"[{now}] >>> Ожидаю появления сетки каналов...")
        try:
            await page.wait_for_selector("a.short-item", timeout=20000)
        except:
            print(f"[{now}] [!] Элементы a.short-item не найдены. Сайт может быть под защитой.")

        for i in range(1, 6):
            await page.mouse.wheel(0, 2000)
            print(f"[{now}] >>> Прокрутка страницы ({i}/5)...")
            await asyncio.sleep(1)

        found_channels = {}
        elements = await page.query_selector_all("a.short-item")
        
        for el in elements:
            name = await el.get_attribute("title")
            url = await el.get_attribute("href")
            
            if url and name:
                full_url = url if url.startswith("http") else f"https://smotrettv.com{url}"
                clean_name = name.strip()
                if full_url not in found_channels.values():
                    found_channels[clean_name] = full_url
            
        print(f"[{now}] [OK] Сбор завершен. Найдено уникальных каналов: {len(found_channels)}")
        return found_channels
    except Exception as e:
        print(f"[{now}] [!] Ошибка при сборе списка: {e}")
        return {}

async def get_tokens_and_make_playlist():
    async with async_playwright() as p:
        print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] >>> Запуск браузера Playwright...")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=USER_AGENT, viewport={'width': 1280, 'height': 720})
        page = await context.new_page()
        
        CHANNELS = await get_all_channels_from_site(page)
        
        if not CHANNELS:
            print("[!] Список каналов пуст. Завершаю работу.")
            await browser.close()
            return

        # Включаем блокировку ресурсов после сбора списка
        await page.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2}", lambda route: route.abort())

        playlist_results = []
        total = len(CHANNELS)
        counter = 0

        for name, url in CHANNELS.items():
            counter += 1
            now = datetime.datetime.now().strftime("%H:%M:%S")
            print(f"\n[{now}] [{counter}/{total}] ОБРАБОТКА: {name}")
            print(f"[{now}] URL: {url}")
            
            stream_url = None

            async def catch_m3u8(request):
                nonlocal stream_url
                u = request.url
                if ".m3u8" in u and not any(x in u for x in ["ads", "telemetree", "analyt", "track"]):
                    if not stream_url:
                        stream_url = u
                        print(f"   [+] Поймал поток: {u[:80]}...")

            page.on("request", catch_m3u8)
            
            try:
                print(f"   > Этап 1: Первый заход (прогрев)...")
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(4)
                
                print(f"   > Этап 2: Перезагрузка страницы для качества...")
                await page.reload(wait_until="domcontentloaded")
                await asyncio.sleep(5)
                
                print(f"   > Этап 3: Попытка активации плеера...")
                await page.mouse.click(640, 400)
                
                for frame in page.frames:
                    try:
                        v = await frame.query_selector("video")
                        if v: 
                            await v.click()
                            print(f"   > Клик по видео внутри фрейма...")
                    except: pass
                
                for i in range(1, 16):
                    if stream_url: break
                    if i % 5 == 0: print(f"   ... ожидаю поток ({i} сек) ...")
                    await asyncio.sleep(1)
                
                if stream_url:
                    playlist_results.append((name, stream_url))
                    print(f"   [SUCCESS] Канал {name} успешно добавлен.")
                else:
                    print(f"   [FAILED] Поток не найден за отведенное время.")
            except Exception as e:
                print(f"   [ERROR] Ошибка: {e}")
            
            page.remove_listener("request", catch_m3u8)
            await asyncio.sleep(random.uniform(1, 2))

        # Сохранение результата
        if playlist_results:
            with open("playlist.m3u", "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for n, l in playlist_results:
                    f.write(f'#EXTINF:-1, {n}\n{l}|Referer=https://smotrettv.com&User-Agent={USER_AGENT}\n')
            print(f"\n\n[!!!] ИТОГ: Собрано {len(playlist_results)} из {total} каналов.")
            print(f"[!!!] Файл playlist.m3u успешно обновлен.")
        else:
            print("\n[!!!] КРИТИЧЕСКАЯ ОШИБКА: Не удалось собрать ни одной ссылки.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())





