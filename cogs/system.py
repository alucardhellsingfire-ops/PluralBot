"""
System cog — manage your plural system's core identity.
Commands: /system create, view, edit, delete, set-channel, export
"""

import discord
from discord import app_commands
from discord.ext import commands
import json
from utils.helpers import system_embed, require_system, parse_color


class SystemCog(commands.Cog, name="System"):
    """Manage your plural system's identity and settings."""

    def __init__(self, bot):
        self.bot = bot

    system_group = app_commands.Group(name="system", description="Manage your plural system")

    @system_group.command(name="create", description="Register your plural system")
    @app_commands.describe(name="Your system's name")
    async def system_create(self, interaction: discord.Interaction, name: str):
        db = self.bot.db
        existing = await db.get_system(str(interaction.user.id), str(interaction.guild_id))
        if existing:
            await interaction.response.send_message(
                "❌ You already have a system registered! Use `/system edit` to update it.",
                ephemeral=True
            )
            return
        sys_id = await db.create_system(str(interaction.user.id), str(interaction.guild_id), name)
        system = await db.get_system_by_id(sys_id)
        embed = system_embed(system, 0)
        embed.description = "✅ Your system has been created! Use `/system edit` to customize it.\nAdd members with `/member add`."
        await interaction.response.send_message(embed=embed)

    @system_group.command(name="view", description="View your system's profile")
    async def system_view(self, interaction: discord.Interaction):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return
        members = await self.bot.db.get_members(system['id'])
        embed = system_embed(system, len(members))
        await interaction.response.send_message(embed=embed)

    @system_group.command(name="edit", description="Edit your system's profile")
    @app_commands.describe(
        name="System name",
        tag="Short tag (e.g. [SYS])",
        description="System description",
        color="Hex color (e.g. #FF69B4)",
        avatar="URL to a system avatar image",
        privacy="Default privacy (public/private)"
    )
    async def system_edit(self, interaction: discord.Interaction,
                          name: str = None, tag: str = None,
                          description: str = None, color: str = None,
                          avatar: str = None, privacy: str = None):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        updates = {}
        if name:
            updates['system_name'] = name
        if tag is not None:
            updates['system_tag'] = tag
        if description is not None:
            updates['description'] = description
        if color:
            updates['color'] = color
        if avatar is not None:
            updates['avatar_url'] = avatar
        if privacy in ('public', 'private'):
            updates['privacy_default'] = privacy

        if not updates:
            await interaction.response.send_message("❌ No changes provided.", ephemeral=True)
            return

        await self.bot.db.update_system(system['id'], **updates)
        system = await self.bot.db.get_system_by_id(system['id'])
        members = await self.bot.db.get_members(system['id'])
        embed = system_embed(system, len(members))
        embed.description = "✅ System updated!"
        await interaction.response.send_message(embed=embed)

    @system_group.command(name="delete", description="⚠️ Permanently delete your system and all data")
    async def system_delete(self, interaction: discord.Interaction):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        embed = discord.Embed(
            title="⚠️ Confirm Deletion",
            description=(
                f"Are you sure you want to delete **{system['system_name']}**?\n\n"
                "This will permanently erase:\n"
                "• All members\n• Front history\n• Journal entries\n• Polls\n• Notes\n\n"
                "**This cannot be undone.**"
            ),
            color=discord.Color.red()
        )

        class ConfirmView(discord.ui.View):
            def __init__(self, db, system_id):
                super().__init__(timeout=30)
                self.db = db
                self.system_id = system_id

            @discord.ui.button(label="Delete Forever", style=discord.ButtonStyle.danger)
            async def confirm(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
                if btn_interaction.user.id != interaction.user.id:
                    await btn_interaction.response.send_message("Not your system!", ephemeral=True)
                    return
                await self.db.delete_system(self.system_id)
                await btn_interaction.response.edit_message(
                    embed=discord.Embed(title="System deleted.", color=discord.Color.greyple()),
                    view=None
                )

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
                await btn_interaction.response.edit_message(
                    embed=discord.Embed(title="Deletion cancelled.", color=discord.Color.green()),
                    view=None
                )

        await interaction.response.send_message(
            embed=embed,
            view=ConfirmView(self.bot.db, system['id']),
            ephemeral=True
        )

    @system_group.command(name="set-channel", description="Set a channel for front-change notifications")
    @app_commands.describe(channel="The channel to post front notifications in")
    async def set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return
        await self.bot.db.set_notification_channel(system['id'], str(channel.id), str(interaction.guild_id))
        await interaction.response.send_message(
            f"✅ Front notifications will now be posted in {channel.mention}",
            ephemeral=True
        )

    @system_group.command(name="export", description="Export all your system data as JSON")
    async def system_export(self, interaction: discord.Interaction):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return
        await interaction.response.defer(ephemeral=True)

        db = self.bot.db
        members = await db.get_members(system['id'], include_archived=True)
        fronts = await db.get_front_history(system['id'], limit=1000)
        journal = await db.get_journal_entries(system['id'], limit=1000)

        export = {
            "system": dict(system),
            "members": [dict(m) for m in members],
            "front_history": [dict(f) for f in fronts],
            "journal": [dict(j) for j in journal],
        }

        data_str = json.dumps(export, indent=2, default=str)
        file = discord.File(
            fp=__import__('io').BytesIO(data_str.encode()),
            filename=f"pluralcord_export_{system['id']}.json"
        )
        await interaction.followup.send(
            "✅ Here's your system data export! Keep this safe.",
            file=file,
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(SystemCog(bot))
