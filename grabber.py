import asyncio
import os
import re
from playwright.async_api import async_playwright

CHANNELS = {
    "Первый канал": "https://smotrettv.com/tv/public/1003-pervyj-kanal.html",
    "Россия 1": "https://smotrettv.com/tv/public/784-rossija-1.html",
    "Звезда": "https://smotrettv.com/tv/public/310-zvezda.html",
    "ТНТ": "https://smotrettv.com/tv/entertainment/329-tnt.html",
    "Россия 24": "https://smotrettv.com/tv/news/217-rossija-24.html",
    "СТС": "https://smotrettv.com/tv/entertainment/783-sts.html",
    "НТВ": "https://smotrettv.com/tv/public/6-ntv.html",
    "Рен ТВ": "https://smotrettv.com/tv/public/316-ren-tv.html"
}

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

async def run():
    async with async_playwright() as p:
        # Запускаем с опцией, которая лучше обходит детекторы ботов (только в Linux)
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = await browser.new_context(user_agent=UA, viewport={'width': 1280, 'height': 720})
        page = await context.new_page()
        page.set_default_timeout(60000)

        print("Авторизация...")
        try:
            await page.goto("https://smotrettv.com/login", wait_until="domcontentloaded")
            
            # --- ОТЛАДКА ---
            # Делаем скриншот, чтобы увидеть, что происходит на странице
            await page.screenshot(path="debug_login_page.png")
            # --- /ОТЛАДКА ---

            # Попробуйте этот альтернативный селектор, если 'input[name="email"]' не работает
            email_selector = 'input[name="email"]'
            if not await page.is_visible(email_selector):
                print(f"Селектор {email_selector} не виден, пробуем альтернативы.")
                email_selector = 'input[type="email"]' # Поиск по типу

            await page.fill(email_selector, os.getenv('LOGIN', 'your_login'))
            await page.fill('input[name="password"]', os.getenv('PASSWORD', 'your_password'))
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")
        except Exception as e:
            print(f"Предупреждение при логине: {e}")

        playlist = "#EXTM3U\n"
        
        for name, url in CHANNELS.items():
            print(f"Обработка: {name}")
            stream_url_container = {"url": None}

            async def intercept_request(request):
                # Ищем реальный m3u8 с токеном в трафике
                if ".m3u8" in request.url and "token=" in request.url:
                    stream_url_container["url"] = request.url

            page.on("request", intercept_request)
            
            try:
                await page.goto(url, wait_until="commit")
                
                # Имитируем клик по плееру, чтобы вызвать запрос потока
                try:
                    await page.click(".vjs-big-play-button", timeout=5000)
                except:
                    pass

                # Ждем перехвата ссылки 15 секунд
                for _ in range(15):
                    if stream_url_container["url"]:
                        break
                    await asyncio.sleep(1)
                
                if stream_url_container["url"]:
                    stream = stream_url_container["url"]
                    # Добавляем необходимые заголовки прямо в плейлист для плеера
                    playlist += f'#EXTINF:-1, {name}\n'
                    playlist += f'#EXTVLCOPT:http-user-agent={UA}\n'
                    playlist += f'#EXTVLCOPT:http-referrer=https://smotrettv.com/\n'
                    # ИСПРАВЛЕНО: Правильный формат для OTT/TiviMate
                    playlist += f'{stream}|Referer=smotrettv.com{UA}\n'
                    print(f"Успех: {name}")
                else:
                    print(f"Токен для {name} не найден")
            
            except Exception as e:
                print(f"Ошибка: {e}")
            finally:
                page.remove_listener("request", intercept_request)

        with open("playlist_8f2d9k1l.m3u", "w", encoding="utf-8") as f:
            f.write(playlist)
        
        await browser.close()
        print("\nГотово. Файл: playlist_8f2d9k1l.m3u")

if __name__ == "__main__":
    asyncio.run(run())
        print("\nГотово. Файл: playlist_8f2d9k1l.m3u")

if __name__ == "__main__":
    asyncio.run(run())
