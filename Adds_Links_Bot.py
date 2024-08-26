import os
import re
import aiohttp
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from dotenv import load_dotenv
from openpyxl import Workbook
import psycopg2

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
    try:
        async with aiohttp.ClientSession():
            urls = re.findall(r'(?:https?://\S+)', message.text)
            wb = Workbook()
            ws = wb.active
            ws.append(
                [
                    "user_id",
                    "username",
                    "bio",
                    "first_name",
                    "last_name",
                    "last_online",
                    "premium",
                    "phone",
                    "image",
                ]
            )
            user_ids_written = set()
            chat_processing = ""
            if urls:
                file_path = "chats_users.xlsx"
                invalid_chat_ids_server = []
                invalid_chat_ids = []
                for url in urls:
                    remainder = url.split("://")[1].split("/", 1)[-1]
                    if re.match(r'^https?://', url) and not '/' in remainder:
                            try:
                                url = url.lower()
                                conn = psycopg2.connect(
                                    host=HOST, database=DATABASE, user=USER, password=PASSWORD
                                )
                                cursor = conn.cursor()
                                chat_ids = []
                                cursor.execute(
                                        "SELECT chat_id FROM chats WHERE parent_link = %s OR children_link = %s",
                                        (url, url),
                                    )
                                chat = cursor.fetchone()
                                if chat:
                                    chat_ids.append(chat[0])

                                chat_users = []
                                if chat_ids:
                                    for chat_id in chat_ids:
                                        cursor.execute("SELECT  user_chat.user_id  FROM user_chat JOIN users ON user_chat.user_id=users.user_id WHERE chat_id = %s  AND bio = 'Default-value-for-parser' GROUP BY user_chat.user_id", (chat_id,))
                                        result = cursor.fetchall()
                                        if len(result) == 0:
                                            cursor.execute("SELECT user_id FROM user_chat WHERE chat_id = %s", (chat_id,))
                                            users = cursor.fetchall()
                                            for user in users:
                                                cursor.execute("SELECT * FROM users WHERE user_id = %s", (user,))
                                                user_data = cursor.fetchall()
                                                user_id = user_data[0][0]
                                                if user_id not in user_ids_written :
                                                    chat_users.append(
                                                        (
                                                            user_data[0][0],
                                                            user_data[0][1],
                                                            user_data[0][2],
                                                            user_data[0][3],
                                                            user_data[0][4],
                                                            user_data[0][5],
                                                            user_data[0][6],
                                                            user_data[0][7],
                                                            user_data[0][8],
                                                        )
                                                    )
                                                    user_ids_written.add(user_id)
                                        else:
                                            chat_processing+= url+', '
                                for user in chat_users:
                                    user_data = [
                                        user[0],
                                        user[1],
                                        user[2],
                                        user[3],
                                        user[4],
                                        user[5].strftime("%Y-%m-%d %H:%M:%S") if user[5] is not None else "",
                                        "false" if user[6] == False else "true",
                                        "" if user[7] is None else user[7],
                                        "true" if user[8] == True else "false",
                                    ]
                                    ws.append(user_data)

                                wb.save(file_path)
                            except Exception as e:
                                await message.reply(f"Произошла ошибка при обработке запроса: {e}")
                    else:
                        invalid_chat_ids.append(url)

                if invalid_chat_ids:
                    await message.reply(f'Ссылки должны начинаться с "https://" и не содержать "/" в конце. Например, ссылка "https://t.me/example1/4544" неправильна, так как содержит "/4544" в конце.\n' +'\n'.join(invalid_chat_ids_server))
                else:
                    await message.reply(f"Чат(ы) {chat_processing} сейчас обрабатывается, попробуйте повторить запрос позже \n")
                    wb.save(file_path)
                    with open(file_path, "rb") as f:
                        document = types.InputFile(f)
                        await message.reply_document(document)
                    os.remove(file_path)
            else:
                await message.reply(f'Ссылки должны начинаться с "https://" и не содержать "/" в конце. Например, ссылка "https://t.me/example1/4544" неправильна, так как содержит "/4544" в конце.')
            await state.finish()
    except Exception as e:
        print(f"Ошибка: {e}")
        await message.reply(f"Ошибка: {e}")



@dp.message_handler(state=ParseState.waiting_for_tasks_links)
async def tasks_links(message: types.Message, state: FSMContext):
    try:
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
                    answer = requests.post(f"http://{IP}/add", json={"urls": valid_links})
                    if answer.status_code == 200:
                        await message.reply('Чаты успешно добавлены в очередь для парсинга.Рекомендуется подождать час, перед тем как получить информацию о пользователях из чатов.')
                    else:
                        await message.reply(f"Ошибка: {answer.status_code}")
        else:
            await message.reply(f'Ссылки должны начинаться с "https://" и не содержать "/" в конце. Например, ссылка "https://t.me/example1/4544" неправильна, так как содержит "/4544" в конце.')
        await state.finish()
    except Exception as e:
        print(f"{e}")
        await message.reply(f"Ошибка: {e}")

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