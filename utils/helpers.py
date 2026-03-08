"""
Shared utility helpers for PluralCord cogs.
"""

import discord
import datetime
from typing import Optional


def parse_color(color_str: str) -> Optional[discord.Color]:
    """Parse a hex color string into a discord.Color."""
    if not color_str:
        return discord.Color(0x7289DA)
    color_str = color_str.strip().lstrip('#')
    try:
        return discord.Color(int(color_str, 16))
    except ValueError:
        return discord.Color(0x7289DA)


def member_embed(member_row, system_row=None) -> discord.Embed:
    """Build a rich embed for a system member."""
    color = parse_color(member_row['color'])
    name = member_row['display_name'] or member_row['name']
    embed = discord.Embed(title=f"💜 {name}", color=color)

    if member_row['avatar_url']:
        embed.set_thumbnail(url=member_row['avatar_url'])

    if member_row['pronouns']:
        embed.add_field(name="Pronouns", value=member_row['pronouns'], inline=True)
    if member_row['role']:
        embed.add_field(name="Role", value=member_row['role'], inline=True)
    if member_row['birthday']:
        embed.add_field(name="Birthday", value=member_row['birthday'], inline=True)
    if member_row['description']:
        embed.add_field(name="About", value=member_row['description'][:1024], inline=False)

    # Proxy tags
    prefix = member_row['proxy_prefix'] or ''
    suffix = member_row['proxy_suffix'] or ''
    if prefix or suffix:
        embed.add_field(name="Proxy Tags", value=f"`{prefix}text{suffix}`", inline=True)

    if system_row:
        embed.set_footer(text=f"System: {system_row['system_name']}")
    return embed


def system_embed(system_row, member_count: int = 0) -> discord.Embed:
    """Build a rich embed for a system."""
    color = parse_color(system_row['color'])
    embed = discord.Embed(
        title=f"🌟 {system_row['system_name']}",
        description=system_row['description'] or '*No description set.*',
        color=color
    )
    if system_row['avatar_url']:
        embed.set_thumbnail(url=system_row['avatar_url'])
    if system_row['system_tag']:
        embed.add_field(name="System Tag", value=system_row['system_tag'], inline=True)
    embed.add_field(name="Members", value=str(member_count), inline=True)
    embed.add_field(name="Privacy", value=system_row['privacy_default'].capitalize(), inline=True)
    embed.set_footer(text=f"System ID: {system_row['id']} • Created {system_row['created_at'][:10]}")
    return embed


def format_duration(minutes: float) -> str:
    """Format a duration in minutes into a human-readable string."""
    if minutes is None:
        return "0m"
    minutes = int(minutes)
    days = minutes // (60 * 24)
    hours = (minutes % (60 * 24)) // 60
    mins = minutes % 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins or not parts:
        parts.append(f"{mins}m")
    return ' '.join(parts)


def get_member_display(member_row) -> str:
    return member_row['display_name'] or member_row['name']


def paginate(items: list, page: int, per_page: int = 10):
    """Return a page of items and total pages."""
    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    return items[start:end], page, total_pages


async def require_system(interaction: discord.Interaction, db) -> Optional[object]:
    """Check if a user has a system; send error embed if not."""
    system = await db.get_system(str(interaction.user.id), str(interaction.guild_id))
    if not system:
        embed = discord.Embed(
            title="No System Found",
            description="You don't have a system registered yet!\nUse `/system create` to get started. 💜",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return None
    return system


def front_embed(fronters: list, system_name: str) -> discord.Embed:
    """Build embed showing who's currently fronting."""
    if not fronters:
        embed = discord.Embed(
            title=f"🌙 {system_name} — Currently Fronting",
            description="*Nobody is currently fronting.*",
            color=discord.Color(0x5865F2)
        )
        return embed

    color = parse_color(fronters[0]['color'])
    embed = discord.Embed(
        title=f"✨ {system_name} — Currently Fronting",
        color=color
    )
    for f in fronters:
        name = f['display_name'] or f['name']
        pronouns = f['pronouns']
        since = f['since'][:16].replace('T', ' ') if 'T' in str(since := f['since']) else str(since)[:16]
        value = []
        if pronouns:
            value.append(f"Pronouns: {pronouns}")
        value.append(f"Since: {since} UTC")
        if f.get('note'):
            value.append(f"Note: {f['note']}")
        embed.add_field(name=f"💜 {name}", value='\n'.join(value), inline=False)
        if f['avatar_url'] and len(fronters) == 1:
            embed.set_thumbnail(url=f['avatar_url'])
    return embed
