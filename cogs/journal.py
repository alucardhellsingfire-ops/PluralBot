"""
Journal cog — write and manage journal entries, private or shared.
Commands: /journal write, list, view, edit, delete, search
"""

import discord
from discord import app_commands
from discord.ext import commands
import json
from utils.helpers import require_system, parse_color, paginate, get_member_display


class JournalModal(discord.ui.Modal, title="Journal Entry"):
    entry_title = discord.ui.TextInput(
        label="Title (optional)",
        placeholder="Give this entry a title...",
        required=False,
        max_length=100
    )
    content = discord.ui.TextInput(
        label="Content",
        placeholder="Write your journal entry here...",
        style=discord.TextStyle.paragraph,
        max_length=2000,
        required=True
    )
    tags = discord.ui.TextInput(
        label="Tags (comma-separated, optional)",
        placeholder="e.g. happy, therapy, trauma",
        required=False,
        max_length=200
    )

    def __init__(self, db, system, member=None, is_private=True):
        super().__init__()
        self.db = db
        self.system = system
        self.member = member
        self.is_private = is_private

    async def on_submit(self, interaction: discord.Interaction):
        tags = [t.strip() for t in self.tags.value.split(',') if t.strip()] if self.tags.value else []

        kwargs = {
            'is_private': 1 if self.is_private else 0,
            'tags': json.dumps(tags)
        }
        if self.entry_title.value:
            kwargs['title'] = self.entry_title.value
        if self.member:
            kwargs['member_id'] = self.member['id']

        entry_id = await self.db.create_journal_entry(
            self.system['id'],
            self.content.value,
            **kwargs
        )

        color = parse_color(self.system['color'])
        embed = discord.Embed(
            title=f"📓 {self.entry_title.value or 'Journal Entry'} #{entry_id}",
            description=self.content.value[:500] + ('...' if len(self.content.value) > 500 else ''),
            color=color
        )
        if self.member:
            embed.set_author(name=get_member_display(self.member))
        if tags:
            embed.add_field(name="Tags", value=', '.join(f'`{t}`' for t in tags))
        embed.set_footer(text=f"{'🔒 Private' if self.is_private else '🌐 Shared'} • ID: {entry_id}")

        await interaction.response.send_message(embed=embed, ephemeral=self.is_private)


class JournalCog(commands.Cog, name="Journal"):
    """Write and manage journal entries for your system."""

    def __init__(self, bot):
        self.bot = bot

    journal_group = app_commands.Group(name="journal", description="System journal")

    @journal_group.command(name="write", description="Write a new journal entry")
    @app_commands.describe(
        member="Which member is writing (optional)",
        private="Keep this entry private (default: True)"
    )
    async def journal_write(self, interaction: discord.Interaction,
                            member: str = None, private: bool = True):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        member_row = None
        if member:
            results = await self.bot.db.search_member(system['id'], member)
            if not results:
                await interaction.response.send_message(f"❌ Member `{member}` not found.", ephemeral=True)
                return
            member_row = results[0]

        modal = JournalModal(self.bot.db, system, member_row, is_private=private)
        await interaction.response.send_modal(modal)

    @journal_group.command(name="list", description="List journal entries")
    @app_commands.describe(member="Filter by member", page="Page number", private="Show private entries")
    async def journal_list(self, interaction: discord.Interaction,
                           member: str = None, page: int = 1, private: bool = True):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        member_id = None
        if member:
            results = await self.bot.db.search_member(system['id'], member)
            if not results:
                await interaction.response.send_message(f"❌ Member `{member}` not found.", ephemeral=True)
                return
            member_id = results[0]['id']

        entries = await self.bot.db.get_journal_entries(system['id'], member_id, limit=100)
        if not entries:
            await interaction.response.send_message("No journal entries yet. Use `/journal write` to start.", ephemeral=True)
            return

        items, current_page, total_pages = paginate(list(entries), page, 10)
        color = parse_color(system['color'])
        embed = discord.Embed(
            title=f"📓 {system['system_name']} — Journal",
            color=color
        )

        for e in items:
            title = e['title'] or f"Entry #{e['id']}"
            preview = e['content'][:80] + ('...' if len(e['content']) > 80 else '')
            date = e['created_at'][:10]
            lock = '🔒' if e['is_private'] else '🌐'
            embed.add_field(
                name=f"{lock} {title} — {date}",
                value=f"*{preview}*\nID: `{e['id']}`",
                inline=False
            )

        embed.set_footer(text=f"Page {current_page}/{total_pages} • {len(entries)} total")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @journal_group.command(name="view", description="View a specific journal entry by ID")
    @app_commands.describe(entry_id="Journal entry ID")
    async def journal_view(self, interaction: discord.Interaction, entry_id: int):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        entry = await self.bot.db.get_journal_entry(entry_id)
        if not entry or entry['system_id'] != system['id']:
            await interaction.response.send_message("❌ Entry not found.", ephemeral=True)
            return

        color = parse_color(system['color'])
        embed = discord.Embed(
            title=entry['title'] or f"Entry #{entry['id']}",
            description=entry['content'],
            color=color
        )

        if entry['member_id']:
            member = await self.bot.db.get_member(entry['member_id'])
            if member:
                embed.set_author(name=get_member_display(member))

        tags = json.loads(entry['tags'] or '[]')
        if tags:
            embed.add_field(name="Tags", value=', '.join(f'`{t}`' for t in tags))

        embed.set_footer(text=f"{'🔒 Private' if entry['is_private'] else '🌐 Shared'} • Written {entry['created_at'][:10]} • Edited {entry['updated_at'][:10]}")
        await interaction.response.send_message(embed=embed, ephemeral=bool(entry['is_private']))

    @journal_group.command(name="delete", description="Delete a journal entry")
    @app_commands.describe(entry_id="Journal entry ID to delete")
    async def journal_delete(self, interaction: discord.Interaction, entry_id: int):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        entry = await self.bot.db.get_journal_entry(entry_id)
        if not entry or entry['system_id'] != system['id']:
            await interaction.response.send_message("❌ Entry not found.", ephemeral=True)
            return

        await self.bot.db.delete_journal_entry(entry_id)
        await interaction.response.send_message(f"✅ Entry #{entry_id} deleted.", ephemeral=True)

    @journal_group.command(name="search", description="Search journal entries by tag or keyword")
    @app_commands.describe(query="Keyword or tag to search for")
    async def journal_search(self, interaction: discord.Interaction, query: str):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        all_entries = await self.bot.db.get_journal_entries(system['id'], limit=1000)
        q = query.lower()
        matches = [
            e for e in all_entries
            if q in (e['content'] or '').lower()
            or q in (e['title'] or '').lower()
            or q in (e['tags'] or '').lower()
        ]

        if not matches:
            await interaction.response.send_message(f"No entries found matching `{query}`.", ephemeral=True)
            return

        color = parse_color(system['color'])
        embed = discord.Embed(
            title=f"🔍 Search: '{query}'",
            color=color
        )
        for e in matches[:8]:
            title = e['title'] or f"Entry #{e['id']}"
            preview = e['content'][:60] + ('...' if len(e['content']) > 60 else '')
            embed.add_field(name=f"{title} ({e['created_at'][:10]})",
                            value=f"*{preview}* | ID: `{e['id']}`", inline=False)
        embed.set_footer(text=f"{len(matches)} result(s) found")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(JournalCog(bot))
