import json
import os
import asyncio
from pathlib import Path
from datetime import datetime
from steam.client import SteamClient
from steam.enums.common import EResult
from telegram import Bot
from telegram.constants import ParseMode

class SteamUpdateMonitor:
    def __init__(self):
        self.client = SteamClient()
        self.cache_file = "steam_updates_cache.json"
        self.games_file = "games.json"
        self._init_cache()
        
    def _init_cache(self):
        """初始化缓存文件"""
        self.cache_path = Path(self.cache_file)
        if not self.cache_path.exists():
            with open(self.cache_file, 'w') as f:
                json.dump({}, f)
    
    def _load_cache(self):
        """加载缓存数据"""
        try:
            with open(self.cache_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_cache(self, cache):
        """保存缓存数据"""
        with open(self.cache_file, 'w') as f:
            json.dump(cache, f, indent=2)

    def _login(self):
        """匿名登录Steam"""
        print("Connecting to Steam...")
        result = self.client.anonymous_login()
        if result != EResult.OK:
            raise ConnectionError(f"Steam连接失败: {result}")
        print("Steam连接成功")

    async def get_game_updates(self, appid):
        """获取游戏更新信息"""
        try:
            # 使用ProductInfo接口获取游戏信息
            info = self.client.get_product_info(apps=[appid])
            
            if not info or 'apps' not in info or str(appid) not in info['apps']:
                return None
                
            app_info = info['apps'][str(appid)]
            
            # 提取最新更新时间
            if 'common' in app_info and 'last_updated' in app_info['common']:
                last_updated = app_info['common']['last_updated']
                return {
                    'appid': appid,
                    'last_updated': last_updated,
                    'time_str': datetime.fromtimestamp(last_updated).strftime('%Y/%m/%d %H:%M')
                }
            return None
            
        except Exception as e:
            print(f"获取AppID {appid}更新失败: {str(e)}")
            return None

    async def send_telegram_notification(self, updates):
        """发送Telegram通知"""
        if not updates:
            return
            
        bot = Bot(token=os.getenv("TG_BOT_TOKEN"))
        message = "```\n📢 Steam游戏更新通知\n\n"
        
        for update in updates:
            message += f"🆔 [AppID: {update['appid']}]\n"
            message += f"⏰ 最后更新: {update['time_str']}\n"
            message += f"🔗 https://store.steampowered.com/app/{update['appid']}\n\n"
        
        message += "```"
        
        try:
            await bot.send_message(
                chat_id=os.getenv("TG_CHAT_ID"),
                text=message,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as e:
            print(f"发送Telegram通知失败: {str(e)}")

    async def monitor_updates(self):
        """主监控逻辑"""
        self._login()
        
        # 加载游戏列表
        with open(self.games_file, 'r') as f:
            appids = json.load(f)
            
        cache = self._load_cache()
        new_updates = []
        
        for appid in appids:
            update = await self.get_game_updates(appid)
            if not update:
                continue
                
            # 检查是否有新更新
            cached_time = cache.get(str(appid), 0)
            if update['last_updated'] > cached_time:
                new_updates.append(update)
                cache[str(appid)] = update['last_updated']
                print(f"发现新更新: AppID {appid} 于 {update['time_str']}")
        
        if new_updates:
            await self.send_telegram_notification(new_updates)
            self._save_cache(cache)
        else:
            print("没有发现新更新")
            
        self.client.disconnect()

if __name__ == "__main__":
    monitor = SteamUpdateMonitor()
    asyncio.run(monitor.monitor_updates())
