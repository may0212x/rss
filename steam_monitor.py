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
    print("\n===== 初始化监控器 =====")
    print(f"工作目录: {os.getcwd()}")
    
    self.hk_tz = pytz.timezone('Asia/Hong_Kong')
    
    # 確保狀態文件路徑正確
    self.STATE_FILE = os.path.join(os.getcwd(), "last_known_versions.json")
    print(f"狀態文件路徑: {self.STATE_FILE}")
    
    self.known_versions = self.load_state()
    self.new_updates = {}
    self.first_time_updates = {}
    
    print(f"已加载 {len(self.known_versions)} 个游戏状态\n")

    def load_state(self):
        """加载已知版本状态"""
        try:
            if Path(STATE_FILE).exists():
                with open(STATE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"从缓存加载状态成功（{len(data)}条记录）")
                    return data
            print("无现有状态文件，将创建新记录")
            return {}
        except Exception as e:
            print(f"⚠️ 加载状态失败: {e}")
            return {}

    def save_state(self):
        """保存状态到文件"""
        try:
            with open(STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.known_versions, f, indent=2, ensure_ascii=False)
            print(f"\n✅ 状态已保存（{len(self.known_versions)}条记录）")
        except Exception as e:
            print(f"❌ 保存状态失败: {e}")
            raise

    def get_game_update(self, appid):
        """从SteamDB获取游戏更新（带香港时间转换）"""
        try:
            url = STEAM_DB_URL.format(appid)
            feed = feedparser.parse(url)
            
            if not feed.entries:
                print(f"⚠️ 游戏 {appid} 无更新记录")
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
        print(f"开始检查 {len(app_ids)} 个游戏...")
        
        for idx, appid in enumerate(app_ids, 1):
            update = self.get_game_update(appid)
            if not update:
                continue

            appid_str = str(appid)
            if appid_str not in self.known_versions:
                print(f"[{idx}/{len(app_ids)}] 新增游戏: {update['title']} (ID: {appid})")
                self.first_time_updates[appid] = update
                self.known_versions[appid_str] = self._sanitize_update(update)
            elif update['build_id'] != self.known_versions[appid_str]['build_id']:
                print(f"[{idx}/{len(app_ids)}] 发现更新: {update['title']} (新版本: {update['build_id']})")
                self.new_updates[appid] = update
                self.known_versions[appid_str] = self._sanitize_update(update)
            else:
                print(f"[{idx}/{len(app_ids)}] 无更新: {self.known_versions[appid_str]['title']}")

    def _sanitize_update(self, update):
        """准备可序列化的更新数据"""
        return {
            'title': update['title'].replace(' update', ''),
            'link': update['link'],
            'published': update['published'],
            'build_id': update['build_id']
        }

    def load_config(self):
        """加载监控配置"""
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                apps = json.load(f).get('apps', [])
                print(f"已加载 {len(apps)} 个监控游戏")
                return apps
        except Exception as e:
            print(f"❌ 加载配置失败: {e}")
            return []

    def send_notification(self):
        """发送Telegram通知（香港时间）"""
        if self.first_time_updates:
            self._send_telegram(
                self._format_updates(self.first_time_updates, "🎮 新增监控游戏列表")
            )
        if self.new_updates:
            self._send_telegram(
                self._format_updates(self.new_updates, "🆕 本次更新游戏列表")
            )

    def _format_updates(self, updates, title):
        """格式化消息内容（香港时间）"""
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
            print("\n📨 发送Telegram通知...")
            response = requests.post(
                TELEGRAM_API,
                data={
                    'chat_id': TELEGRAM_CHAT,
                    'text': message,
                    'parse_mode': 'MarkdownV2'
                },
                timeout=10
            )
            response.raise_for_status()
            print("✅ 通知发送成功")
        except Exception as e:
            print(f"❌ Telegram发送失败: {e}")

    def run(self):
        """主运行流程"""
        self.check_updates()
        if self.first_time_updates or self.new_updates:
            self.send_notification()
            self.save_state()
        else:
            print("\nℹ️ 未检测到新更新")

if __name__ == "__main__":
    monitor = SteamMonitor()
    monitor.run()
