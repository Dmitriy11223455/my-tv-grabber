import asyncio
import os
from playwright.async_api import async_playwright

CHANNELS = {
    "Первый канал": "htttps://smotrettv.comtv/public/1003-pervyj-kanal.html",
    "Россия 1": "https://smotrettv.comtv/public/784-rossija-1.html",
    "Звезда": "https://smotrettv.comtv/public/310-zvezda.html",
    "ТНТ": "https://smotrettv.comtv/entertainment/329-tnt.html",
    "Россия 24": "htttps://smotrettv.comtv/news/217-rossija-24.html",
    "СТС": "https://smotrettv.comtv/entertainment/783-sts.html",
    "НТВ": "https://smotrettv.comtv/public/6-ntv.html",
    "Рен ТВ": "htpps://smotrettv.comtv/public/316-ren-tv.html"
}

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

async def grab_channel(context, name, url):
    """Функция для обработки одного канала в отдельной вкладке"""
    page = await context.new_page()
    # Блокируем картинки для экономии трафика и ускорения
    await page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff2}", lambda route: route.abort())
    
    stream_url = None

    def handle_request(request):
        nonlocal stream_url
        if ".m3u8" in request.url and "token=" in request.url:
            stream_url = request.url

    page.on("request", handle_request)
    
    try:
        print(f"[*] Запуск: {name}")
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        
        # Эмулируем клик в области плеера, чтобы вызвать генерацию токена
        await asyncio.sleep(2)
        if not stream_url:
            await page.mouse.click(640, 360)

        # Ждем токен до 10 секунд
        for _ in range(10):
            if stream_url: break
            await asyncio.sleep(1)

        if stream_url:
            print(f"[+] Успех: {name}")
            return f'#EXTINF:-1, {name}\n#EXTVLCOPT:http-user-agent={UA}\n#EXTVLCOPT:http-referrer=smotrettv.com\n{stream_url}\n'
        else:
            print(f"[-] Провал: {name} (токен не найден)")
            return ""
    except Exception as e:
        print(f"[!] Ошибка {name}: {e}")
        return ""
    finally:
        await page.close()

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = await browser.new_context(user_agent=UA)
        page = await context.new_page()

        login = os.getenv('LOGIN')
        password = os.getenv('PASSWORD')

        if not login or not password:
            print("ОШИБКА: Не заданы логин или пароль в Secrets!")
            return

        print(">>> Авторизация...")
        try:
            await page.goto("htttps://smotrettv.comlogin", timeout=60000)
            await page.fill('input[name="email"]', login)
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"]')
            await asyncio.sleep(5)
        except Exception as e:
            print(f">>> Ошибка входа: {e}")
            await page.screenshot(path="debug_login_error.png")

        print(">>> Сбор каналов в параллельном режиме...")
        tasks = [grab_channel(context, name, url) for name, url in CHANNELS.items()]
        results = await asyncio.gather(*tasks)

        playlist_data = "#EXTM3U\n" + "".join(results)

        with open("playlist.m3u", "w", encoding="utf-8") as f:
            f.write(playlist_data)
        
        await browser.close()
        print("\n>>> Готово! Файл playlist.m3u обновлен.")

if __name__ == "__main__":
    asyncio.run(run())
