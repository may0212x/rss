#!/usr/bin/env python3
import json
import os
import asyncio
from pathlib import Path
from datetime import datetime
from steam.client import SteamClient
from steam.enums.common import EResult
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

class SteamUpdateMonitor:
    def __init__(self):
        self.client = SteamClient()
        self.cache_file = Path("steam_updates_cache.json")
        self.games_file = Path("games.json")
        self._ensure_files_exist()

    def _ensure_files_exist(self):
        """确保所需文件存在"""
        self.cache_file.touch(exist_ok=True)
        if not self.games_file.exists():
            with open(self.games_file, 'w') as f:
                json.dump([400, 620, 730], f)  # 默认监控的游戏

    def _load_cache(self) -> dict:
        """加载缓存数据"""
        try:
            return json.loads(self.cache_file.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _save_cache(self, cache: dict):
        """保存缓存数据"""
        self.cache_file.write_text(json.dumps(cache, indent=2))

    def _login(self):
        """匿名登录Steam"""
        print("🔄 正在连接Steam...")
        result = self.client.anonymous_login()
        if result != EResult.OK:
            raise ConnectionError(f"❌ Steam连接失败: {result}")
        print("✅ Steam连接成功")

    async def get_game_updates(self, appid: int) -> dict:
        """获取游戏更新信息"""
        try:
            # 获取游戏产品信息
            info = self.client.get_product_info(apps=[appid])
            
            if not info or 'apps' not in info or str(appid) not in info['apps']:
                print(f"⚠️ AppID {appid} 未找到信息")
                return None
                
            app_info = info['apps'][str(appid)]
            last_updated = app_info.get('common', {}).get('last_updated')
            
            if not last_updated:
                print(f"⚠️ AppID {appid} 无更新时间数据")
                return None
                
            return {
                'appid': appid,
                'last_updated': last_updated,
                'time_str': datetime.fromtimestamp(last_updated).strftime('%Y/%m/%d %H:%M'),
                'name': app_info.get('common', {}).get('name', f"AppID {appid}")
            }
            
        except Exception as e:
            print(f"❌ 获取 AppID {appid} 失败: {str(e)}")
            return None

    async def send_telegram_notification(self, updates: list):
        """发送Telegram通知"""
        if not updates:
            print("ℹ️ 没有新更新需要通知")
            return
            
        bot = Bot(token=os.getenv("TG_BOT_TOKEN"))
        message = "```\n🎮 Steam游戏更新通知\n\n"
        
        for update in sorted(updates, key=lambda x: x['last_updated']):
            message += f"▫️ {update['name']}\n"
            message += f"   🆔 AppID: {update['appid']}\n"
            message += f"   ⏰ 更新时间: {update['time_str']}\n"
            message += f"   🔗 https://store.steampowered.com/app/{update['appid']}\n\n"
        
        message += "```"
        
        try:
            await bot.send_message(
                chat_id=os.getenv("TG_CHAT_ID"),
                text=message,
                parse_mode=ParseMode.MARKDOWN_V2
            )
            print("✅ 通知发送成功")
        except TelegramError as e:
            print(f"❌ Telegram发送失败: {str(e)}")
        except Exception as e:
            print(f"❌ 未知发送错误: {str(e)}")

    async def monitor(self):
        """主监控逻辑"""
        self._login()
        
        # 加载游戏列表
        try:
            appids = json.loads(self.games_file.read_text())
            if not appids:
                raise ValueError("游戏列表为空")
        except Exception as e:
            print(f"❌ 加载游戏列表失败: {str(e)}")
            return
            
        cache = self._load_cache()
        new_updates = []
        
        print(f"🔍 开始检查 {len(appids)} 个游戏...")
        for appid in appids:
            update = await self.get_game_updates(appid)
            if not update:
                continue
                
            # 检查是否有新更新
            cached_time = cache.get(str(appid), 0)
            if update['last_updated'] > cached_time:
                new_updates.append(update)
                cache[str(appid)] = update['last_updated']
                print(f"🆕 发现更新: {update['name']} (AppID: {appid})")
        
        if new_updates:
            await self.send_telegram_notification(new_updates)
            self._save_cache(cache)
        else:
            print("ℹ️ 没有发现新更新")
            
        self.client.disconnect()

if __name__ == "__main__":
    print("="*40)
    print("Steam游戏更新监控系统 v2.0")
    print("="*40)
    
    monitor = SteamUpdateMonitor()
    try:
        asyncio.run(monitor.monitor())
    except KeyboardInterrupt:
        print("\n🛑 手动中断")
    except Exception as e:
        print(f"❌ 全局错误: {str(e)}")
    finally:
        monitor.client.disconnect()
        print("✅ 程序结束")
