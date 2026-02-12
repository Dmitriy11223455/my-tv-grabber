import asyncio
import datetime
import sys
from playwright.async_api import async_playwright

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"

async def get_all_channels_from_site(page):
    print(">>> [1/3] Поиск списка каналов...", flush=True)
    try:
        # Заходим на главную
        await page.goto("https://smotrettv.com", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        
        found_channels = {}
        # Собираем ссылки на каналы
        links = await page.query_selector_all("a")
        for link in links:
            try:
                url = await link.get_attribute("href")
                name = await link.inner_text()
                if url and name:
                    clean_name = name.strip().split('\n')[0].upper()
                    # Фильтр разделов
                    if len(clean_name) > 1 and any(x in url for x in ['/public/', '/news/', '/sport/', '/entertainment/']):
                        full_url = url if url.startswith("http") else f"https://smotrettv.com{url}"
                        if clean_name not in found_channels:
                            found_channels[clean_name] = full_url
            except: continue
        
        print(f"    [+] Найдено каналов: {len(found_channels)}", flush=True)
        return found_channels
    except Exception as e:
        print(f"[!] Ошибка главной: {e}", flush=True)
        return {}

async def get_tokens_and_make_playlist():
    async with async_playwright() as p:
        print(">>> [2/3] Инициализация браузера...", flush=True)
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        
        # 1. Получаем список каналов
        init_ctx = await browser.new_context(user_agent=USER_AGENT)
        temp_page = await init_ctx.new_page()
        # Маскировка webdriver
        await temp_page.add_init_script("delete navigator.__proto__.webdriver")
        
        CHANNELS = await get_all_channels_from_site(temp_page)
        await init_ctx.close()

        if not CHANNELS:
            await browser.close()
            return

        print(f"\n>>> [3/3] Сбор прямых ссылок (полная изоляция)...", flush=True)
        results = []
        
        # Обрабатываем первые 20 каналов
        for name, url in list(CHANNELS.items())[:20]:
            # НОВЫЙ КОНТЕКСТ ДЛЯ КАЖДОГО КАНАЛА (Гарантия отсутствия дублей контента)
            ch_ctx = await browser.new_context(
                user_agent=USER_AGENT,
                viewport={'width': 1280, 'height': 720}
            )
            ch_page = await ch_ctx.new_page()
            await ch_page.add_init_script("delete navigator.__proto__.webdriver")
            
            stream_data = {"url": None}

            async def handle_request(request):
                u = request.url
                # Ловим m3u8, исключая рекламу и яндекс
                if ".m3u8" in u and not any(x in u for x in ["ads", "log", "stat", "yandex", "metrika"]):
                    if any(k in u for k in ["token", "master", "index", "chunklist", "playlist"]):
                        stream_data["url"] = u

            ch_page.on("request", handle_request)
            print(f"[*] {name:.<25}", end=" ", flush=True)

            try:
                # Переход на страницу канала
                await ch_page.goto(url, wait_until="domcontentloaded", timeout=45000)
                
                # Имитация человеческих действий для активации плеера
                await asyncio.sleep(4)
                await ch_page.mouse.wheel(0, 300) # Скролл к плееру
                await asyncio.sleep(2)
                
                # Пытаемся кликнуть в центр экрана несколько раз (разные точки)
                points = [(640, 360), (600, 300), (700, 400)]
                for x, y in points:
                    if stream_data["url"]: break
                    await ch_page.mouse.click(x, y)
                    await asyncio.sleep(1.5)

                # Ждем ссылку до упора
                for _ in range(12):
                    if stream_data["url"]: break
                    await asyncio.sleep(1)

                if stream_data["url"]:
                    results.append((name, stream_data["url"]))
                    print("OK", flush=True)
                else:
                    print("FAIL", flush=True)
            except:
                print("ERR", flush=True)
            finally:
                # Полная очистка сессии канала
                await ch_ctx.close()

        # Сохранение плейлиста
        if results:
            filename = "playlist.m3u"
            with open(filename, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                f.write(f'{l}|Referer=https://smotrettv.com{USER_AGENT}\n')
                for n, l in results:
                    f.write(f"#EXTINF:-1, {n}\n{l}\n")
            print(f"\n>>> ГОТОВО! Файл {filename} создан. Найдено: {len(results)}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())





























