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

STREAM_BASE_URL = "https://server.smotrettv.com/{channel_id}.m3u8?token={token}"

async def run():
    async with async_playwright() as p:
        # Запуск с игнорированием ошибок HTTPS
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 720}
        )
        page = await context.new_page()
        
        # Устанавливаем таймаут по умолчанию 60 секунд
        page.set_default_timeout(60000)

        # Авторизация
        print("Авторизация...")
        try:
            await page.goto("https://smotrettv.com/login", wait_until="domcontentloaded")
            await page.fill('input[name="email"]', os.getenv('LOGIN', 'your_login'))
            await page.fill('input[name="password"]', os.getenv('PASSWORD', 'your_password'))
            await asyncio.gather(
                page.wait_for_navigation(wait_until="networkidle"),
                page.click('button[type="submit"]')
            )
        except Exception as e:
            print(f"Предупреждение при логине: {e}")

        playlist = "#EXTM3U\n"
        
        for name, url in CHANNELS.items():
            print(f"Запрос для: {name}")
            token_container = {"value": None}

            async def intercept_request(request):
                if "token=" in request.url:
                    match = re.search(r'token=([^&]+)', request.url)
                    if match:
                        token_container["value"] = match.group(1)

            page.on("request", intercept_request)
            
            try:
                channel_id = url.split("/")[-1].split("-")[0]
                
                # Переходим на страницу канала, игнорируя таймаут загрузки тяжелых элементов
                try:
                    await page.goto(url, wait_until="commit", timeout=60000)
                except Exception:
                    pass # Нам важен только поток данных, а не полная отрисовка
                
                # Ждем появления токена в трафике
                for _ in range(20):
                    if token_container["value"]:
                        break
                    await asyncio.sleep(1)
                
                if token_container["value"]:
                    stream = STREAM_BASE_URL.format(channel_id=channel_id, token=token_container["value"])
                    playlist += f'#EXTINF:-1, {name}\n#EXTVLCOPT:http-user-agent=Mozilla/5.0\n{stream}\n'
                    print(f"Успешно получен: {name}")
                else:
                    print(f"Токен для {name} не перехвачен")
            
            except Exception as e:
                print(f"Ошибка на канале {name}: {e}")
            finally:
                page.remove_listener("request", intercept_request)

        with open("playlist_8f2d9k1l.m3u", "w", encoding="utf-8") as f:
            f.write(playlist)
        
        print("\nРабота завершена. Файл создан.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
