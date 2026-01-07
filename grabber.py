import asyncio
import os
from playwright.async_api import async_playwright

# Словарь: Название -> (URL страницы, ID канала для формулы)
CHANNELS = {
    "Первый канал": ("https://smotrettv.com/tv/public/1003-pervyj-kanal.html", "1003"),
    "Россия 1": ("https://smotrettv.com/tv/public/784-rossija-1.html", "784"),
    "Звезда": ("https://smotrettv.com/tv/public/310-zvezda.html", "310"),
    "ТНТ": ("https://smotrettv.com/tv/entertainment/329-tnt.html", "329"),
    "Россия 24": ("https://smotrettv.com/tv/news/217-rossija-24.html", "217"),
    "СТС": ("https://smotrettv.com/tv/entertainment/783-sts.html", "783"),
    "НТВ": ("https://smotrettv.com/tv/public/6-ntv.html", "6"),
    "Рен ТВ": ("https://smotrettv.com/tv/public/316-ren-tv.html", "316")
}

# Формула ссылки (актуальна на 2026 год)
STREAM_FORMULA = "https://server.smotrettv.com/{channel_id}.m3u8?token={token}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

async def grab_token(context, name, page_url, channel_id):
    page = await context.new_page()
    # Отключаем медиа для мгновенной загрузки
    await page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff2}", lambda route: route.abort())
    
    token = None

    def handle_request(request):
        nonlocal token
        # Ищем токен в любом m3u8 запросе на странице
        if "token=" in request.url and ".m3u8" in request.url:
            try:
                # Извлекаем токен из параметров URL
                token = request.url.split("token=")[1].split("&")[0]
            except:
                pass

    page.on("request", handle_request)
    
    try:
        print(f"[*] Получаю токен для: {name}")
        await page.goto(page_url, wait_until="domcontentloaded", timeout=45000)
        
        # Ждем появления токена (обычно 2-5 секунд)
        for _ in range(10):
            if token: break
            await asyncio.sleep(1)

        if token:
            # Собираем ссылку по формуле
            final_url = STREAM_FORMULA.format(channel_id=channel_id, token=token)
            print(f"[+] {name}: Токен получен")
            return f'#EXTINF:-1, {name}\n#EXTVLCOPT:http-user-agent={UA}\n#EXTVLCOPT:http-referrer=smotrettv.com\n{final_url}\n'
        else:
            print(f"[-] {name}: Токен не найден")
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

        print(">>> Авторизация на smotrettv.comlogin")
        try:
            await page.goto("https://smotrettv.comlogin", timeout=60000)
            await page.fill('input[name="email"]', login)
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"]')
            await asyncio.sleep(5)
        except Exception as e:
            print(f">>> Ошибка входа: {e}")

        # Запускаем все задачи параллельно
        tasks = [grab_token(context, name, url, cid) for name, (url, cid) in CHANNELS.items()]
        results = await asyncio.gather(*tasks)

        playlist_data = "#EXTM3U\n" + "".join(results)
        with open("playlist.m3u", "w", encoding="utf-8") as f:
            f.write(playlist_data)
        
        await browser.close()
        print(">>> Плейлист готов и сохранен.")

if __name__ == "__main__":
    asyncio.run(run())
