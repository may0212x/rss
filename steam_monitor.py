import os
import json
import feedparser
import requests
from datetime import datetime
from dateutil import parser
from pathlib import Path

# 配置常量
CONFIG_FILE = "apps_to_monitor.json"
STATE_FILE = "last_known_versions.json"
STEAM_DB_URL = "https://steamdb.info/api/PatchnotesRSS/?appid={}"
TELEGRAM_API = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage"
TELEGRAM_CHAT = os.getenv('TELEGRAM_CHAT_ID')

class SteamMonitor:
    def __init__(self):
        self.known_versions = self.load_state()
        self.new_updates = {}
        self.first_time_updates = {}

    def load_state(self):
        """加载已知版本状态"""
        try:
            if Path(STATE_FILE).exists():
                with open(STATE_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"加载状态失败: {e}")
            return {}

    def save_state(self):
        """增强版状态保存"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
            
            # 原子化写入（避免写入中途失败）
            temp_file = f"{STATE_FILE}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.known_versions, f, indent=2, ensure_ascii=False)
            
            # 重命名确保完整性
            os.replace(temp_file, STATE_FILE)
            print(f"状态已保存到 {os.path.abspath(STATE_FILE)}")
            
        except Exception as e:
            print(f"保存状态失败: {str(e)}")
            raise

    def get_game_update(self, appid):
        """获取游戏更新信息"""
        try:
            feed = feedparser.parse(STEAM_DB_URL.format(appid))
            if not feed.entries:
                return None

            entry = feed.entries[0]
            return {
                'title': entry.title.split(' for ')[0],  # 移除"for platform"后缀
                'link': entry.link,
                'published': entry.published,
                'timestamp': parser.parse(entry.published),
                'build_id': entry.link.split('/')[-2]
            }
        except Exception as e:
            print(f"获取游戏{appid}更新失败: {e}")
            return None

    def check_updates(self):
        """检查所有游戏的更新状态"""
        app_ids = self.load_config()
        for appid in app_ids:
            update = self.get_game_update(appid)
            if not update:
                continue

            appid_str = str(appid)
            if appid_str not in self.known_versions:
                self.first_time_updates[appid] = update
                self.known_versions[appid_str] = self._sanitize_update(update)
            elif update['build_id'] != self.known_versions[appid_str]['build_id']:
                self.new_updates[appid] = update
                self.known_versions[appid_str] = self._sanitize_update(update)

    def _sanitize_update(self, update):
        """准备可序列化的更新数据"""
        return {
            'title': update['title'],
            'link': update['link'],
            'published': update['published'],
            'build_id': update['build_id']
        }

    def load_config(self):
        """加载监控配置"""
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f).get('apps', [])
        except Exception as e:
            print(f"加载配置失败: {e}")
            return []

    def send_notification(self):
        """发送Telegram通知"""
        if self.first_time_updates:
            self._send_telegram(self._format_updates(self.first_time_updates, "新增监控游戏列表"))
        if self.new_updates:
            self._send_telegram(self._format_updates(self.new_updates, "本次更新游戏列表"))

    def _format_updates(self, updates, title):
        """格式化更新信息"""
        sorted_updates = sorted(updates.items(), key=lambda x: x[1]['timestamp'])
        message = [f"```\n{title}"]
        for appid, update in sorted_updates:
            time_str = update['timestamp'].strftime('%Y/%m/%d %H:%M')
            message.append(
                f"[GAME][{appid}] {update['title']} ({update['build_id']}) {time_str}"
            )
        message.append("```")
        return '\n'.join(message)

    def _send_telegram(self, message):
        """发送到Telegram"""
        try:
            response = requests.post(
                TELEGRAM_API,
                data={
                    'chat_id': TELEGRAM_CHAT,
                    'text': message,
                    'parse_mode': 'MarkdownV2'
                }
            )
            response.raise_for_status()
        except Exception as e:
            print(f"Telegram发送失败: {e}")

    def run(self):
        """主运行逻辑"""
        self.check_updates()
        if self.first_time_updates or self.new_updates:
            self.send_notification()
            self.save_state()

if __name__ == "__main__":
    monitor = SteamMonitor()
    monitor.run()
