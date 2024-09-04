import aiohttp
import requests
import asyncio
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from db.db import db
from commands.commands import start, tasks_command, tasks_links,download_command,download_links
from config.config import dp


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
    asyncio.run(main())
