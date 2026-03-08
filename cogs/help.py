"""
Help cog — comprehensive help command with all features.
"""

import discord
from discord import app_commands
from discord.ext import commands


HELP_PAGES = {
    "overview": {
        "title": "💜 PluralCord — Help",
        "description": (
            "PluralCord is a full-featured system management bot for plural systems, "
            "built as a Discord-native replacement for Simply Plural.\n\n"
            "Use the dropdown below to explore all features.\n\n"
            "**Quick Start:**\n"
            "1. `/system create` — Register your system\n"
            "2. `/member add` — Add your headmates\n"
            "3. `/front set` — Log who's fronting\n"
            "4. `/proxy set` — Set up message proxying"
        ),
        "color": 0x5865F2,
        "fields": [
            ("📦 Categories", (
                "🌟 **System** — Your system's identity & settings\n"
                "👥 **Members** — Manage headmates/alters\n"
                "✨ **Fronting** — Track switches & view analytics\n"
                "📓 **Journal** — Private or shared journal entries\n"
                "📊 **Polls** — Per-member voting system\n"
                "🏷️ **Proxying** — Send messages as members\n"
                "💜 **Friends** — Connect with other systems\n"
            ), False)
        ]
    },
    "system": {
        "title": "🌟 System Commands",
        "description": "Manage your plural system's core identity.",
        "color": 0x57F287,
        "fields": [
            ("/system create `<name>`", "Register your system with PluralCord", True),
            ("/system view", "View your system's profile card", True),
            ("/system edit", "Edit name, tag, description, color, avatar, privacy", True),
            ("/system delete", "⚠️ Permanently delete all system data", True),
            ("/system set-channel `<#channel>`", "Set where front notifications are posted", True),
            ("/system export", "Download all your data as JSON", True),
        ]
    },
    "members": {
        "title": "👥 Member Commands",
        "description": "Add and manage your system's headmates and alters.",
        "color": 0xEB459E,
        "fields": [
            ("/member add `<name>`", "Add a new member with optional details", True),
            ("/member view `<name>`", "View a member's full profile", True),
            ("/member edit `<name>`", "Edit any field of a member's profile", True),
            ("/member list", "List all members (paginated)", True),
            ("/member delete `<name>`", "Permanently remove a member", True),
            ("/member archive `<name>`", "Hide a member without deleting them", True),
            ("/member note `<name>` `<note>`", "Add a note to a member", True),
            ("/member notes `<name>`", "View all notes for a member", True),
            ("/group create `<name>`", "Create a group/subsystem", True),
            ("/group add-member `<group>` `<member>`", "Add a member to a group", True),
            ("/group list", "List all groups and their members", True),
            ("/group delete `<name>`", "Delete a group (keeps members)", True),
        ]
    },
    "fronting": {
        "title": "✨ Fronting Commands",
        "description": "Log switches, track history, and view analytics.",
        "color": 0xFEE75C,
        "fields": [
            ("/front set `<member>`", "Set who's fronting (clears others)", True),
            ("/front add `<member>`", "Add to current front (co-fronting)", True),
            ("/front remove `<member>`", "Remove one member from co-front", True),
            ("/front clear", "Clear the entire front", True),
            ("/front view", "See who is currently fronting", True),
            ("/front history", "View switch history (paginated, filterable)", True),
            ("/front stats", "Visual analytics — time per member with % bars", True),
        ]
    },
    "journal": {
        "title": "📓 Journal Commands",
        "description": "Write private or shared journal entries, searchable by tag.",
        "color": 0xED4245,
        "fields": [
            ("/journal write", "Opens a form to write a new entry", True),
            ("/journal list", "List entries (filter by member, page)", True),
            ("/journal view `<id>`", "Read a specific entry", True),
            ("/journal delete `<id>`", "Delete an entry", True),
            ("/journal search `<query>`", "Search by keyword or tag", True),
        ]
    },
    "polls": {
        "title": "📊 Poll Commands",
        "description": "Create polls where each system member votes independently.",
        "color": 0x5865F2,
        "fields": [
            ("/poll create `<question>` `<options...>`", "Create a poll (2–5 options)", True),
            ("/poll vote `<id>` `<member>` `<option>`", "Cast a vote for a member", True),
            ("/poll results `<id>`", "View poll results with bar chart", True),
            ("/poll close `<id>`", "Close a poll (no more votes)", True),
            ("/poll list", "List all open polls", True),
        ]
    },
    "proxying": {
        "title": "🏷️ Proxy Commands",
        "description": (
            "Send messages as your system members using proxy tags.\n"
            "**Example:** If Alex has prefix `A:`, typing `A: Hello!` will send as Alex.\n\n"
            "⚠️ Requires **Manage Webhooks** permission in the channel."
        ),
        "color": 0x57F287,
        "fields": [
            ("/proxy set `<member>` `[prefix]` `[suffix]`", "Set proxy tags for a member", True),
            ("/proxy clear `<member>`", "Remove a member's proxy tags", True),
            ("/proxy list", "List all configured proxy tags", True),
            ("/proxy test `<member>`", "Test proxy setup and check permissions", True),
        ]
    },
    "friends": {
        "title": "💜 Friends Commands",
        "description": "Connect with other plural systems and see their front.",
        "color": 0xEB459E,
        "fields": [
            ("/friends add `@user`", "Send a friend request to a system", True),
            ("/friends accept `@user`", "Accept a friend request", True),
            ("/friends pending", "View incoming requests", True),
            ("/friends list", "See your friends list", True),
            ("/friends front `@user`", "See who a friend has fronting", True),
            ("/friends remove `@user`", "Unfriend a system", True),
        ]
    }
}


class HelpSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Overview", value="overview", emoji="💜", description="Quick start & feature overview"),
            discord.SelectOption(label="System", value="system", emoji="🌟", description="System identity & settings"),
            discord.SelectOption(label="Members", value="members", emoji="👥", description="Headmates & alters"),
            discord.SelectOption(label="Fronting", value="fronting", emoji="✨", description="Switches & analytics"),
            discord.SelectOption(label="Journal", value="journal", emoji="📓", description="Private/shared entries"),
            discord.SelectOption(label="Polls", value="polls", emoji="📊", description="Per-member voting"),
            discord.SelectOption(label="Proxying", value="proxying", emoji="🏷️", description="Message proxying"),
            discord.SelectOption(label="Friends", value="friends", emoji="💜", description="Connect with other systems"),
        ]
        super().__init__(placeholder="📖 Choose a category...", options=options)

    async def callback(self, interaction: discord.Interaction):
        page = HELP_PAGES.get(self.values[0])
        if not page:
            return
        embed = discord.Embed(
            title=page["title"],
            description=page.get("description", ""),
            color=discord.Color(page["color"])
        )
        for field_data in page.get("fields", []):
            embed.add_field(name=field_data[0], value=field_data[1], inline=field_data[2])
        embed.set_footer(text="PluralCord — Built with 💜 for the plural community")
        await interaction.response.edit_message(embed=embed)


class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(HelpSelect())


class HelpCog(commands.Cog, name="Help"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="View all PluralCord commands and features")
    async def help_cmd(self, interaction: discord.Interaction):
        page = HELP_PAGES["overview"]
        embed = discord.Embed(
            title=page["title"],
            description=page["description"],
            color=discord.Color(page["color"])
        )
        for field_data in page.get("fields", []):
            embed.add_field(name=field_data[0], value=field_data[1], inline=field_data[2])
        embed.set_footer(text="PluralCord — Built with 💜 for the plural community")
        await interaction.response.send_message(embed=embed, view=HelpView(), ephemeral=True)

    @app_commands.command(name="about", description="About PluralCord")
    async def about_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="💜 About PluralCord",
            description=(
                "PluralCord is a free, open-source Discord bot built for plural systems.\n\n"
                "It was built as a community resource in response to Simply Plural shutting down, "
                "providing similar features natively inside Discord where many plural folks already live.\n\n"
                "**Features:**\n"
                "• System & member profiles with rich embeds\n"
                "• Front tracking with history and analytics\n"
                "• Message proxying (send as your headmates)\n"
                "• Private journaling with tags and search\n"
                "• Per-member polls & voting\n"
                "• Member groups & subsystems\n"
                "• Friend system to view other systems' fronts\n"
                "• Full data export to JSON\n\n"
                "**Privacy:** All data is stored locally per server. Nothing is shared publicly unless you choose to.\n\n"
                "Built with 💜 for the plural community."
            ),
            color=discord.Color(0x5865F2)
        )
        embed.set_footer(text="Use /help to explore all commands")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(HelpCog(bot))
