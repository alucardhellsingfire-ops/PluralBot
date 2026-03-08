"""
PluralCord - A Discord bot for plural systems
A feature-rich replacement for Simply Plural, built with love for the plural community.
"""

import discord
from discord import app_commands
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
        db_path = os.environ.get('DB_PATH', 'pluralcord.db')
        self.db = Database(db_path)
        await self.db.init()
        log.info(f'Database loaded from: {db_path}')

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

    async def on_app_command_error(self, interaction: discord.Interaction, error: Exception):
        """Handle slash command errors so Discord never shows 'application did not respond'."""
        log.error(
            f'Slash command error in /{interaction.command.name if interaction.command else "unknown"}: {error}',
            exc_info=error
        )

        message = "❌ Something went wrong running that command. Please try again."

        if isinstance(error, app_commands.CommandOnCooldown):
            message = f"⏳ Command on cooldown. Try again in {error.retry_after:.1f}s."
        elif isinstance(error, app_commands.MissingPermissions):
            message = "❌ You don't have permission to use that command."
        elif isinstance(error, app_commands.BotMissingPermissions):
            message = f"❌ I'm missing a permission needed for that: `{', '.join(error.missing_permissions)}`"

        try:
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)
        except Exception as e:
            log.error(f'Failed to send error message: {e}')


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
