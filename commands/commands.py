import os
import re
import aiohttp
import requests
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from openpyxl import Workbook
from db.db import db
from config.config import dp, IP


class DownloadState(StatesGroup):
    waiting_for_download_links = State()


class ParseState(StatesGroup):
    waiting_for_tasks_links = State()


@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.reply(
        'Привет! Мы рады представить Вам нашего бота и ознакомить с его функционалом.\n\nКоманда "/parse"\nОтправьте список ссылок, которые Вы хотите добавить в базу данных. Бот проверит их на корректность и добавит допустимые ссылки.\n\nКоманда "/download"\nОтправьте список ссылок на чаты, после чего бот отправит информацию о пользователях этих чатов в формате Excel.\n\nВы можете отправлять как одну ссылку, так и несколько ссылок одновременно. Просто разделите их переносом строки.'
    )


@dp.message_handler(commands=["parse"])
async def tasks_command(message: types.Message):
    await ParseState.waiting_for_tasks_links.set()
    await message.reply(
        "Пожалуйста, отправьте ссылки, которые нужно добавить в базу данных.\nПример:\nhttps://t.me/example1 \nhttps://t.me/example2"
    )


@dp.message_handler(commands=["download"])
async def download_command(message: types.Message):
    await message.reply(
        "Пожалуйста, отправьте ссылки на чаты, чтобы скачать информацию о пользователях этих чатов.\nПример:\nhttps://t.me/example1 \nhttps://t.me/example2"
    )
    await DownloadState.waiting_for_download_links.set()


@dp.message_handler(state=DownloadState.waiting_for_download_links)
async def download_links(message: types.Message, state: FSMContext):
    try:
        async with aiohttp.ClientSession():
            urls = re.findall(r"(?:https?://\S+)", message.text)
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
                    "ban",
                ]
            )
            if urls:
                file_path = "chats_users.xlsx"
                invalid_chat_ids_server = []
                invalid_chat_ids = []
                valid_urls = []
                for url in urls:
                    remainder = url.split("://")[1].split("/", 1)[-1]
                    if re.match(r"^https?://", url) and not "/" in remainder:
                        valid_urls.append(url.lower())
                    else:
                        invalid_chat_ids.append(url)
                data_base = db()
                cursor_chat = data_base["chats"]
                cursor_links = data_base["links"]
                cursor_users = data_base["users"]

                chats_ids = cursor_chat.distinct(
                    "chat_id",
                    {
                        "$or": [
                            {"parent_link": {"$in": valid_urls}},
                            {"children_link": {"$in": valid_urls}},
                        ]
                    },
                )
                users_ids = cursor_links.distinct(
                    "user_id", {"chat_id": {"$in": chats_ids}}
                )
                info_users = list(
                    cursor_users.find(
                        {"user_id": {"$in": users_ids}, "ban": {"$ne": True}},
                        {"_id": 0},
                    )
                )
                is_not_finished = False

                for user in info_users:
                    if "ban" not in user:
                        user["ban"] = False
                    if user["bio"] == "Default-value-for-parser":
                        bio = None
                        is_not_finished = True
                    else:
                        bio = user["bio"]
                    user_data = [
                        user["user_id"],
                        user["username"],
                        bio,
                        str(user["first_name"]),
                        str(user["last_name"]),
                        (
                            user["last_online"].strftime("%Y-%m-%d %H:%M:%S")
                            if user["last_online"] is not None
                            else ""
                        ),
                        "false" if user["premium"] == False else "true",
                        "" if user["phone"] is None else user["phone"],
                        "true" if user["image"] == True else "false",
                        "true" if user["ban"] == True else "false",
                    ]
                    ws.append(user_data)
                wb.save(file_path)
                if is_not_finished:
                    await message.reply(
                        f"На данный момент не вся информации о пользователях доступна. Пожалуйста, подождите некоторое время и повторите попытку. \n "
                    )
                if invalid_chat_ids:
                    await message.reply(
                        f'Ссылки должны начинаться с "https://" и не содержать "/" в конце. Например, ссылка "https://t.me/example1/4544" неправильна, так как содержит "/4544" в конце.\n'
                        + "\n".join(invalid_chat_ids_server)
                    )
                else:
                    with open(file_path, "rb") as f:
                        document = types.InputFile(f)
                        await message.reply_document(document)
                    os.remove(file_path)
            else:
                await message.reply(
                    f'Ссылки должны начинаться с "https://" и не содержать "/" в конце. Например, ссылка "https://t.me/example1/4544" неправильна, так как содержит "/4544" в конце.'
                )
        await state.finish()
    except Exception as e:
        await message.reply(f"Произошла ошибка при обработке запроса: {e}")


@dp.message_handler(state=ParseState.waiting_for_tasks_links)
async def tasks_links(message: types.Message, state: FSMContext):
    try:
        links = re.findall(r"(?:https?://\S+)", message.text)
        if links:
            valid_links = []
            invalid_links = []

            for link in links:
                remainder = link.split("://")[1].split("/", 1)[-1]
                if re.match(r"^https?://", link) and not "/" in remainder:
                    valid_links.append(link)
                else:
                    invalid_links.append(link)

            if invalid_links:
                await message.reply(
                    'Ссылки должны начинаться с "https://" и не содержать "/" в конце. Например, ссылка "https://t.me/example1/4544" неправильна, так как содержит "/4544" в конце.\n'
                    + "\n".join(invalid_links)
                )
            else:
                if valid_links:
                    answer = requests.post(
                        f"http://{IP}/add", json={"urls": valid_links}
                    )
                    if answer.status_code == 200:
                        await message.reply(
                            "Чаты успешно добавлены в очередь для парсинга.Рекомендуется подождать час, перед тем как получить информацию о пользователях из чатов."
                        )
                    else:
                        await message.reply(f"Ошибка: {answer.status_code}")
        else:
            await message.reply(
                f'Ссылки должны начинаться с "https://" и не содержать "/" в конце. Например, ссылка "https://t.me/example1/4544" неправильна, так как содержит "/4544" в конце.'
            )
        await state.finish()
    except Exception as e:
        print(f"{e}")
        await message.reply(f"Ошибка: {e}")
