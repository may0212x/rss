import asyncio
import feedparser
import json
import os
from datetime import datetime
from telegram import Bot

# 配置（从环境变量读取）
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
CONFIG_FILE = "games.json"

async def send_telegram_notification(message):
    """异步发送消息到 Telegram"""
    bot = Bot(token=TG_BOT_TOKEN)
    await bot.send_message(chat_id=TG_CHAT_ID, text=message)

async def check_updates():
    with open(CONFIG_FILE, "r") as f:
        app_ids = json.load(f)
    
    for app_id in app_ids:
        rss_url = f"https://steamdb.info/api/PatchnotesRSS/?appid={app_id}"
        feed = feedparser.parse(rss_url)
        if feed.entries:
            latest_entry = feed.entries[0]
            message = f"[GAME][{app_id}] {latest_entry.title.split(' update for ')[0]} ({latest_entry.guid.split('#')[-1]}) {datetime.strptime(latest_entry.published, '%a, %d %b %Y %H:%M:%S %z').strftime('%Y/%m/%d %H:%M')}"
            await send_telegram_notification(message)

if __name__ == "__main__":
    asyncio.run(check_updates())
