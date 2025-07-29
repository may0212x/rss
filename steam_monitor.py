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
        print("\n===== Steam游戏更新监控器 =====")
        print(f"当前时间: {datetime.now(pytz.timezone('Asia/Hong_Kong')).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"工作目录: {os.getcwd()}")
        
        # 确保状态文件存在
        self._ensure_state_file()
        
        self.hk_tz = pytz.timezone('Asia/Hong_Kong')
        self.known_versions = self.load_state()
        self.new_updates = {}
        self.first_time_updates = {}
        
        print(f"已加载 {len(self.known_versions)} 个游戏状态\n")

    def _ensure_state_file(self):
        """确保状态文件存在"""
        if not Path(STATE_FILE).exists():
            print(f"⚠️ 状态文件不存在，正在创建: {STATE_FILE}")
            with open(STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump({}, f, indent=2)

    def load_state(self):
        """加载已知版本状态"""
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"✅ 从 {STATE_FILE} 加载状态成功（{len(data)}条记录）")
                return data
        except Exception as e:
            print(f"❌ 加载状态失败: {e}")
            print("⚠️ 将使用空状态继续运行")
            return {}

    def save_state(self):
        """保存状态到文件"""
        try:
            with open(STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.known_versions, f, indent=2, ensure_ascii=False)
            print(f"✅ 状态已保存到 {STATE_FILE}（{len(self.known_versions)}条记录）")
        except Exception as e:
            print(f"❌ 保存状态失败: {e}")
            raise

    def get_game_update(self, appid):
        """从SteamDB获取游戏更新"""
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

    def check_updates(self):
        """检查所有游戏更新"""
        app_ids = self.load_config()
        print(f"\n开始检查 {len(app_ids)} 个游戏...")
        
        for idx, appid in enumerate(app_ids, 1):
            update = self.get_game_update(appid)
            if not update:
                continue

            appid_str = str(appid)
            current_build = self.known_versions.get(appid_str, {}).get('build_id')
            
            if appid_str not in self.known_versions:
                print(f"[{idx}/{len(app_ids)}] 🆕 新增游戏: {update['title']} (ID: {appid})")
                self.first_time_updates[appid] = update
                self.known_versions[appid_str] = self._sanitize_update(update)
            elif update['build_id'] != current_build:
                print(f"[{idx}/{len(appids)}] 🔄 发现更新: {update['title']} (版本: {current_build} → {update['build_id']})")
                self.new_updates[appid] = update
                self.known_versions[appid_str] = self._sanitize_update(update)
            else:
                print(f"[{idx}/{len(app_ids)}] ✅ 无更新: {update['title']} (当前版本: {current_build})")

    def _sanitize_update(self, update):
        """准备可序列化的更新数据"""
        return {
            'title': update['title'],
            'link': update['link'],
            'published': update['published'],
            'build_id': update['build_id'],
            'last_checked': datetime.now(self.hk_tz).isoformat()
        }

    def send_notification(self):
        """发送Telegram通知"""
        if self.first_time_updates:
            self._send_telegram(
                self._format_updates(self.first_time_updates, "🎮 新增监控游戏")
            )
        if self.new_updates:
            self._send_telegram(
                self._format_updates(self.new_updates, "🆕 游戏更新通知")
            )

    def _format_updates(self, updates, title):
        """格式化消息内容"""
        sorted_updates = sorted(updates.items(), key=lambda x: x[1]['timestamp'])
        message = [f"*{title}*", ""]
        
        for appid, update in sorted_updates:
            hk_time = update['timestamp'].strftime('%m/%d %H:%M')
            message.append(
                f"▪️ [{update['title']}]({update['link']})"
                f"\n  版本: `{update['build_id']}`"
                f"\n  更新时间: `{hk_time}`"
                f"\n  AppID: `{appid}`"
            )
        
        return "\n".join(message)

    def _send_telegram(self, message):
        """发送到Telegram"""
        try:
            print("\n📨 发送Telegram通知...")
            response = requests.post(
                TELEGRAM_API,
                data={
                    'chat_id': TELEGRAM_CHAT,
                    'text': message,
                    'parse_mode': 'Markdown',
                    'disable_web_page_preview': True
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
        print("\n🏁 监控任务完成")

if __name__ == "__main__":
    monitor = SteamMonitor()
    monitor.run()
