import os
import json
import feedparser
from datetime import datetime
import requests
from pathlib import Path
from dateutil import parser

# 配置文件路径
CONFIG_FILE = "apps_to_monitor.json"
LAST_VERSIONS_FILE = "last_known_versions.json"
STEAM_DB_RSS_URL = "https://steamdb.info/api/PatchnotesRSS/?appid={}"

# Telegram 配置
TELEGRAM_API_URL = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage"
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def load_json_file(filename):
    """加载 JSON 文件"""
    try:
        if Path(filename).exists():
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except json.JSONDecodeError:
        return {}

def save_json_file(filename, data):
    """保存数据到 JSON 文件"""
    # 转换 datetime 对象为字符串
    serializable_data = {}
    for appid, update in data.items():
        serializable_data[appid] = {
            'title': update['title'],
            'link': update['link'],
            'published': update['published'],
            'build_id': update['build_id']
        }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(serializable_data, f, indent=2, ensure_ascii=False)

def get_game_updates(appid):
    """从 SteamDB 获取游戏更新信息"""
    url = STEAM_DB_RSS_URL.format(appid)
    feed = feedparser.parse(url)
    
    if not feed.entries:
        return None
    
    latest_update = feed.entries[0]
    return {
        'title': latest_update.title,
        'link': latest_update.link,
        'published': latest_update.published,
        'published_parsed': parser.parse(latest_update.published),
        'build_id': latest_update.link.split('/')[-2]
    }

def format_message(updates, is_first_time=False):
    """格式化消息内容，严格按时间排序（旧→新）且无空行"""
    # 按发布时间从旧到新排序
    sorted_updates = sorted(
        updates.items(),
        key=lambda x: x[1]['published_parsed']
    )
    
    # 构建消息内容（紧凑格式）
    message = "```\n"  # 开始黑底代码块
    message += "新增监控游戏列表\n" if is_first_time else "本次更新游戏列表\n"
    
    for appid, update in sorted_updates:
        # 格式化日期时间
        formatted_date = update['published_parsed'].strftime('%Y/%m/%d %H:%M')
        
        # 提取纯净游戏名（移除'for XXX'后缀）
        game_name = update['title'].split(' for ')[0]
        
        # 紧凑格式：无空行
        message += f"[GAME][{appid}] {game_name} ({update['build_id']}) {formatted_date}\n"
    
    message += "```"  # 结束黑底代码块
    return message

def send_telegram_message(message):
    """发送 Telegram 通知"""
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'MarkdownV2'
    }
    requests.post(TELEGRAM_API_URL, data=payload)

def main():
    # 初始化状态文件
    if not Path(LAST_VERSIONS_FILE).exists():
        with open(LAST_VERSIONS_FILE, 'w') as f:
            json.dump({}, f)
    # 加载配置
    config = load_json_file(CONFIG_FILE)
    app_ids = config.get('apps', [])
    last_versions = load_json_file(LAST_VERSIONS_FILE)
    
    new_updates = {}
    first_time_updates = {}
    has_changes = False
    
    for appid in app_ids:
        update = get_game_updates(appid)
        if not update:
            continue
            
        appid_str = str(appid)
        
        # 首次监控的游戏
        if appid_str not in last_versions:
            last_versions[appid_str] = update
            first_time_updates[appid] = update
            has_changes = True
            continue
            
        # 检查新版本
        if update['build_id'] != last_versions[appid_str]['build_id']:
            new_updates[appid] = update
            last_versions[appid_str] = update
            has_changes = True
    
    # 发送通知
    if first_time_updates:
        send_telegram_message(format_message(first_time_updates, is_first_time=True))
    if new_updates:
        send_telegram_message(format_message(new_updates))
    
    # 保存状态
    if has_changes:
        save_json_file(LAST_VERSIONS_FILE, last_versions)

if __name__ == "__main__":
    main()
