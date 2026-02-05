import asyncio
import random
import datetime
from playwright.async_api import async_playwright

# Используем мобильный User-Agent (Android), сайт доверяет им больше
USER_AGENT = "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36"

async def get_all_channels_from_site(page):
    now = lambda: datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now()}] >>> Поиск каналов в мобильном режиме...")
    
    for attempt in range(1, 4):
        try:
            # Заходим с имитацией обычного пользователя
            await page.goto("https://smotrettv.com", wait_until="domcontentloaded", timeout=40000)
            
            # Ждем появления любого элемента ссылки (на мобильных класс может быть другим, ищем по href)
            print(f"[{now()}] Проверка структуры страницы (попытка {attempt})...")
            await asyncio.sleep(7) # Даем JS время отрисовать сетку
            
            # Собираем ссылки по паттерну, а не только по классу
            links = await page.query_selector_all("a[href*='.html']")
            
            found_channels = {}
            for el in links:
                url = await el.get_attribute("href")
                name = await el.get_attribute("title") or await el.inner_text()
                
                # Фильтруем только страницы каналов (обычно цифры в начале)
                if url and name and any(c.isdigit() for c in url):
                    full_url = url if url.startswith("http") else f"https://smotrettv.com{url}"
                    if "smotrettv.com" in full_url and len(name.strip()) > 2:
                        found_channels[name.strip().split('\n')[0]] = full_url
            
            if found_channels:
                print(f"[{now()}] [OK] Найдено каналов: {len(found_channels)}")
                return found_channels
                
        except Exception as e:
            print(f"[{now()}] [!] Ошибка: {e}")
            await asyncio.sleep(5)
            
    return {}

async def get_tokens_and_make_playlist():
    async with async_playwright() as p:
        now_ts = lambda: datetime.datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now_ts()}] >>> Запуск в режиме маскировки...")
        
        # Эмулируем мобильный девайс для обхода блокировок
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 450, 'height': 900},
            is_mobile=True,
            has_touch=True
        )
        page = await context.new_page()
        
        # Сбор списка
        CHANNELS = await get_all_channels_from_site(page)
        
        if not CHANNELS:
            print(f"[{now_ts()}] [!] Сайт заблокировал доступ. Попробуйте сменить регион в YAML или использовать VPN.")
            await browser.close()
            return

        # Блокируем картинки только после получения списка
        await page.route("**/*.{png,jpg,jpeg,gif,webp,svg}", lambda route: route.abort())

        playlist_results = []
        target_list = list(CHANNELS.items())

        for counter, (name, url) in enumerate(target_list, 1):
            print(f"[{now_ts()}] [{counter}/{len(target_list)}] Граббинг: {name}")
            current_stream = None

            async def catch_m3u8(request):
                nonlocal current_stream
                if ".m3u8" in request.url and "ads" not in request.url:
                    current_stream = request.url

            page.on("request", catch_m3u8)
            
            try:
                await page.goto(url, wait_until="commit", timeout=25000)
                await asyncio.sleep(6)
                
                # На мобилках клик обязателен
                await page.mouse.click(200, 300)
                await asyncio.sleep(5)
                
                if current_stream:
                    playlist_results.append((name, current_stream))
                    print(f"   [+] Поток найден")
                
            except: pass
            page.remove_listener("request", catch_m3u8)

        if playlist_results:
            with open("playlist.m3u", "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                for n, l in playlist_results:
                    f.write(f'#EXTINF:-1, {n}\n{l}|Referer=https://smotrettv.com&User-Agent={USER_AGENT}\n')
            print(f"[{now_ts()}] Плейлист обновлен: {len(playlist_results)} каналов.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())





