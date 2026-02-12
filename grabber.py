import asyncio
import datetime
import sys
import os
import random
from playwright.async_api import async_playwright

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

async def get_all_channels_from_site(page):
    print(">>> [1/3] Поиск списка каналов...", flush=True)
    try:
        # Используем commit, чтобы не ждать вечно тяжелую рекламу
        await page.goto("https://smotrettv.com", wait_until="commit", timeout=60000)
        await asyncio.sleep(10)
        
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
        
        print(f"    [+] Найдено каналов: {len(found_channels)}", flush=True)
        return found_channels
    except Exception as e:
        print(f"[!] Ошибка главной: {e}", flush=True)
        return {}

async def get_tokens_and_make_playlist():
    async with async_playwright() as p:
        print(">>> [2/3] Инициализация браузера (Stealth Mode)...", flush=True)
        
        # Запуск с отключением признаков автоматизации
        browser = await p.chromium.launch(headless=True, args=[
            '--no-sandbox', 
            '--disable-setuid-sandbox',
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
            print("[!] Список каналов пуст. Возможно, IP GitHub заблокирован.")
            await browser.close()
            return

        print(f"\n>>> [3/3] Сбор прямых ссылок (активная эмуляция)...", flush=True)
        results = []
        
        # Берем первые 20 каналов
        for name, url in list(CHANNELS.items())[:20]:
            ch_page = await context.new_page()
            stream_data = {"url": None}

            async def handle_request(request):
                u = request.url
                # Ловим m3u8, исключая мусор
                if ".m3u8" in u and not any(x in u for x in ["ads", "log", "yandex", "metrika", "stat"]):
                    if any(k in u for k in ["token", "master", "index", "playlist", "chunklist"]):
                        stream_data["url"] = u

            ch_page.on("request", handle_request)
            print(f"[*] {name:.<25}", end=" ", flush=True)

            try:
                # Переход с ожиданием только структуры страницы
                await ch_page.goto(url, wait_until="domcontentloaded", timeout=45000)
                
                # 1. Человеческая пауза перед действием
                await asyncio.sleep(random.uniform(6, 9))
                
                # 2. Имитация движения мыши (важно для России 1)
                await ch_page.mouse.move(random.randint(0, 100), random.randint(0, 100))
                await ch_page.mouse.move(640, 360, steps=15) # Двигаем к центру плеера плавно
                
                # 3. Скролл (активирует подгрузку плеера)
                await ch_page.mouse.wheel(0, 350)
                await asyncio.sleep(2)

                # 4. Попытка нажать на кнопку Play или центр экрана
                # Сначала ищем стандартные кнопки плеера
                play_selectors = [".vjs-big-play-button", ".play-button", "video"]
                btn_clicked = False
                for sel in play_selectors:
                    try:
                        btn = await ch_page.query_selector(sel)
                        if btn and await btn.is_visible():
                            await btn.click()
                            btn_clicked = True
                            break
                    except: continue
                
                if not btn_clicked:
                    # Если кнопки не нашли - кликаем в центр наугад
                    await ch_page.mouse.click(640, 360)

                # 5. Ожидание появления ссылки в сети (до 15 сек)
                for _ in range(15):
                    if stream_data["url"]: break
                    await asyncio.sleep(1)

                if stream_data["url"]:
                    results.append((name, stream_data["url"]))
                    print("OK", flush=True)
                else:
                    # Скриншот для отладки
                    safe_name = name.replace(" ", "_").replace("/", "_")
                    await ch_page.screenshot(path=f"fail_{safe_name}.png")
                    print("FAIL (📷 saved)", flush=True)
            except Exception as e:
                print(f"ERR ({str(e)[:15]})", flush=True)
            finally:
                await ch_page.close()

        # Сохранение итогового плейлиста
        if results:
            filename = "playlist.m3u"
            with open(filename, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                f.write(f"# Сгенерировано: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
                for n, l in results:
                    # Лекарство от буферизации: принудительный Referer и User-Agent
                    f.write(f'#EXTINF:-1, {n}\n')
                    f.write(f'{l}|Referer=https://smotrettv.com{USER_AGENT}\n\n')
            print(f"\n>>> ГОТОВО! Файл {filename} создан. Найдено: {len(results)}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())





















































