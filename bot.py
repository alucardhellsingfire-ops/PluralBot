"""
PluralCord - A Discord bot for plural systems
A feature-rich replacement for Simply Plural, built with love for the plural community.
"""

import discord
from discord.ext import commands
import asyncio
import logging
import os
from utils.database import Database

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('pluralcord.log')
    ]
)
log = logging.getLogger('PluralCord')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True


class PluralCord(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix='pc!',
            intents=intents,
            description='PluralCord — System management for plural systems on Discord',
            help_command=None
        )
        self.db: Database = None

    async def setup_hook(self):
        self.db = Database('pluralcord.db')
        await self.db.init()

        cogs = [
            'cogs.members',
            'cogs.fronting',
            'cogs.journal',
            'cogs.polls',
            'cogs.proxying',
            'cogs.system',
            'cogs.friends',
            'cogs.help',
        ]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                log.info(f'Loaded cog: {cog}')
            except Exception as e:
                log.error(f'Failed to load cog {cog}: {e}')

        await self.tree.sync()
        log.info('Slash commands synced.')

    async def on_ready(self):
        log.info(f'PluralCord online as {self.user} (ID: {self.user.id})')
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="over your system 💜 | /help"
            )
        )

    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        log.error(f'Command error: {error}')


bot = PluralCord()


def main():
    token = os.environ.get('DISCORD_TOKEN')
    if not token:
        print("ERROR: Set your bot token in the DISCORD_TOKEN environment variable.")
        print("  export DISCORD_TOKEN=your_token_here")
        return
    bot.run(token, log_handler=None)


if __name__ == '__main__':
    main()
