"""
Members cog — add, view, edit, archive, and delete system members (alters/headmates).
Commands: /member add, view, edit, list, delete, archive, groups
"""

import discord
from discord import app_commands
from discord.ext import commands
from utils.helpers import member_embed, require_system, paginate, get_member_display


class MemberCog(commands.Cog, name="Members"):
    """Manage your system's members (headmates/alters)."""

    def __init__(self, bot):
        self.bot = bot

    member_group = app_commands.Group(name="member", description="Manage system members")
    group_group = app_commands.Group(name="group", description="Manage member groups/subsystems")

    # -------------------------------------------------------------------------
    # MEMBER COMMANDS
    # -------------------------------------------------------------------------

    @member_group.command(name="add", description="Add a new member to your system")
    @app_commands.describe(
        name="Member's name",
        pronouns="Their pronouns (e.g. she/her)",
        description="A short description or bio",
        color="Hex color code (e.g. #FF69B4)",
        role="Their role in the system (e.g. Protector, Littles)",
        avatar="URL to their avatar image",
        proxy_prefix="Proxy prefix (e.g. 'A:')",
        proxy_suffix="Proxy suffix (e.g. '-A')",
        birthday="Birthday (e.g. March 15)"
    )
    async def member_add(self, interaction: discord.Interaction,
                         name: str,
                         pronouns: str = None,
                         description: str = None,
                         color: str = None,
                         role: str = None,
                         avatar: str = None,
                         proxy_prefix: str = None,
                         proxy_suffix: str = None,
                         birthday: str = None):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        kwargs = {}
        if pronouns: kwargs['pronouns'] = pronouns
        if description: kwargs['description'] = description
        if color: kwargs['color'] = color
        if role: kwargs['role'] = role
        if avatar: kwargs['avatar_url'] = avatar
        if proxy_prefix: kwargs['proxy_prefix'] = proxy_prefix
        if proxy_suffix: kwargs['proxy_suffix'] = proxy_suffix
        if birthday: kwargs['birthday'] = birthday

        member_id = await self.bot.db.create_member(system['id'], name, **kwargs)
        member = await self.bot.db.get_member(member_id)
        embed = member_embed(member, system)
        embed.description = f"✅ **{name}** has been added to {system['system_name']}!"
        await interaction.response.send_message(embed=embed)

    @member_group.command(name="view", description="View a member's profile")
    @app_commands.describe(name="Member name to look up")
    async def member_view(self, interaction: discord.Interaction, name: str):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        results = await self.bot.db.search_member(system['id'], name)
        if not results:
            await interaction.response.send_message(f"❌ No member found matching `{name}`.", ephemeral=True)
            return

        member = results[0]
        embed = member_embed(member, system)

        # Show notes count
        notes = await self.bot.db.get_notes(system['id'], member['id'])
        if notes:
            embed.add_field(name="Notes", value=f"{len(notes)} note(s) on file", inline=True)

        await interaction.response.send_message(embed=embed)

    @member_group.command(name="edit", description="Edit a member's profile")
    @app_commands.describe(
        name="Member name to edit",
        new_name="New name",
        display_name="Display name (shown instead of name)",
        pronouns="Pronouns",
        description="Bio/description",
        color="Hex color",
        role="Role in system",
        avatar="Avatar URL",
        proxy_prefix="Proxy prefix",
        proxy_suffix="Proxy suffix",
        birthday="Birthday"
    )
    async def member_edit(self, interaction: discord.Interaction,
                          name: str,
                          new_name: str = None,
                          display_name: str = None,
                          pronouns: str = None,
                          description: str = None,
                          color: str = None,
                          role: str = None,
                          avatar: str = None,
                          proxy_prefix: str = None,
                          proxy_suffix: str = None,
                          birthday: str = None):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        results = await self.bot.db.search_member(system['id'], name)
        if not results:
            await interaction.response.send_message(f"❌ No member found matching `{name}`.", ephemeral=True)
            return

        member = results[0]
        updates = {}
        if new_name: updates['name'] = new_name
        if display_name is not None: updates['display_name'] = display_name
        if pronouns is not None: updates['pronouns'] = pronouns
        if description is not None: updates['description'] = description
        if color: updates['color'] = color
        if role is not None: updates['role'] = role
        if avatar is not None: updates['avatar_url'] = avatar
        if proxy_prefix is not None: updates['proxy_prefix'] = proxy_prefix
        if proxy_suffix is not None: updates['proxy_suffix'] = proxy_suffix
        if birthday is not None: updates['birthday'] = birthday

        if not updates:
            await interaction.response.send_message("❌ No changes provided.", ephemeral=True)
            return

        await self.bot.db.update_member(member['id'], **updates)
        updated = await self.bot.db.get_member(member['id'])
        embed = member_embed(updated, system)
        embed.description = "✅ Member updated!"
        await interaction.response.send_message(embed=embed)

    @member_group.command(name="list", description="List all members in your system")
    @app_commands.describe(page="Page number", show_archived="Include archived members")
    async def member_list(self, interaction: discord.Interaction,
                          page: int = 1, show_archived: bool = False):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        all_members = await self.bot.db.get_members(system['id'], include_archived=show_archived)
        if not all_members:
            await interaction.response.send_message(
                "No members yet! Use `/member add` to add your first headmate. 💜",
                ephemeral=True
            )
            return

        items, current_page, total_pages = paginate(all_members, page, 15)
        from utils.helpers import parse_color
        color = parse_color(system['color'])
        embed = discord.Embed(
            title=f"💜 {system['system_name']} — Members",
            color=color
        )

        lines = []
        for m in items:
            display = get_member_display(m)
            parts = [f"**{display}**"]
            if m['pronouns']:
                parts.append(f"({m['pronouns']})")
            if m['role']:
                parts.append(f"• *{m['role']}*")
            if m['is_archived']:
                parts.append("*(archived)*")
            if m['proxy_prefix'] or m['proxy_suffix']:
                prefix = m['proxy_prefix'] or ''
                suffix = m['proxy_suffix'] or ''
                parts.append(f"[`{prefix}text{suffix}`]")
            lines.append(' '.join(parts))

        embed.description = '\n'.join(lines)
        embed.set_footer(text=f"Page {current_page}/{total_pages} • {len(all_members)} total member(s)")
        await interaction.response.send_message(embed=embed)

    @member_group.command(name="delete", description="Permanently delete a member from your system")
    @app_commands.describe(name="Member name to delete")
    async def member_delete(self, interaction: discord.Interaction, name: str):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        results = await self.bot.db.search_member(system['id'], name)
        if not results:
            await interaction.response.send_message(f"❌ No member found matching `{name}`.", ephemeral=True)
            return

        member = results[0]
        display = get_member_display(member)

        class ConfirmView(discord.ui.View):
            def __init__(self, db, member_id):
                super().__init__(timeout=30)
                self.db = db
                self.member_id = member_id

            @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
            async def confirm(self, btn_i: discord.Interaction, button: discord.ui.Button):
                if btn_i.user.id != interaction.user.id:
                    await btn_i.response.send_message("Not your system!", ephemeral=True)
                    return
                await self.db.delete_member(self.member_id)
                await btn_i.response.edit_message(
                    embed=discord.Embed(title=f"{display} has been removed.", color=discord.Color.greyple()),
                    view=None
                )

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, btn_i: discord.Interaction, button: discord.ui.Button):
                await btn_i.response.edit_message(
                    embed=discord.Embed(title="Deletion cancelled.", color=discord.Color.green()),
                    view=None
                )

        await interaction.response.send_message(
            embed=discord.Embed(
                title=f"Delete {display}?",
                description="This will permanently remove the member and all their data.",
                color=discord.Color.red()
            ),
            view=ConfirmView(self.bot.db, member['id']),
            ephemeral=True
        )

    @member_group.command(name="archive", description="Archive (hide) a member without deleting them")
    @app_commands.describe(name="Member name to archive", unarchive="Set True to restore an archived member")
    async def member_archive(self, interaction: discord.Interaction,
                             name: str, unarchive: bool = False):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        all_members = await self.bot.db.get_members(system['id'], include_archived=True)
        member = next((m for m in all_members if m['name'].lower() == name.lower()), None)
        if not member:
            await interaction.response.send_message(f"❌ No member found matching `{name}`.", ephemeral=True)
            return

        new_state = 0 if unarchive else 1
        await self.bot.db.update_member(member['id'], is_archived=new_state)
        action = "restored" if unarchive else "archived"
        await interaction.response.send_message(
            f"✅ **{get_member_display(member)}** has been {action}.",
            ephemeral=True
        )

    @member_group.command(name="note", description="Add a note to a member")
    @app_commands.describe(name="Member name", note="The note to add")
    async def member_note(self, interaction: discord.Interaction, name: str, note: str):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        results = await self.bot.db.search_member(system['id'], name)
        if not results:
            await interaction.response.send_message(f"❌ Member `{name}` not found.", ephemeral=True)
            return

        member = results[0]
        await self.bot.db.add_note(system['id'], note, member['id'])
        await interaction.response.send_message(
            f"✅ Note added for **{get_member_display(member)}**.",
            ephemeral=True
        )

    @member_group.command(name="notes", description="View notes for a member")
    @app_commands.describe(name="Member name")
    async def member_notes(self, interaction: discord.Interaction, name: str):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        results = await self.bot.db.search_member(system['id'], name)
        if not results:
            await interaction.response.send_message(f"❌ Member `{name}` not found.", ephemeral=True)
            return

        member = results[0]
        notes = await self.bot.db.get_notes(system['id'], member['id'])

        if not notes:
            await interaction.response.send_message(
                f"No notes found for **{get_member_display(member)}**.", ephemeral=True
            )
            return

        from utils.helpers import parse_color
        embed = discord.Embed(
            title=f"📝 Notes for {get_member_display(member)}",
            color=parse_color(member['color'])
        )
        for n in notes[-10:]:  # Most recent 10
            embed.add_field(
                name=n['created_at'][:10],
                value=n['content'][:500],
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # -------------------------------------------------------------------------
    # GROUP COMMANDS
    # -------------------------------------------------------------------------

    @group_group.command(name="create", description="Create a member group/subsystem")
    @app_commands.describe(name="Group name", description="What this group represents", color="Hex color")
    async def group_create(self, interaction: discord.Interaction,
                           name: str, description: str = None, color: str = None):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return
        kwargs = {}
        if description: kwargs['description'] = description
        if color: kwargs['color'] = color
        gid = await self.bot.db.create_group(system['id'], name, **kwargs)
        await interaction.response.send_message(f"✅ Group **{name}** created! (ID: `{gid}`)")

    @group_group.command(name="add-member", description="Add a member to a group")
    @app_commands.describe(group_name="Group name", member_name="Member to add")
    async def group_add_member(self, interaction: discord.Interaction, group_name: str, member_name: str):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        group = await self.bot.db.get_group_by_name(system['id'], group_name)
        if not group:
            await interaction.response.send_message(f"❌ Group `{group_name}` not found.", ephemeral=True)
            return

        results = await self.bot.db.search_member(system['id'], member_name)
        if not results:
            await interaction.response.send_message(f"❌ Member `{member_name}` not found.", ephemeral=True)
            return

        await self.bot.db.add_member_to_group(group['id'], results[0]['id'])
        await interaction.response.send_message(
            f"✅ **{get_member_display(results[0])}** added to group **{group['name']}**."
        )

    @group_group.command(name="list", description="List all groups in your system")
    async def group_list(self, interaction: discord.Interaction):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        groups = await self.bot.db.get_groups(system['id'])
        if not groups:
            await interaction.response.send_message("No groups yet! Use `/group create` to make one.", ephemeral=True)
            return

        from utils.helpers import parse_color
        embed = discord.Embed(
            title=f"🗂️ {system['system_name']} — Groups",
            color=parse_color(system['color'])
        )
        for g in groups:
            members = await self.bot.db.get_group_members(g['id'])
            names = ', '.join(get_member_display(m) for m in members) if members else '*Empty*'
            embed.add_field(
                name=f"**{g['name']}**",
                value=f"{g['description'] or ''}\nMembers: {names}",
                inline=False
            )
        await interaction.response.send_message(embed=embed)

    @group_group.command(name="delete", description="Delete a group (does not delete members)")
    @app_commands.describe(name="Group name to delete")
    async def group_delete(self, interaction: discord.Interaction, name: str):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        group = await self.bot.db.get_group_by_name(system['id'], name)
        if not group:
            await interaction.response.send_message(f"❌ Group `{name}` not found.", ephemeral=True)
            return

        await self.bot.db.delete_group(group['id'])
        await interaction.response.send_message(f"✅ Group **{name}** deleted.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(MemberCog(bot))
