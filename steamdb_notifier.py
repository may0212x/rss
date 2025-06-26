import asyncio
import feedparser
import json
import os
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError

# 配置
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
CONFIG_FILE = "games.json"

async def send_telegram_message(bot, chat_id, message):
    try:
        await bot.send_message(chat_id=chat_id, text=message)
        print(f"消息发送成功: {message}")
    except TelegramError as e:
        print(f"发送消息失败: {e}")

async def check_updates():
    bot = Bot(token=TG_BOT_TOKEN)
    with open(CONFIG_FILE, "r") as f:
        app_ids = json.load(f)
    
    for app_id in app_ids:
        rss_url = f"https://steamdb.info/api/PatchnotesRSS/?appid={app_id}"
        feed = feedparser.parse(rss_url)
        if feed.entries:
            latest_entry = feed.entries[0]
            game_name = latest_entry.title.split(" update for ")[0]
            build_id = latest_entry.guid.split("#")[-1]
            pub_date = datetime.strptime(latest_entry.published, "%a, %d %b %Y %H:%M:%S %z").strftime("%Y/%m/%d %H:%M")
            message = f"[GAME][{app_id}] {game_name} ({build_id}) {pub_date}"
            await send_telegram_message(bot, TG_CHAT_ID, message)

if __name__ == "__main__":
    asyncio.run(check_updates())
