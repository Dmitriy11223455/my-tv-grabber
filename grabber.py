import asyncio
import os
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

async def run():
    async with async_playwright() as p:
        # Добавляем --no-sandbox для работы в Docker/GitHub
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = await context.new_page()

        login = os.getenv('LOGIN')
        password = os.getenv('PASSWORD')

        print("Авторизация...")
        try:
            await page.goto("https://smotrettv.com/login", timeout=60000)
            await page.fill('input[name="email"]', login)
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"]')
            await asyncio.sleep(5)
        except Exception as e:
            print(f"Ошибка входа: {e}")

        playlist_data = "#EXTM3U\n"
        
        for name, url in CHANNELS.items():
            print(f"Захват {name}...")
            stream_url = None

            def handle_request(request):
                nonlocal stream_url
                if ".m3u8" in request.url and "token=" in request.url:
                    stream_url = request.url

            page.on("request", handle_request)
            
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                # Ждем появления токена 10 секунд
                for _ in range(10):
                    if stream_url: break
                    await asyncio.sleep(1)

                if stream_url:
                    playlist_data += f'#EXTINF:-1, {name}\n'
                    playlist_data += f'#EXTVLCOPT:http-user-agent=Mozilla/5.0\n'
                    playlist_data += f'{stream_url}\n'
                    print("  > ОК")
                else:
                    print("  > Ссылка не найдена")
            except Exception as e:
                print(f"  > Ошибка: {e}")
            finally:
                page.remove_listener("request", handle_request)

        with open("playlist.m3u", "w", encoding="utf-8") as f:
            f.write(playlist_data)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
