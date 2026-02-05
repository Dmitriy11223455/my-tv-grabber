import asyncio
import random
import datetime
from playwright.async_api import async_playwright

# Используем мобильный агент, так как он стабильнее для этого сайта
USER_AGENT = "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36"

async def get_all_channels_from_site(page):
    """Автоматический сбор всех доступных каналов с прокруткой"""
    now = lambda: datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now()}] >>> Начинаю поиск всех каналов на сайте...")
    
    try:
        # Заходим на главную (используем зеркало smotret.tv для надежности)
        await page.goto("https://smotret.tv", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        
        # Прокручиваем страницу 5 раз, чтобы подгрузить "ленивые" карточки каналов
        for i in range(1, 6):
            await page.mouse.wheel(0, 3000)
            print(f"[{now()}] >>> Прокрутка страницы для подгрузки ({i}/5)...")
            await asyncio.sleep(2)

        # Собираем ссылки по паттерну .html (страницы каналов)
        links = await page.query_selector_all("a[href*='.html']")
        found_channels = {}
        
        for el in links:
            url = await el.get_attribute("href")
            name = await el.get_attribute("title") or await el.inner_text()
            
            if url and name:
                # Фильтруем служебные ссылки
                if any(x in url for x in ["contact", "about", "rules", "dmca", "copyright", "feedback"]): 
                    continue
                
                full_url = url if url.startswith("http") else f"https://smotret.tv{url}"
                clean_name = name.strip().split('\n')[0] # Берем чистое название
                
                # Имя канала должно быть длиннее 2 символов
                if len(clean_name) > 2 and full_url not in found_channels.values():
                    found_channels[clean_name] = full_url
        
        print(f"[{now()}] [OK] Всего найдено каналов: {len(found_channels)}")
        return found_channels
    except Exception as e:
        print(f"[{now()}] [!] Ошибка при сборе списка: {e}")
        return {}

async def get_tokens_and_make_playlist():
    async with async_playwright() as p:
        now_ts = lambda: datetime.datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now_ts()}] >>> Запуск граббера...")
        
        # Запуск браузера (Chromium для GitHub Actions)
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 450, 'height': 900},
            is_mobile=True,
            has_touch=True
        )
        page = await context.new_page()
        
        # 1. Автоматически собираем список всех каналов
        CHANNELS = await get_all_channels_from_site(page)
        
        if not CHANNELS:
            print(f"[{now_ts()}] [!] Список каналов пуст. Проверьте доступность сайта.")
            await browser.close()
            return

        # Блокируем картинки, чтобы ускорить процесс граббинга
        await page.route("**/*.{png,jpg,jpeg,gif,webp,svg}", lambda route: route.abort())

        playlist_results = []
        target_list = list(CHANNELS.items())
        total = len(target_list)

        # 2. Перебираем все найденные каналы
        for counter, (name, url) in enumerate(target_list, 1):
            print(f"[{now_ts()}] [{counter}/{total}] Граббинг: {name}")
            current_stream = None

            async def catch_m3u8(request):
                nonlocal current_stream
                u = request.url
                # Твоя старая рабочая логика захвата
                if ".m3u8" in u and len(u) > 50:
                    if not any(x in u for x in ["/ads/", "track", "pixel", "telemetree"]):
                        if not current_stream:
                            current_stream = u
                            print(f"   [+] Поток найден!")

            page.on("request", catch_m3u8)
            
            try:
                # Заходим на страницу канала
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(8)
                
                # Клик для активации потока
                await page.mouse.click(225, 350)
                await asyncio.sleep(6)
                
                if current_stream:
                    playlist_results.append((name, current_stream))
                else:
                    # Вторая попытка клика, если не поймали сразу
                    await page.mouse.click(225, 450)
                    await asyncio.sleep(4)
                    if current_stream:
                        playlist_results.append((name, current_stream))

            except Exception as e:
                print(f"   [!] Ошибка: {e}")
            
            page.remove_listener("request", catch_m3u8)
            await asyncio.sleep(1)

        # 3. Сохраняем результат в файл для ТВ
        if playlist_results:
            with open("playlist.m3u", "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for n, l in playlist_results:
                    # Добавляем Referer для работы на ТВ
                    f.write(f'#EXTINF:-1, {n}\n{l}|Referer=https://smotrettv.com{USER_AGENT}\n')
            print(f"\n[{now_ts()}] >>> Успех! Собрано {len(playlist_results)} каналов.")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())








