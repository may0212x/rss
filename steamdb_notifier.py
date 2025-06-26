import feedparser
import json
import os
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode

# 配置
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
CONFIG_FILE = "games.json"

def extract_game_name(title):
    """智能提取游戏名称（自动处理中英文/特殊格式）"""
    clean_title = title.split(" update for ")[0]
    # 处理 "中文名/英文名" 格式
    return clean_title.split("/")[0] if "/" in clean_title else clean_title

async def send_steam_updates():
    """获取所有更新并合并发送（完全匹配范例格式）"""
    with open(CONFIG_FILE, "r") as f:
        app_ids = json.load(f)
    
    bot = Bot(token=TG_BOT_TOKEN)
    updates = []
    
    # 收集所有更新
    for app_id in app_ids:
        rss_url = f"https://steamdb.info/api/PatchnotesRSS/?appid={app_id}"
        feed = feedparser.parse(rss_url)
        if feed.entries:
            entry = feed.entries[0]
            game_name = extract_game_name(entry.title)
            build_id = entry.guid.split("#")[-1]
            pub_date = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z").strftime("%Y/%m/%d %H:%M")
            updates.append(f"[GAME][{app_id}] {game_name} ({build_id}) {pub_date}")
    
    if updates:
        # 构建完全匹配范例格式的消息（使用代码块实现黑底效果）
        message = "```\n本次更新游戏列表\n"
        message += "\n".join(updates)
        message += "\n```"
        
        # 发送消息（启用Markdown解析）
        await bot.send_message(
            chat_id=TG_CHAT_ID,
            text=message,
            parse_mode=ParseMode.MARKDOWN_V2
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(send_steam_updates())
