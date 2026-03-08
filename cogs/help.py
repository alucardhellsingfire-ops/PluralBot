"""
Help cog — comprehensive help command.
"""

import discord
from discord import app_commands
from discord.ext import commands

HELP_PAGES = {
    "overview": {
        "title": "💜 PluralCord — Help",
        "description": (
            "PluralCord is a full-featured system management bot for plural systems.\n\n"
            "**Quick Start:**\n"
            "1. `/system create` — Register your system\n"
            "2. `/member add` — Add your headmates\n"
            "3. `/front set` — Log who's fronting\n"
            "4. `/proxy set` — Set up message proxying"
        ),
        "color": 0x5865F2,
        "fields": [("📦 Categories", "🌟 **System** — Identity & settings\n👥 **Members** — Manage headmates/alters\n✨ **Fronting** — Track switches & analytics\n📓 **Journal** — Private or shared entries\n📊 **Polls** — Per-member voting\n🏷️ **Proxying** — Send messages as members\n💜 **Friends** — Connect with other systems", False)]
    },
    "system": {"title": "🌟 System Commands", "description": "Manage your plural system's core identity.", "color": 0x57F287, "fields": [
        ("/system create `<name>`", "Register your system", True), ("/system view", "View your system profile", True),
        ("/system edit", "Edit name, tag, description, color, avatar, privacy", True), ("/system delete", "⚠️ Delete all system data", True),
        ("/system set-channel `<#channel>`", "Set front notification channel", True), ("/system export", "Download all data as JSON", True),
    ]},
    "members": {"title": "👥 Member Commands", "description": "Manage your headmates and alters.", "color": 0xEB459E, "fields": [
        ("/member add `<name>`", "Add a new member", True), ("/member view `<name>`", "View a member's profile", True),
        ("/member edit `<name>`", "Edit a member's details", True), ("/member list", "List all members", True),
        ("/member delete `<name>`", "Remove a member", True), ("/member archive `<name>`", "Hide without deleting", True),
        ("/member note `<name>` `<note>`", "Add a note", True), ("/member notes `<name>`", "View member notes", True),
        ("/group create `<name>`", "Create a group/subsystem", True), ("/group add-member", "Add member to group", True),
        ("/group list", "List all groups", True), ("/group delete `<name>`", "Delete a group", True),
    ]},
    "fronting": {"title": "✨ Fronting Commands", "description": "Log switches, track history, view analytics.", "color": 0xFEE75C, "fields": [
        ("/front set", "Pick who's fronting from a dropdown (clears others)", True),
        ("/front add", "Add to co-front via dropdown", True), ("/front remove", "Remove one from co-front via dropdown", True),
        ("/front clear", "Clear the entire front", True), ("/front view", "See who's fronting now", True),
        ("/front history", "View switch history", True), ("/front stats", "Analytics with percentage bars", True),
    ]},
    "journal": {"title": "📓 Journal Commands", "description": "Write private or shared journal entries.", "color": 0xED4245, "fields": [
        ("/journal write", "Open a form to write an entry", True), ("/journal list", "List entries", True),
        ("/journal view `<id>`", "Read an entry", True), ("/journal delete `<id>`", "Delete an entry", True),
        ("/journal search `<query>`", "Search by keyword or tag", True),
    ]},
    "polls": {"title": "📊 Poll Commands", "description": "Create polls where each member votes independently.", "color": 0x5865F2, "fields": [
        ("/poll create `<question>` `<options>`", "Create a poll (2–5 options)", True),
        ("/poll results `<id>`", "View results", True), ("/poll close `<id>`", "Close a poll", True), ("/poll list", "List active polls", True),
    ]},
    "proxying": {"title": "🏷️ Proxy Commands", "description": "Send messages as your members.\n**Example:** If Alex has prefix `A:`, typing `A: Hello!` sends as Alex.\n\n⚠️ Requires **Manage Webhooks** permission.", "color": 0x57F287, "fields": [
        ("/proxy set `<member>` `[prefix]` `[suffix]`", "Set proxy tags", True), ("/proxy clear `<member>`", "Remove proxy tags", True),
        ("/proxy list", "List all proxy configs", True), ("/proxy test `<member>`", "Test setup and check permissions", True),
    ]},
    "friends": {"title": "💜 Friends Commands", "description": "Connect with other plural systems.", "color": 0xEB459E, "fields": [
        ("/friends add `@user`", "Send a friend request", True), ("/friends accept `@user`", "Accept a request", True),
        ("/friends pending", "View incoming requests", True), ("/friends list", "See your friends list", True),
        ("/friends front `@user`", "See who a friend has fronting", True), ("/friends remove `@user`", "Unfriend a system", True),
    ]},
}


class HelpSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Overview", value="overview", emoji="💜"),
            discord.SelectOption(label="System", value="system", emoji="🌟"),
            discord.SelectOption(label="Members", value="members", emoji="👥"),
            discord.SelectOption(label="Fronting", value="fronting", emoji="✨"),
            discord.SelectOption(label="Journal", value="journal", emoji="📓"),
            discord.SelectOption(label="Polls", value="polls", emoji="📊"),
            discord.SelectOption(label="Proxying", value="proxying", emoji="🏷️"),
            discord.SelectOption(label="Friends", value="friends", emoji="💜"),
        ]
        super().__init__(placeholder="📖 Choose a category...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        page = HELP_PAGES.get(self.values[0])
        if not page:
            return
        embed = discord.Embed(title=page["title"], description=page.get("description", ""), color=discord.Color(page["color"]))
        for f in page.get("fields", []):
            embed.add_field(name=f[0], value=f[1], inline=f[2])
        embed.set_footer(text="PluralCord — Built with 💜 for the plural community")
        await interaction.edit_original_response(embed=embed)


class HelpCog(commands.Cog, name="Help"):

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="View all PluralCord commands and features")
    async def help_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        page = HELP_PAGES["overview"]
        embed = discord.Embed(title=page["title"], description=page["description"], color=discord.Color(page["color"]))
        for f in page.get("fields", []):
            embed.add_field(name=f[0], value=f[1], inline=f[2])
        embed.set_footer(text="PluralCord — Built with 💜 for the plural community")
        view = discord.ui.View(timeout=120)
        view.add_item(HelpSelect())
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="about", description="About PluralCord")
    async def about_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(
            title="💜 About PluralCord",
            description=(
                "PluralCord is a free, open-source Discord bot built for plural systems.\n\n"
                "Built as a community resource in response to Simply Plural shutting down.\n\n"
                "**Features:** System & member profiles • Front tracking with analytics • "
                "Message proxying • Private journaling • Per-member polls • "
                "Member groups • Friends system • Full data export\n\n"
                "**Privacy:** All data stored locally per server. Nothing shared publicly unless you choose to.\n\n"
                "Built with 💜 for the plural community."
            ),
            color=discord.Color(0x5865F2)
        )
        embed.set_footer(text="Use /help to explore all commands")
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(HelpCog(bot))
