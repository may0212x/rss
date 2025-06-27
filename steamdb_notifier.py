import feedparser
import json
import os
import sys
import asyncio
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode

# 配置常量
CACHE_FILE = "steamdb_cache.json"
CONFIG_FILE = "games.json"
MAX_MESSAGE_LENGTH = 4000

def extract_game_name(title):
    """智能处理游戏名称"""
    clean_title = title.split(" update for ")[0]
    return clean_title.split("/")[0] if "/" in clean_title else clean_title

def load_game_list():
    """加载游戏列表"""
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def load_cache():
    """加载推送记录（确保结构完整）"""
    default_cache = {"normal": {}, "force": {}}
    try:
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)
            # 合并现有缓存与默认结构
            return {
                "normal": {**default_cache["normal"], **cache.get("normal", {})},
                "force": {**default_cache["force"], **cache.get("force", {})}
            }
    except (FileNotFoundError, json.JSONDecodeError):
        return default_cache

def save_cache(cache):
    """原子化保存缓存"""
    temp_file = f"{CACHE_FILE}.tmp"
    with open(temp_file, "w") as f:
        json.dump({
            "normal": cache.get("normal", {}),
            "force": cache.get("force", {})
        }, f, indent=2)
    os.replace(temp_file, CACHE_FILE)

async def send_grouped_message(bot, updates):
    """发送合并消息"""
    if not updates:
        return
    
    # 按时间排序（最早的在前）
    updates.sort(key=lambda x: x["pub_date"])
    
    message = "```\n本次更新游戏列表\n"
    for update in updates:
        message += f"{update['text']}\n"
    message += "```"
    
    await bot.send_message(
        chat_id=os.getenv("TG_CHAT_ID"),
        text=message,
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def check_updates(force_resend=False):
    """检查更新核心逻辑"""
    bot = Bot(token=os.getenv("TG_BOT_TOKEN"))
    app_ids = load_game_list()
    cache = load_cache()
    new_updates = []
    cache_key = "force" if force_resend else "normal"

    for app_id in app_ids:
        try:
            rss_url = f"https://steamdb.info/api/PatchnotesRSS/?appid={app_id}"
            feed = feedparser.parse(rss_url)
            
            if feed.entries:
                entry = feed.entries[0]
                build_id = entry.guid.split("#")[-1]
                
                # 强制模式或检测到新版本
                if force_resend or cache[cache_key].get(str(app_id)) != build_id:
                    pub_date = datetime.strptime(
                        entry.published, 
                        "%a, %d %b %Y %H:%M:%S %z"
                    )
                    new_updates.append({
                        "app_id": app_id,
                        "text": f"[GAME][{app_id}] {extract_game_name(entry.title)} ({build_id}) {pub_date.strftime('%Y/%m/%d %H:%M')}",
                        "pub_date": pub_date.timestamp(),
                        "build_id": build_id
                    })
                    cache[cache_key][str(app_id)] = build_id
                    
        except Exception as e:
            print(f"处理AppID {app_id}时出错: {str(e)}")
            continue

    if new_updates:
        await send_grouped_message(bot, new_updates)
        save_cache(cache)

if __name__ == "__main__":
    force_mode = "--force" in sys.argv
    asyncio.run(check_updates(force_resend=force_mode))
