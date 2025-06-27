import feedparser
import json
import os
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode

# 配置常量
CACHE_FILE = "steamdb_cache.json"
MAX_MESSAGE_LENGTH = 2000  # 预留空间给Markdown格式字符

def extract_game_name(title):
    clean_title = title.split(" update for ")[0]
    return clean_title.split("/")[0] if "/" in clean_title else clean_title

def load_game_list():
    with open("games.json", "r") as f:
        return json.load(f)

def load_cache():
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

async def send_split_messages(bot, updates):
    """分段发送超长消息"""
    header = "```\n本次更新游戏列表\n"
    footer = "\n```"
    chunk = header
    separator = "\n"
    
    for update in updates:
        new_line = update["text"] + separator
        if len(chunk) + len(new_line) + len(footer) > MAX_MESSAGE_LENGTH:
            await bot.send_message(
                chat_id=os.getenv("TG_CHAT_ID"),
                text=chunk + footer,
                parse_mode=ParseMode.MARKDOWN_V2
            )
            chunk = header + new_line
        else:
            chunk += new_line
    
    if chunk != header:  # 发送剩余内容
        await bot.send_message(
            chat_id=os.getenv("TG_CHAT_ID"),
            text=chunk + footer,
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def check_updates():
    bot = Bot(token=os.getenv("TG_BOT_TOKEN"))
    app_ids = load_game_list()
    cache = load_cache()
    new_updates = []

    for app_id in app_ids:
        rss_url = f"https://steamdb.info/api/PatchnotesRSS/?appid={app_id}"
        feed = feedparser.parse(rss_url)
        
        if feed.entries:
            entry = feed.entries[0]
            build_id = entry.guid.split("#")[-1]
            
            if cache.get(str(app_id)) != build_id:
                pub_date = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z")
                new_updates.append({
                    "app_id": app_id,
                    "text": f"[GAME][{app_id}] {extract_game_name(entry.title)} ({build_id}) {pub_date.strftime('%Y/%m/%d %H:%M')}",
                    "pub_date": pub_date.timestamp(),
                    "build_id": build_id
                })
                cache[str(app_id)] = build_id

    if new_updates:
        new_updates.sort(key=lambda x: x["pub_date"])
        await send_split_messages(bot, new_updates)
        save_cache(cache)

if __name__ == "__main__":
    import asyncio
    asyncio.run(check_updates())
