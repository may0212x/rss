import feedparser
import json
import os
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode

# 配置常量
CACHE_FILE = "steamdb_cache.json"

def extract_game_name(title):
    """从标题提取纯净游戏名（处理'中文/英文'格式）"""
    clean_title = title.split(" update for ")[0]
    return clean_title.split("/")[0] if "/" in clean_title else clean_title

def load_game_list():
    """加载要监控的游戏列表"""
    with open("games.json", "r") as f:
        return json.load(f)

def load_cache():
    """读取已推送记录"""
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_cache(cache):
    """保存推送记录"""
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

async def check_updates():
    """检查更新并发送通知"""
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
            
            # 如果是新BuildID
            if cache.get(str(app_id)) != build_id:
                pub_date = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z")
                new_updates.append({
                    "app_id": app_id,
                    "text": f"[GAME][{app_id}] {extract_game_name(entry.title)} ({build_id}) {pub_date.strftime('%Y/%m/%d %H:%M')}",
                    "pub_date": pub_date.timestamp(),
                    "build_id": build_id
                })
                cache[str(app_id)] = build_id  # 更新缓存

    if new_updates:
        # 按时间排序（最早的在前，最新的在后）
        new_updates.sort(key=lambda x: x["pub_date"])
        
        # 构建消息（Markdown代码块实现黑底效果）
        message = "```\n本次更新游戏列表\n" + \
                 "\n".join([u["text"] for u in new_updates]) + \
                 "\n```"
        
        await bot.send_message(
            chat_id=os.getenv("TG_CHAT_ID"),
            text=message,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        save_cache(cache)

if __name__ == "__main__":
    import asyncio
    asyncio.run(check_updates())
