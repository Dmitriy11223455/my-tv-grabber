import asyncio
import datetime
import random
from playwright.async_api import async_playwright

# Актуальный Chrome User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

async def get_all_channels_from_site(page):
    print(">>> [1/3] Поиск списка каналов...", flush=True)
    try:
        await page.goto("https://smotrettv.com", wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        
        found_channels = {}
        links = await page.query_selector_all("a")
        for link in links:
            try:
                url = await link.get_attribute("href")
                name = await link.inner_text()
                if url and name:
                    clean_name = name.strip().split('\n')[0].upper()
                    if len(clean_name) > 1 and any(x in url for x in ['/public/', '/news/', '/sport/', '/entertainment/']):
                        full_url = url if url.startswith("http") else f"https://smotrettv.com{url}"
                        if clean_name not in found_channels:
                            found_channels[clean_name] = full_url
            except: continue
        
        print(f"    [+] Найдено: {len(found_channels)}", flush=True)
        return found_channels
    except Exception as e:
        print(f"[!] Ошибка главной: {e}", flush=True)
        return {}

async def get_tokens_and_make_playlist():
    async with async_playwright() as p:
        print(">>> [2/3] Запуск Stealth-браузера...", flush=True)
        
        browser = await p.chromium.launch(headless=True, args=[
            '--no-sandbox', 
            '--disable-blink-features=AutomationControlled'
        ])
        
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1280, 'height': 720},
            locale="ru-RU"
        )
        
        # Маскировка под реального человека
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        temp_page = await context.new_page()
        CHANNELS = await get_all_channels_from_site(temp_page)
        await temp_page.close()

        if not CHANNELS:
            await browser.close()
            return

        print(f"\n>>> [3/3] Сбор ссылок (Россия 1, НТВ, РЕН)...", flush=True)
        results = []
        
        # Берем первые 20 каналов
        target_channels = list(CHANNELS.items())[:20]
        
        for name, url in target_channels:
            ch_page = await context.new_page()
            captured_urls = []

            async def handle_request(request):
                u = request.url
                # Фильтруем m3u8, игнорируя мусор
                if ".m3u8" in u and not any(x in u for x in ["ads", "log", "stat", "yandex", "metrika", "telemetry"]):
                    captured_urls.append(u)

            ch_page.on("request", handle_request)
            print(f"[*] {name:.<25}", end=" ", flush=True)

            try:
                # Переходим на страницу
                await ch_page.goto(url, wait_until="commit", timeout=45000)
                await asyncio.sleep(random.uniform(5, 7))
                
                # ЛЕЧЕНИЕ FAIL: Ищем реальную кнопку Play или видео
                play_selectors = ["video", ".vjs-big-play-button", "div[class*='play']", "button[class*='play']", "canvas"]
                success_click = False
                
                for selector in play_selectors:
                    try:
                        target = await ch_page.wait_for_selector(selector, timeout=2000)
                        if target:
                            await target.click()
                            success_click = True
                            break
                    except: continue
                
                if not success_click:
                    await ch_page.mouse.click(640, 360) # Клик в центр если ничего не нашли

                # Даем время на прогрузку потока (особенно для России 1)
                for _ in range(15):
                    if captured_urls: break
                    await asyncio.sleep(1)

                if captured_urls:
                    # Выбираем самую длинную ссылку (обычно там больше параметров защиты)
                    final_link = max(captured_urls, key=len)
                    results.append((name, final_link))
                    print("OK", flush=True)
                else:
                    # Делаем скриншот для отладки, если FAIL
                    # await ch_page.screenshot(path=f"fail_{name[:3]}.png")
                    print("FAIL", flush=True)
            except:
                print("ERR", flush=True)
            finally:
                await ch_page.close()
                await asyncio.sleep(1) # Пауза между каналами

        # Запись плейлиста с "лекарством" от буферизации
        if results:
            filename = "playlist.m3u"
            with open(filename, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n\n")
                for n, l in results:
                    f.write(f'#EXTINF:-1, {n}\n')
                    # Прокидываем Referer и UA прямо в ссылку через пайп
                    f.write(f'{l}|Referer=https://smotrettv.com{USER_AGENT}\n\n')
            
            print(f"\n>>> ГОТОВО! Плейлист создан. Найдено: {len(results)}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())








































































































































































