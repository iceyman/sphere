import discord
from discord.ext import commands, tasks
import aiohttp
import re
import logging
import os
import asyncio
import utils.settings as s

log_directory = s.chatlog_path
webhook_url = s.chatlog_webhook

class ChatFeedCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_directory = log_directory
        self.webhook_url = webhook_url
        self.first_check_done = False
        self.last_processed_line = None
        self.current_log_file = None
        self.check_logs.start()
        self.blocked_phrases = ["/adminpassword", "/creativemenu", "/"]

    def cog_unload(self):
        self.check_logs.cancel()

    @tasks.loop(seconds=8)
    async def check_logs(self):
        try:
            files = sorted(
                [
                    f for f in os.listdir(self.log_directory)
                    if f.endswith(".txt") or f.endswith(".log")
                ],
                key=lambda x: os.stat(os.path.join(self.log_directory, x)).st_mtime,
                reverse=True
            )
            if not files:
                return

            newest_file = os.path.join(self.log_directory, files[0])
            if self.current_log_file != newest_file:
                self.current_log_file = newest_file
                self.last_processed_line = None
                self.first_check_done = False

            with open(self.current_log_file, "r", encoding="utf-8", errors="ignore") as file:
                content = file.read()
                lines = content.splitlines()

            if not self.first_check_done:
                if lines:
                    self.last_processed_line = lines[-1]
                self.first_check_done = True
                return

            new_lines_start = False
            for line in lines:
                if line == self.last_processed_line:
                    new_lines_start = True
                    continue
                if new_lines_start or self.last_processed_line is None:
                    if "[Chat::" in line:
                        await self.process_and_send(line)

            if lines:
                self.last_processed_line = lines[-1]
        except:
            pass

    async def process_and_send(self, line):
        try:
            match = re.search(r"\[Chat::(?:Global|Local|Guild)\]\['([^']+)'.*\]: (.*)", line)
            if match:
                username, message = match.groups()
                if any(bp in message for bp in self.blocked_phrases):
                    return
                async with aiohttp.ClientSession() as session:
                    async with session.post(self.webhook_url, json={"username": username, "content": message}):
                        await asyncio.sleep(1)
        except:
            pass

    @check_logs.before_loop
    async def before_check_logs(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    if not os.getenv("CHATLOG_PATH") or not os.getenv("CHATLOG_WEBHOOKURL"):
        logging.error("CHATLOG_PATH and CHATLOG_WEBHOOKURL must be set.")
        return
    await bot.add_cog(ChatFeedCog(bot))
