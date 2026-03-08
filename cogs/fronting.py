"""
Fronting cog — log switches, view current front, history, and analytics.
"""

import discord
from discord import app_commands
from discord.ext import commands
from utils.helpers import (
    require_system, front_embed, format_duration,
    get_member_display, parse_color, paginate
)


class FrontingCog(commands.Cog, name="Fronting"):

    def __init__(self, bot):
        self.bot = bot

    front_group = app_commands.Group(name="front", description="Track and view fronting")

    async def _notify(self, interaction, system, embed):
        channel_id = await self.bot.db.get_notification_channel(system['id'], str(interaction.guild_id))
        if channel_id:
            channel = interaction.guild.get_channel(int(channel_id))
            if channel and channel.id != interaction.channel_id:
                try:
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    pass

    @front_group.command(name="set", description="Choose who is fronting from a dropdown (replaces current front)")
    @app_commands.describe(note="Optional note (e.g. mood, context)")
    async def front_set(self, interaction: discord.Interaction, note: str = None):
        await interaction.response.defer(ephemeral=True)
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        members = await self.bot.db.get_members(system['id'])
        if not members:
            await interaction.followup.send("❌ You have no members yet! Use `/member add` first.", ephemeral=True)
            return

        options = [
            discord.SelectOption(
                label=get_member_display(m),
                value=str(m['id']),
                description=(m['pronouns'] or m['role'] or '')[:100]
            )
            for m in members[:25]
        ]

        class FrontSetSelect(discord.ui.Select):
            def __init__(self_inner):
                super().__init__(
                    placeholder="Choose who is fronting...",
                    options=options,
                    min_values=1,
                    max_values=min(len(options), 5)
                )

            async def callback(self_inner, si: discord.Interaction):
                await si.response.defer(ephemeral=True)
                if si.user.id != interaction.user.id:
                    await si.followup.send("Not your system!", ephemeral=True)
                    return
                await self.bot.db.clear_front(system['id'])
                for mid in self_inner.values:
                    await self.bot.db.set_front(system['id'], int(mid), note)
                fronters = await self.bot.db.get_current_front(system['id'])
                embed = front_embed(fronters, system['system_name'])
                await si.edit_original_response(content=None, embed=embed, view=None)
                await self._notify(interaction, system, embed)

        view = discord.ui.View(timeout=60)
        view.add_item(FrontSetSelect())
        await interaction.followup.send("Who is fronting right now? (You can select multiple)", view=view, ephemeral=True)

    @front_group.command(name="add", description="Add someone to the current front (co-fronting)")
    @app_commands.describe(note="Optional note")
    async def front_add(self, interaction: discord.Interaction, note: str = None):
        await interaction.response.defer(ephemeral=True)
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        members = await self.bot.db.get_members(system['id'])
        if not members:
            await interaction.followup.send("❌ You have no members yet! Use `/member add` first.", ephemeral=True)
            return

        options = [
            discord.SelectOption(
                label=get_member_display(m),
                value=str(m['id']),
                description=(m['pronouns'] or m['role'] or '')[:100]
            )
            for m in members[:25]
        ]

        class FrontAddSelect(discord.ui.Select):
            def __init__(self_inner):
                super().__init__(
                    placeholder="Choose who to add to the front...",
                    options=options,
                    min_values=1,
                    max_values=min(len(options), 5)
                )

            async def callback(self_inner, si: discord.Interaction):
                await si.response.defer(ephemeral=True)
                if si.user.id != interaction.user.id:
                    await si.followup.send("Not your system!", ephemeral=True)
                    return
                for mid in self_inner.values:
                    await self.bot.db.set_front(system['id'], int(mid), note)
                fronters = await self.bot.db.get_current_front(system['id'])
                embed = front_embed(fronters, system['system_name'])
                await si.edit_original_response(content=None, embed=embed, view=None)
                await self._notify(interaction, system, embed)

        view = discord.ui.View(timeout=60)
        view.add_item(FrontAddSelect())
        await interaction.followup.send("Who do you want to add to the front?", view=view, ephemeral=True)

    @front_group.command(name="remove", description="Remove someone from the front using a dropdown")
    async def front_remove(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        fronters = await self.bot.db.get_current_front(system['id'])
        if not fronters:
            await interaction.followup.send("Nobody is currently fronting.", ephemeral=True)
            return

        options = [
            discord.SelectOption(
                label=f['display_name'] or f['name'],
                value=str(f['member_id'])
            )
            for f in fronters
        ]

        class FrontRemoveSelect(discord.ui.Select):
            def __init__(self_inner):
                super().__init__(placeholder="Choose who to remove from front...", options=options)

            async def callback(self_inner, si: discord.Interaction):
                await si.response.defer(ephemeral=True)
                if si.user.id != interaction.user.id:
                    await si.followup.send("Not your system!", ephemeral=True)
                    return
                await self.bot.db.remove_from_front(system['id'], int(self_inner.values[0]))
                remaining = await self.bot.db.get_current_front(system['id'])
                embed = front_embed(remaining, system['system_name'])
                await si.edit_original_response(content=None, embed=embed, view=None)

        view = discord.ui.View(timeout=60)
        view.add_item(FrontRemoveSelect())
        await interaction.followup.send("Who do you want to remove from the front?", view=view, ephemeral=True)

    @front_group.command(name="clear", description="Clear the current front (nobody is fronting)")
    async def front_clear(self, interaction: discord.Interaction):
        await interaction.response.defer()
        system = await require_system(interaction, self.bot.db)
        if not system:
            return
        await self.bot.db.clear_front(system['id'])
        embed = discord.Embed(
            title=f"🌙 {system['system_name']} — Front Cleared",
            description="Nobody is currently fronting.",
            color=discord.Color(0x5865F2)
        )
        await interaction.followup.send(embed=embed)

    @front_group.command(name="view", description="See who is currently fronting")
    async def front_view(self, interaction: discord.Interaction):
        await interaction.response.defer()
        system = await require_system(interaction, self.bot.db)
        if not system:
            return
        fronters = await self.bot.db.get_current_front(system['id'])
        embed = front_embed(fronters, system['system_name'])
        await interaction.followup.send(embed=embed)

    @front_group.command(name="history", description="View front switch history")
    @app_commands.describe(page="Page number", member="Filter by member name")
    async def front_history(self, interaction: discord.Interaction, page: int = 1, member: str = None):
        await interaction.response.defer(ephemeral=True)
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        history = await self.bot.db.get_front_history(system['id'], limit=200)
        if member:
            history = [f for f in history if
                       member.lower() in (f['name'] or '').lower() or
                       member.lower() in (f['display_name'] or '').lower()]

        if not history:
            await interaction.followup.send("No front history yet.", ephemeral=True)
            return

        items, current_page, total_pages = paginate(list(history), page, 10)
        embed = discord.Embed(title=f"📋 {system['system_name']} — Front History", color=discord.Color(0x5865F2))

        for entry in items:
            name = entry['display_name'] or entry['name']
            started = entry['started_at'][:16].replace('T', ' ')
            if entry['ended_at']:
                ended = entry['ended_at'][:16].replace('T', ' ')
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
        await interaction.followup.send(embed=embed, ephemeral=True)

    @front_group.command(name="stats", description="View fronting statistics and analytics")
    async def front_stats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        stats = await self.bot.db.get_front_stats(system['id'])
        if not stats:
            await interaction.followup.send("No fronting data yet! Use `/front set` to start tracking.")
            return

        color = parse_color(system['color'])
        embed = discord.Embed(title=f"📊 {system['system_name']} — Fronting Analytics", color=color)
        total_minutes = sum(s['total_minutes'] for s in stats if s['total_minutes'])

        for s in stats[:10]:
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
