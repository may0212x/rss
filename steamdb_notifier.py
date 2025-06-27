#!/usr/bin/env python3
import feedparser
import json
import os
import sys
import asyncio
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

# 配置常量
CACHE_FILE = "steamdb_cache.json"
CONFIG_FILE = "games.json"
MAX_MESSAGE_LENGTH = 4000  # 预留空间给Markdown格式字符
REQUEST_TIMEOUT = 10       # 单个请求超时时间(秒)
RETRY_DELAY = 5            # 请求失败重试间隔

def extract_game_name(title):
    """智能处理游戏名称（处理'中文/英文'格式）"""
    clean_title = title.split(" update for ")[0]
    return clean_title.split("/")[0] if "/" in clean_title else clean_title

def load_game_list():
    """加载游戏列表"""
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"❌ 加载游戏列表失败: {str(e)}")
        return []

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
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"⚠️ 加载缓存失败，使用默认缓存: {str(e)}")
        return default_cache

def save_cache(cache):
    """原子化保存缓存"""
    temp_file = f"{CACHE_FILE}.tmp"
    try:
        with open(temp_file, "w") as f:
            json.dump({
                "normal": cache.get("normal", {}),
                "force": cache.get("force", {})
            }, f, indent=2)
        os.replace(temp_file, CACHE_FILE)
    except Exception as e:
        print(f"❌ 保存缓存失败: {str(e)}")
        if os.path.exists(temp_file):
            os.remove(temp_file)

async def send_message_safe(bot, text):
    """安全发送消息（带错误处理）"""
    try:
        await bot.send_message(
            chat_id=os.getenv("TG_CHAT_ID"),
            text=text,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return True
    except TelegramError as e:
        print(f"❌ 发送消息失败: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ 未知发送错误: {str(e)}")
        return False

async def send_grouped_message(bot, updates):
    """分段发送消息（自动处理长度限制）"""
    if not updates:
        print("ℹ️ 没有新更新需要发送")
        return
    
    # 按时间排序（最早的在前）
    updates.sort(key=lambda x: x["pub_date"])
    
    # 初始化消息块
    chunks = []
    current_chunk = "```\n📢 本次更新游戏列表\n────────────────────\n"
    chunk_size = len(current_chunk)
    
    for update in updates:
        line = f"{update['text']}\n"
        line_size = len(line)
        
        # 检查是否超出长度限制（预留代码块关闭标记空间）
        if chunk_size + line_size + 3 > MAX_MESSAGE_LENGTH:
            chunks.append(current_chunk + "```")
            current_chunk = "```\n📢 本次更新游戏列表（续）\n────────────────────\n"
            chunk_size = len(current_chunk)
        
        current_chunk += line
        chunk_size += line_size
    
    # 添加最后一个块
    if len(current_chunk) > len("```\n📢 本次更新游戏列表\n────────────────────\n"):
        chunks.append(current_chunk + "```")
    
    # 发送所有消息块
    for i, chunk in enumerate(chunks, 1):
        success = await send_message_safe(bot, chunk)
        if not success and i < len(chunks):
            await asyncio.sleep(RETRY_DELAY)  # 失败后延迟重试

async def check_updates(force_resend=False):
    """检查更新核心逻辑"""
    print(f"\n{'🔄 强制检查模式' if force_resend else '🔍 普通检查模式'}")
    
    try:
        bot = Bot(token=os.getenv("TG_BOT_TOKEN"))
        app_ids = load_game_list()
        if not app_ids:
            print("❌ 游戏列表为空，请检查games.json")
            return
            
        cache = load_cache()
        new_updates = []
        cache_key = "force" if force_resend else "normal"
        
        print(f"📋 共需检查 {len(app_ids)} 个游戏")
        
        for app_id in app_ids:
            try:
                rss_url = f"https://steamdb.info/api/PatchnotesRSS/?appid={app_id}"
                print(f"🔎 正在检查 AppID: {app_id}...")
                
                feed = feedparser.parse(rss_url)
                if not feed.entries:
                    print(f"   ⚠️ 无更新记录")
                    continue
                
                entry = feed.entries[0]
                build_id = entry.guid.split("#")[-1]
                cached_id = cache[cache_key].get(str(app_id))
                
                if force_resend or cached_id != build_id:
                    pub_date = datetime.strptime(
                        entry.published, 
                        "%a, %d %b %Y %H:%M:%S %z"
                    )
                    game_name = extract_game_name(entry.title)
                    new_updates.append({
                        "app_id": app_id,
                        "text": f"[GAME][{app_id}] {game_name} ({build_id}) {pub_date.strftime('%Y/%m/%d %H:%M')}",
                        "pub_date": pub_date.timestamp(),
                        "build_id": build_id
                    })
                    cache[cache_key][str(app_id)] = build_id
                    print(f"   ✅ 发现新更新 (BuildID: {build_id})")
                else:
                    print(f"   ✔️ 无新更新 (已缓存: {cached_id})")
                    
            except Exception as e:
                print(f"   ❌ 处理出错: {str(e)}")
                continue
        
        if new_updates:
            print(f"\n📨 准备发送 {len(new_updates)} 条更新...")
            await send_grouped_message(bot, new_updates)
            save_cache(cache)
            print("🎉 更新发送完成")
        else:
            print("\nℹ️ 没有发现新更新")
            
    except Exception as e:
        print(f"\n❌ 全局错误: {str(e)}")
        raise

if __name__ == "__main__":
    force_mode = "--force" in sys.argv
    print("="*50)
    print("SteamDB 游戏更新监控系统 v2.1")
    print("="*50)
    asyncio.run(check_updates(force_resend=force_mode))
