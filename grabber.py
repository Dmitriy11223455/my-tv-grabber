import asyncio
import os
from playwright.async_api import async_playwright

# Список каналов. Вставьте ID каналов из URL (например, /channel/123)
CHANNELS = {
    "Первый канал": "https://smotrettv.com/tv/public/1003-pervyj-kanal.html",
    "Россия 1": "https://smotrettv.com/tv/public/784-rossija-1.html",
    "Звезда": "https://smotrettv.com/tv/public/310-zvezda.html",
    "ТНТ": "https://smotrettv.com/tv/entertainment/329-tnt.html",
    "Россия 24": "https://smotrettv.com/tv/news/217-rossija-24.html",
    "СТС": "https://smotrettv.com/tv/entertainment/783-sts.html",
    "НТВ":"https://smotrettv.com/tv/public/6-ntv.html",
    "Рен ТВ":"https://smotrettv.com/tv/public/316-ren-tv.html"
}

STREAM_BASE_URL = "https://server.smotrettv.com/{channel_id}.m3u8?token={token}"

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0")
        page = await context.new_page()

        # Авторизация
        await page.goto("https://smotrettv.com/login")
        await page.fill('input[name="email"]', os.getenv('LOGIN'))
        await page.fill('input[name="password"]', os.getenv('PASSWORD'))
        await page.click('button[type="submit"]')
        await asyncio.sleep(5)

        playlist = "#EXTM3U\n"
        
        for name, url in CHANNELS.items():
            print(f"Получение токена для: {name}")
            token = None

            def intercept_token(request):
                nonlocal token
                if "token=" in request.url:
                    token = request.url.split("token=")[1].split("&")[0]

            page.on("request", intercept_token)
            try:
                await page.goto(url, wait_until="networkidle")
                await asyncio.sleep(10) # Ждем прогрузки видео
                if token:
                    channel_id = url.split("/")[-1]
                    stream = STREAM_BASE_URL.format(channel_id=channel_id, token=token)
                    playlist += f'#EXTINF:-1, {name}\n#EXTVLCOPT:http-user-agent=Mozilla/5.0\n{stream}\n'
            except:
                continue

        # Сохранение (название файла с секретным хвостом)
        with open("playlist_8f2d9k1l.m3u", "w", encoding="utf-8") as f:
            f.write(playlist)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
