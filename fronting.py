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


class ConfirmView(discord.ui.View):
    """A reusable Confirm / Cancel button pair."""

    def __init__(self, original_interaction: discord.Interaction, confirm_label: str = "✅ Confirm", danger: bool = False):
        super().__init__(timeout=30)
        self.original_interaction = original_interaction
        self.confirmed = False

        style = discord.ButtonStyle.danger if danger else discord.ButtonStyle.success

        confirm_btn = discord.ui.Button(label=confirm_label, style=style)
        cancel_btn = discord.ui.Button(label="❌ Cancel", style=discord.ButtonStyle.secondary)

        confirm_btn.callback = self._confirm
        cancel_btn.callback = self._cancel

        self.add_item(confirm_btn)
        self.add_item(cancel_btn)

    async def _confirm(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != self.original_interaction.user.id:
            await interaction.followup.send("Not your system!", ephemeral=True)
            return
        self.confirmed = True
        self.stop()

    async def _cancel(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        self.confirmed = False
        embed = discord.Embed(title="Cancelled.", color=discord.Color.greyple())
        await interaction.edit_original_response(embed=embed, view=None)
        self.stop()

    async def on_timeout(self):
        try:
            embed = discord.Embed(title="Timed out — no changes made.", color=discord.Color.greyple())
            await self.original_interaction.edit_original_response(embed=embed, view=None)
        except Exception:
            pass


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

        selected_ids = []

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

                selected_ids.clear()
                selected_ids.extend(self_inner.values)

                # Build the names of who was selected
                chosen = [get_member_display(m) for m in members if str(m['id']) in selected_ids]
                names = ', '.join(f'**{n}**' for n in chosen)

                confirm = ConfirmView(interaction)
                embed = discord.Embed(
                    title="Confirm Front Switch",
                    description=f"Set front to: {names}?\n\nThis will replace whoever is currently fronting.",
                    color=discord.Color(0x5865F2)
                )
                if note:
                    embed.add_field(name="Note", value=note)

                await si.edit_original_response(embed=embed, view=confirm)
                await confirm.wait()

                if confirm.confirmed:
                    await self.bot.db.clear_front(system['id'])
                    for mid in selected_ids:
                        await self.bot.db.set_front(system['id'], int(mid), note)
                    fronters = await self.bot.db.get_current_front(system['id'])
                    result_embed = front_embed(fronters, system['system_name'])
                    await si.edit_original_response(embed=result_embed, view=None)
                    await self._notify(interaction, system, result_embed)

        select_view = discord.ui.View(timeout=60)
        select_view.add_item(FrontSetSelect())
        await interaction.followup.send(
            "Who is fronting right now? (You can select multiple)",
            view=select_view,
            ephemeral=True
        )

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

        selected_ids = []

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

                selected_ids.clear()
                selected_ids.extend(self_inner.values)

                chosen = [get_member_display(m) for m in members if str(m['id']) in selected_ids]
                names = ', '.join(f'**{n}**' for n in chosen)

                confirm = ConfirmView(interaction)
                embed = discord.Embed(
                    title="Confirm Co-Front Addition",
                    description=f"Add {names} to the current front?",
                    color=discord.Color(0x5865F2)
                )
                if note:
                    embed.add_field(name="Note", value=note)

                await si.edit_original_response(embed=embed, view=confirm)
                await confirm.wait()

                if confirm.confirmed:
                    for mid in selected_ids:
                        await self.bot.db.set_front(system['id'], int(mid), note)
                    fronters = await self.bot.db.get_current_front(system['id'])
                    result_embed = front_embed(fronters, system['system_name'])
                    await si.edit_original_response(embed=result_embed, view=None)
                    await self._notify(interaction, system, result_embed)

        select_view = discord.ui.View(timeout=60)
        select_view.add_item(FrontAddSelect())
        await interaction.followup.send(
            "Who do you want to add to the front?",
            view=select_view,
            ephemeral=True
        )

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

        selected_id = []

        class FrontRemoveSelect(discord.ui.Select):
            def __init__(self_inner):
                super().__init__(placeholder="Choose who to remove from front...", options=options)

            async def callback(self_inner, si: discord.Interaction):
                await si.response.defer(ephemeral=True)
                if si.user.id != interaction.user.id:
                    await si.followup.send("Not your system!", ephemeral=True)
                    return

                selected_id.clear()
                selected_id.append(self_inner.values[0])

                chosen_name = next(
                    (f['display_name'] or f['name'] for f in fronters if str(f['member_id']) == selected_id[0]),
                    "this member"
                )

                confirm = ConfirmView(interaction, confirm_label="✅ Remove", danger=True)
                embed = discord.Embed(
                    title="Confirm Front Removal",
                    description=f"Remove **{chosen_name}** from the front?",
                    color=discord.Color.red()
                )

                await si.edit_original_response(embed=embed, view=confirm)
                await confirm.wait()

                if confirm.confirmed:
                    await self.bot.db.remove_from_front(system['id'], int(selected_id[0]))
                    remaining = await self.bot.db.get_current_front(system['id'])
                    result_embed = front_embed(remaining, system['system_name'])
                    await si.edit_original_response(embed=result_embed, view=None)

        select_view = discord.ui.View(timeout=60)
        select_view.add_item(FrontRemoveSelect())
        await interaction.followup.send(
            "Who do you want to remove from the front?",
            view=select_view,
            ephemeral=True
        )

    @front_group.command(name="clear", description="Clear the current front (nobody is fronting)")
    async def front_clear(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        confirm = ConfirmView(interaction, confirm_label="✅ Clear Front", danger=True)
        embed = discord.Embed(
            title="Confirm Clear Front",
            description="Remove everyone from the front?",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, view=confirm, ephemeral=True)
        await confirm.wait()

        if confirm.confirmed:
            await self.bot.db.clear_front(system['id'])
            result_embed = discord.Embed(
                title=f"🌙 {system['system_name']} — Front Cleared",
                description="Nobody is currently fronting.",
                color=discord.Color(0x5865F2)
            )
            await interaction.edit_original_response(embed=result_embed, view=None)

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
            bar = '█' * int(pct / 5) + '░' * (20 - int(pct / 5))
            embed.add_field(
                name=f"💜 {name}",
                value=f"`{bar}` {pct:.1f}%\n⏱️ {format_duration(mins)} • 🔄 {count} switch(es)",
                inline=False
            )

        embed.set_footer(text=f"Total tracked: {format_duration(total_minutes)}")
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(FrontingCog(bot))
