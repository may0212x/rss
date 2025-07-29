import os
import json
import feedparser
import requests
from datetime import datetime
from dateutil import parser
import pytz
from pathlib import Path

# 配置常量
CONFIG_FILE = "apps_to_monitor.json"
STATE_FILE = "last_known_versions.json"
STEAM_DB_URL = "https://steamdb.info/api/PatchnotesRSS/?appid={}"
TELEGRAM_API = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage"
TELEGRAM_CHAT = os.getenv('TELEGRAM_CHAT_ID')

class SteamMonitor:
    def __init__(self):
        print("\n===== Steam游戏更新监控 =====")
        print(f"启动时间: {datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%Y/%m/%d %H:%M:%S')}")
        
        # 强制初始化状态文件
        self._init_state_file()
        
        self.hk_tz = pytz.timezone('Asia/Hong_Kong')
        self.known_versions = self.load_state()
        self.new_updates = {}
        self.first_time_updates = {}
        
        print(f"已加载 {len(self.known_versions)} 个游戏状态")

    def _init_state_file(self):
        """初始化状态文件（如果不存在）"""
        if not Path(STATE_FILE).exists():
            with open(STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump({}, f)
            print(f"已创建初始状态文件: {STATE_FILE}")

    def load_state(self):
        """加载已知版本状态"""
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ 加载状态失败: {e}")
            return {}

    def save_state(self):
        """保存状态到文件"""
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.known_versions, f, indent=2, ensure_ascii=False)
        print(f"✅ 已保存 {len(self.known_versions)} 个游戏状态")

    def get_game_update(self, appid):
        """从SteamDB获取游戏更新"""
        try:
            url = STEAM_DB_URL.format(appid)
            feed = feedparser.parse(url)
            
            if not feed.entries:
                return None

            entry = feed.entries[0]
            utc_time = parser.parse(entry.published)
            hk_time = utc_time.astimezone(self.hk_tz)
            
            return {
                'title': entry.title.split(' for ')[0].replace(' update', ''),
                'link': entry.link,
                'published': entry.published,
                'timestamp': hk_time,
                'build_id': entry.link.split('/')[-2]
            }
        except Exception as e:
            print(f"❌ 获取游戏 {appid} 更新失败: {e}")
            return None

    def check_updates(self):
        """检查所有游戏更新"""
        app_ids = self.load_config()
        print(f"\n正在检查 {len(app_ids)} 个游戏...")
        
        for appid in app_ids:
            update = self.get_game_update(appid)
            if not update:
                continue

            appid_str = str(appid)
            if appid_str not in self.known_versions:
                print(f"[新增] {update['title']} (ID: {appid})")
                self.first_time_updates[appid] = update
                self.known_versions[appid_str] = self._sanitize_update(update)
            elif update['build_id'] != self.known_versions[appid_str]['build_id']:
                print(f"[更新] {update['title']} (新版本: {update['build_id']})")
                self.new_updates[appid] = update
                self.known_versions[appid_str] = self._sanitize_update(update)
            else:
                print(f"[无更新] {update['title']}")

    def _sanitize_update(self, update):
        """准备可序列化的更新数据"""
        return {
            'title': update['title'],
            'link': update['link'],
            'published': update['published'],
            'build_id': update['build_id'],
            'last_checked': datetime.now(self.hk_tz).isoformat()
        }

    def load_config(self):
        """加载监控配置"""
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f).get('apps', [])

    def send_notification(self):
        """发送Telegram通知（完全保留原格式）"""
        if self.first_time_updates:
            self._send_telegram(
                self._format_updates(self.first_time_updates, "🎮 新增监控游戏列表")
            )
        if self.new_updates:
            self._send_telegram(
                self._format_updates(self.new_updates, "🆕 本次更新游戏列表")
            )

    def _format_updates(self, updates, title):
        """严格保留原有消息格式"""
        sorted_updates = sorted(updates.items(), key=lambda x: x[1]['timestamp'])
        message = ["```"]
        message.append(title)
        
        for appid, update in sorted_updates:
            hk_time_str = update['timestamp'].strftime('%Y/%m/%d %H:%M')
            message.append(
                f"[GAME][{appid}] {update['title']} ({update['build_id']}) {hk_time_str}"
            )
        
        message.append("```")
        return '\n'.join(message)

    def _send_telegram(self, message):
        """发送到Telegram"""
        try:
            requests.post(
                TELEGRAM_API,
                data={
                    'chat_id': TELEGRAM_CHAT,
                    'text': message,
                    'parse_mode': 'MarkdownV2'
                },
                timeout=10
            )
            print("✅ 已发送Telegram通知")
        except Exception as e:
            print(f"❌ Telegram发送失败: {e}")

    def run(self):
        """主运行流程"""
        self.check_updates()
        if self.first_time_updates or self.new_updates:
            self.send_notification()
        self.save_state()
        print("\n监控任务完成")

if __name__ == "__main__":
    monitor = SteamMonitor()
    monitor.run()
