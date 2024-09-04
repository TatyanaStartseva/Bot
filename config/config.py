import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
IP = os.getenv("IP")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
