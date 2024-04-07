import os
import re
import aiohttp
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
IP = os.getenv("IP")
IP_USERS_SAVE=os.getenv("IP_USERS_SAVE")
HOST = os.getenv("HOST")
DATABASE = os.getenv("DATABASE")
USER = os.getenv("USERNAME_DB")
PASSWORD = os.getenv("PASSWORD_DB")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
class DownloadState(StatesGroup):
    waiting_for_download_links = State()

class ParseState(StatesGroup):
    waiting_for_tasks_links = State()

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply('Привет! Мы рады представить Вам нашего бота и ознакомить с его функционалом.\n\nКоманда "/parse"\nОтправьте список ссылок, которые Вы хотите добавить в базу данных. Бот проверит их на корректность и добавит допустимые ссылки.\n\nКоманда "/download"\nОтправьте список ссылок на чаты, после чего бот отправит информацию о пользователях этих чатов в формате Excel.\n\nВы можете отправлять как одну ссылку, так и несколько ссылок одновременно. Просто разделите их переносом строки.')

@dp.message_handler(commands=['parse'])
async def tasks_command(message: types.Message):
    await ParseState.waiting_for_tasks_links.set()
    await message.reply('Пожалуйста, отправьте ссылки, которые нужно добавить в базу данных.\nПример:\nhttps://t.me/example1 \nhttps://t.me/example2')

@dp.message_handler(commands=['download'])
async def download_command(message: types.Message):
    await message.reply('Пожалуйста, отправьте ссылки на чаты, чтобы скачать информацию о пользователях этих чатов.\nПример:\nhttps://t.me/example1 \nhttps://t.me/example2')
    await DownloadState.waiting_for_download_links.set()

@dp.message_handler(state=DownloadState.waiting_for_download_links)
async def download_links(message: types.Message, state: FSMContext):
    async with aiohttp.ClientSession() as session:
        urls = re.findall(r'(?:https?://\S+)', message.text)
        if urls:
            file_path = "chats_users.xlsx"
            invalid_chat_ids_server = []
            invalid_chat_ids = []
            for url in urls:
                remainder = url.split("://")[1].split("/", 1)[-1]
                if re.match(r'^https?://', url) and not '/' in remainder:
                    async with session.get(f"http://{IP_USERS_SAVE}/chats_links?urls={url}") as resp:
                        try:
                            if resp.status == 200:
                                file_content = await resp.read()
                                with open(file_path, "ab") as f:
                                    f.write(file_content)
                            else:
                                error_message = await resp.text()
                                invalid_chat_ids_server.append(url)
                        except Exception as e:
                            await message.reply(f"Произошла ошибка при обработке запроса: {e}")
                else:
                    invalid_chat_ids.append(url)
            if invalid_chat_ids_server:
                await message.reply(f"{error_message}\n" + '\n'.join(invalid_chat_ids_server))
            if invalid_chat_ids:
                await message.reply(f'Ссылки должны начинаться с "https://" и не содержать "/" в конце. Например, ссылка "https://t.me/example1/4544" неправильна, так как содержит "/4544" в конце.\n' +'\n'.join(invalid_chat_ids_server))
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    await message.reply_document(f)
                    os.remove(file_path)
        else:
            await message.reply(f'Ссылки должны начинаться с "https://" и не содержать "/" в конце. Например, ссылка "https://t.me/example1/4544" неправильна, так как содержит "/4544" в конце.')
        await state.finish()



@dp.message_handler(state=ParseState.waiting_for_tasks_links)
async def tasks_links(message: types.Message, state: FSMContext):
    links = re.findall(r'(?:https?://\S+)', message.text)
    if links:
        valid_links = []
        invalid_links = []

        for link in links:
            remainder = link.split("://")[1].split("/", 1)[-1]
            if re.match(r'^https?://', link) and not '/' in remainder:
                valid_links.append(link)
            else:
                invalid_links.append(link)

        if invalid_links:
            await message.reply('Ссылки должны начинаться с "https://" и не содержать "/" в конце. Например, ссылка "https://t.me/example1/4544" неправильна, так как содержит "/4544" в конце.\n' + '\n'.join(invalid_links))
        else:
            if valid_links:
                requests.get(f"http://{IP}/add")
                requests.post(f"http://{IP}/add", json={"urls": valid_links})
                await message.reply('Чаты успешно добавлены в очередь для парсинга.Рекомендуется подождать час, перед тем как получить информацию о пользователях из чатов.')
    else:
        await message.reply(f'Ссылки должны начинаться с "https://" и не содержать "/" в конце. Например, ссылка "https://t.me/example1/4544" неправильна, так как содержит "/4544" в конце.')
    await state.finish()

async def on_shutdown():
    await bot.close()

async def main():
    await dp.start_polling()
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
            if hasattr(dp.bot, 'session') and dp.bot.session:
                await dp.bot.session.close()
            if hasattr(dp.bot, 'connector') and dp.bot.connector:
                await dp.bot.connector.close()
            await dp.stop_polling()
            await dp.wait_closed()
    finally:
        await bot.session.close()
        await bot.connector.close()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())