import asyncio
import os
import re
from playwright.async_api import async_playwright

# Исправленные ссылки и логика извлечения ID
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

STREAM_BASE_URL = "https://server.smotrettv.com/{channel_id}.m3u8?token={token}"

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = await context.new_page()

        # Авторизация
        print("Авторизация...")
        await page.goto("https://smotrettv.com/login")
        await page.fill('input[name="email"]', os.getenv('LOGIN', 'your_email'))
        await page.fill('input[name="password"]', os.getenv('PASSWORD', 'your_password'))
        await page.click('button[type="submit"]')
        await page.wait_for_load_state("networkidle")

        playlist = "#EXTM3U\n"
        
        for name, url in CHANNELS.items():
            print(f"Получение токена для: {name}")
            current_token = [None] # Используем список для изменяемости внутри функции

            async def intercept_request(request):
                if "token=" in request.url:
                    match = re.search(r'token=([^&]+)', request.url)
                    if match:
                        current_token[0] = match.group(1)

            page.on("request", intercept_request)
            
            try:
                # Извлекаем ID (число в начале названия файла)
                # Например из 1003-pervyj-kanal.html получим 1003
                channel_file = url.split("/")[-1].replace(".html", "")
                channel_id = channel_file.split("-")[0]

                await page.goto(url, wait_until="domcontentloaded")
                
                # Ждем токен максимум 15 секунд
                for _ in range(15):
                    if current_token[0]:
                        break
                    await asyncio.sleep(1)
                
                if current_token[0]:
                    stream = STREAM_BASE_URL.format(channel_id=channel_id, token=current_token[0])
                    playlist += f'#EXTINF:-1, {name}\n#EXTVLCOPT:http-user-agent=Mozilla/5.0\n{stream}\n'
                    print(f"Успешно: {name}")
                else:
                    print(f"Ошибка: Токен для {name} не найден")
            
            except Exception as e:
                print(f"Ошибка при обработке {name}: {e}")
            finally:
                page.remove_listener("request", intercept_request)

        with open("playlist_8f2d9k1l.m3u", "w", encoding="utf-8") as f:
            f.write(playlist)
        
        print("Готово. Плейлист сохранен.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
