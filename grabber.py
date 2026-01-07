import asyncio
import os
from playwright.async_api import async_playwright

# !!! ВАЖНО ИСПРАВИТЬ: Укажите полные ссылки на страницы каналов !!!
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

# Шаблон ссылки сайта (может меняться со временем)
STREAM_BASE_URL = "server.smotrettv.com{channel_id}.m3u8?token={token}"

async def get_tokens_and_make_playlist():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = await context.new_page()

        # Получение данных авторизации из переменных окружения
        login = os.getenv('LOGIN', 'ВАШ_ЛОГИН')
        password = os.getenv('PASSWORD', 'ВАШ_ПАРОЛЬ')

        try:
            await page.goto("smotrettv.com") # Страница входа
            await page.fill('input[name="email"]', login)
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"]')
            await asyncio.sleep(5)
            print("Авторизация прошла успешно.")
        except Exception as e:
            print(f"Ошибка авторизации: {e}")

        playlist_data = "#EXTM3U\n"
        
        for name, url in CHANNELS.items():
            print(f"Обработка: {name}...")
            current_token = None

            def handle_request(request):
                nonlocal current_token
                if "token=" in request.url and ".m3u8" in request.url:
                     # Пытаемся извлечь только токен из URL
                    current_token = request.url.split("token=")[1].split("&")[0]

            page.on("request", handle_request)
            
            try:
                # Переходим на страницу канала для захвата токена
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(8) 

                if current_token:
                    # Извлекаем ID канала из URL страницы
                    channel_id = url.split("-")[-2].split("/")[-1]
                    stream_url = STREAM_BASE_URL.format(channel_id=channel_id, token=current_token)
                    
                    # Формат для плееров, включая заголовки для DRM/User-Agent
                    playlist_data += f'#EXTINF:-1, {name}\n'
                    playlist_data += f'#KODIPROP:inputstream.adaptive.license_type=widevine\n'
                    playlist_data += f'#EXTVLCOPT:http-user-agent=Mozilla/5.0\n'
                    playlist_data += f'{stream_url}\n'
                    print(f"  > Токен получен.")
                else:
                    print(f"  > Токен не найден для {name}.")

            except Exception as e:
                print(f"Ошибка на {name}: {e}")

        # Сохраняем результат
        with open("playlist.m3u", "w", encoding="utf-8") as f:
            f.write(playlist_data)
        
        print("\nПлейлист для DRM-play готов.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_tokens_and_make_playlist())

