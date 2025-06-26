import feedparser
import json
import os
from datetime import datetime
from telegram import Bot

# 配置
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")  # 从 GitHub Secrets 读取
TG_CHAT_ID = os.getenv("TG_CHAT_ID")  # 从 GitHub Secrets 读取
CONFIG_FILE = "games.json"


def extract_game_name(title):
    """从 RSS 标题提取游戏名（如 'xxx update for date' → 'xxx'）"""
    return title.split(" update for ")[0]

def check_updates():
    with open(CONFIG_FILE, "r") as f:
        app_ids = json.load(f)
    
    bot = Bot(token=TG_BOT_TOKEN)
    for app_id in app_ids:
        rss_url = f"https://steamdb.info/api/PatchnotesRSS/?appid={app_id}"
        feed = feedparser.parse(rss_url)
        print(f"检查 AppID: {app_id}, RSS 条目数: {len(feed.entries)}")  # 调试日志
        if feed.entries:
            latest_entry = feed.entries[0]
            print(f"最新条目: {latest_entry.title}")  # 调试日志
            message = format_message(latest_entry, app_id)
            bot.send_message(chat_id=TG_CHAT_ID, text=message)

def format_message(entry, app_id):
    """格式化消息为 [GAME][AppID] 游戏名 (BuildID) 更新时间"""
    game_name = extract_game_name(entry.title)
    build_id = entry.guid.split("#")[-1]
    pub_date = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z").strftime("%Y/%m/%d %H:%M")
    return f"[GAME][{app_id}] {game_name} ({build_id}) {pub_date}"


def check_updates():
    with open(CONFIG_FILE, "r") as f:
        app_ids = json.load(f)

    bot = Bot(token=TG_BOT_TOKEN)
    for app_id in app_ids:
        rss_url = f"https://steamdb.info/api/PatchnotesRSS/?appid={app_id}"
        feed = feedparser.parse(rss_url)
        if feed.entries:
            latest_entry = feed.entries[0]
            message = format_message(latest_entry, app_id)
            bot.send_message(chat_id=TG_CHAT_ID, text=message)


if __name__ == "__main__":
    check_updates()
