import asyncio
import aiohttp
import feedparser
import json
import os
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode
from tenacity import retry, stop_after_attempt, wait_exponential

# 配置常量
CACHE_FILE = "steamdb_cache.json"
BATCH_SIZE = 50  # 每批处理游戏数量
REQUEST_TIMEOUT = 30  # 单个请求超时时间(秒)

class SteamDBMonitor:
    def __init__(self):
        self.cache = {}
        self.session = None
        self.bot = None

    async def init(self):
        """异步初始化"""
        self.bot = Bot(token=os.getenv("TG_BOT_TOKEN"))
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            headers={"User-Agent": "SteamDB-Monitor/1.0"}
        )
        self.cache = self._load_cache()

    def _load_game_list(self):
        """加载游戏列表（分片支持）"""
        with open("games.json") as f:
            all_games = json.load(f)
        shard_id = int(os.getenv("SHARD_ID", "0"))
        total_shards = int(os.getenv("TOTAL_SHARDS", "1"))
        return [g for i,g in enumerate(all_games) if i % total_shards == shard_id]

    def _load_cache(self):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_cache(self):
        with open(CACHE_FILE, "w") as f:
            json.dump(self.cache, f)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _fetch_rss(self, app_id):
        """带重试机制的RSS获取"""
        url = f"https://steamdb.info/api/PatchnotesRSS/?appid={app_id}"
        try:
            async with self.session.get(url) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    return feedparser.parse(text)
                elif resp.status == 429:
                    await asyncio.sleep(60)  # 速率限制冷却
                    raise Exception("Rate limited")
        except Exception as e:
            print(f"Failed to fetch {app_id}: {str(e)}")
            raise

    async def _process_batch(self, batch):
        """处理一批游戏"""
        tasks = [self._check_game(app_id) for app_id in batch]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_game(self, app_id):
        """检查单个游戏更新"""
        try:
            feed = await self._fetch_rss(app_id)
            if not feed.entries:
                return None

            entry = feed.entries[0]
            build_id = entry.guid.split("#")[-1]
            
            if self.cache.get(str(app_id)) != build_id:
                pub_date = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %z")
                self.cache[str(app_id)] = build_id
                return {
                    "app_id": app_id,
                    "text": f"[GAME][{app_id}] {self._extract_name(entry.title)} ({build_id}) {pub_date.strftime('%Y/%m/%d %H:%M')}",
                    "pub_date": pub_date.timestamp()
                }
        except Exception as e:
            print(f"Error processing {app_id}: {str(e)}")
        return None

    def _extract_name(self, title):
        """优化版名称提取"""
        return title.split(" update for ")[0].split("/")[0]

    async def send_updates(self, updates):
        """智能消息分片发送"""
        if not updates:
            return

        updates.sort(key=lambda x: x["pub_date"])
        message_chunks = []
        current_chunk = "本次更新游戏列表\n"
        
        for update in updates:
            new_line = f"{update['text']}\n"
            if len(current_chunk) + len(new_line) > 4000:  # Telegram消息长度限制
                message_chunks.append(current_chunk)
                current_chunk = new_line
            else:
                current_chunk += new_line
        
        if current_chunk:
            message_chunks.append(current_chunk)

        for chunk in message_chunks:
            await self.bot.send_message(
                chat_id=os.getenv("TG_CHAT_ID"),
                text=f"```\n{chunk}\n```",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            await asyncio.sleep(1)  # 避免速率限制

    async def run(self):
        """主监控流程"""
        await self.init()
        try:
            game_list = self._load_game_list()
            total_games = len(game_list)
            
            for i in range(0, total_games, BATCH_SIZE):
                batch = game_list[i:i+BATCH_SIZE]
                results = await self._process_batch(batch)
                
                valid_updates = [r for r in results if r is not None and not isinstance(r, Exception)]
                if valid_updates:
                    await self.send_updates(valid_updates)
                    self._save_cache()
                
                print(f"Processed {min(i+BATCH_SIZE, total_games)}/{total_games} games")
                await asyncio.sleep(5)  # 批次间隔
            
        finally:
            await self.session.close()

if __name__ == "__main__":
    monitor = SteamDBMonitor()
    asyncio.run(monitor.run())
