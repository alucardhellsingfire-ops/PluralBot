"""
Fronting cog — log switches, view current front, history, and analytics.
Commands: /front set, clear, remove, view, history, stats
"""

import discord
from discord import app_commands
from discord.ext import commands
from utils.helpers import (
    require_system, front_embed, format_duration,
    get_member_display, parse_color, paginate
)


class FrontingCog(commands.Cog, name="Fronting"):
    """Track fronting, switches, and view analytics."""

    def __init__(self, bot):
        self.bot = bot

    front_group = app_commands.Group(name="front", description="Track and view fronting")

    @front_group.command(name="set", description="Log who is currently fronting (replaces current front)")
    @app_commands.describe(
        member="Member name who is fronting",
        note="Optional note (e.g. mood, context)",
        add="If True, ADD to front instead of replacing"
    )
    async def front_set(self, interaction: discord.Interaction,
                        member: str, note: str = None, add: bool = False):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        results = await self.bot.db.search_member(system['id'], member)
        if not results:
            await interaction.response.send_message(f"❌ Member `{member}` not found.", ephemeral=True)
            return

        m = results[0]

        if not add:
            await self.bot.db.clear_front(system['id'])

        await self.bot.db.set_front(system['id'], m['id'], note)

        fronters = await self.bot.db.get_current_front(system['id'])
        embed = front_embed(fronters, system['system_name'])
        await interaction.response.send_message(embed=embed)

        # Post to notification channel if set
        channel_id = await self.bot.db.get_notification_channel(system['id'], str(interaction.guild_id))
        if channel_id:
            channel = interaction.guild.get_channel(int(channel_id))
            if channel and channel.id != interaction.channel_id:
                try:
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    pass

    @front_group.command(name="add", description="Add another member to the current front (co-fronting)")
    @app_commands.describe(member="Member name to add to front", note="Optional note")
    async def front_add(self, interaction: discord.Interaction, member: str, note: str = None):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        results = await self.bot.db.search_member(system['id'], member)
        if not results:
            await interaction.response.send_message(f"❌ Member `{member}` not found.", ephemeral=True)
            return

        m = results[0]
        await self.bot.db.set_front(system['id'], m['id'], note)
        fronters = await self.bot.db.get_current_front(system['id'])
        embed = front_embed(fronters, system['system_name'])
        await interaction.response.send_message(embed=embed)

    @front_group.command(name="remove", description="Remove one member from a co-front")
    @app_commands.describe(member="Member name to remove from front")
    async def front_remove(self, interaction: discord.Interaction, member: str):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        results = await self.bot.db.search_member(system['id'], member)
        if not results:
            await interaction.response.send_message(f"❌ Member `{member}` not found.", ephemeral=True)
            return

        await self.bot.db.remove_from_front(system['id'], results[0]['id'])
        fronters = await self.bot.db.get_current_front(system['id'])
        embed = front_embed(fronters, system['system_name'])
        await interaction.response.send_message(embed=embed)

    @front_group.command(name="clear", description="Clear the current front (nobody is fronting)")
    async def front_clear(self, interaction: discord.Interaction):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        await self.bot.db.clear_front(system['id'])
        embed = discord.Embed(
            title=f"🌙 {system['system_name']} — Front Cleared",
            description="Nobody is currently fronting.",
            color=discord.Color(0x5865F2)
        )
        await interaction.response.send_message(embed=embed)

    @front_group.command(name="view", description="See who is currently fronting")
    async def front_view(self, interaction: discord.Interaction):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        fronters = await self.bot.db.get_current_front(system['id'])
        embed = front_embed(fronters, system['system_name'])
        await interaction.response.send_message(embed=embed)

    @front_group.command(name="history", description="View front switch history")
    @app_commands.describe(page="Page number", member="Filter by member name")
    async def front_history(self, interaction: discord.Interaction,
                            page: int = 1, member: str = None):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        history = await self.bot.db.get_front_history(system['id'], limit=200)

        if member:
            history = [f for f in history if
                       member.lower() in (f['name'] or '').lower() or
                       member.lower() in (f['display_name'] or '').lower()]

        if not history:
            await interaction.response.send_message("No front history yet.", ephemeral=True)
            return

        items, current_page, total_pages = paginate(list(history), page, 10)
        embed = discord.Embed(
            title=f"📋 {system['system_name']} — Front History",
            color=discord.Color(0x5865F2)
        )

        for entry in items:
            name = entry['display_name'] or entry['name']
            started = entry['started_at'][:16].replace('T', ' ')
            if entry['ended_at']:
                ended = entry['ended_at'][:16].replace('T', ' ')
                # Calculate duration
                from datetime import datetime
                try:
                    s = datetime.fromisoformat(entry['started_at'])
                    e = datetime.fromisoformat(entry['ended_at'])
                    dur = format_duration((e - s).total_seconds() / 60)
                    time_str = f"{started} → {ended} ({dur})"
                except Exception:
                    time_str = f"{started} → {ended}"
            else:
                time_str = f"{started} → *now*"

            value = time_str
            if entry.get('note'):
                value += f"\n*{entry['note']}*"

            embed.add_field(name=f"💜 {name}", value=value, inline=False)

        embed.set_footer(text=f"Page {current_page}/{total_pages} • {len(history)} total entries")
        await interaction.response.send_message(embed=embed)

    @front_group.command(name="stats", description="View fronting statistics and analytics")
    async def front_stats(self, interaction: discord.Interaction):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        await interaction.response.defer()
        stats = await self.bot.db.get_front_stats(system['id'])

        if not stats:
            await interaction.followup.send("No fronting data yet! Use `/front set` to start tracking.")
            return

        color = parse_color(system['color'])
        embed = discord.Embed(
            title=f"📊 {system['system_name']} — Fronting Analytics",
            color=color
        )

        total_minutes = sum(s['total_minutes'] for s in stats if s['total_minutes'])

        for s in stats[:10]:  # Top 10 fronters
            name = s['display_name'] or s['name']
            mins = s['total_minutes'] or 0
            count = s['switch_count']
            pct = (mins / total_minutes * 100) if total_minutes else 0
            bar_len = int(pct / 5)
            bar = '█' * bar_len + '░' * (20 - bar_len)
            embed.add_field(
                name=f"💜 {name}",
                value=f"`{bar}` {pct:.1f}%\n⏱️ {format_duration(mins)} • 🔄 {count} switch(es)",
                inline=False
            )

        embed.set_footer(text=f"Total tracked: {format_duration(total_minutes)}")
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(FrontingCog(bot))
