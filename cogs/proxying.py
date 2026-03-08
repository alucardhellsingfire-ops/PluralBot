"""
Proxying cog — send messages as your system members using proxy tags.
Uses webhooks to mimic PluralKit-style proxying.
E.g. if a member has prefix "A:" then typing "A: Hello!" sends as that member.
"""

import discord
from discord.ext import commands
import re


class ProxyingCog(commands.Cog, name="Proxying"):
    """Send messages as your system members using proxy tags."""

    def __init__(self, bot):
        self.bot = bot
        self._webhook_cache: dict = {}  # channel_id -> webhook

    async def get_or_create_webhook(self, channel: discord.TextChannel) -> discord.Webhook:
        """Get or create a webhook for the given channel."""
        if channel.id in self._webhook_cache:
            return self._webhook_cache[channel.id]

        # Look for existing PluralCord webhook
        try:
            webhooks = await channel.webhooks()
            for wh in webhooks:
                if wh.name == "PluralCord":
                    self._webhook_cache[channel.id] = wh
                    return wh
            # Create one
            wh = await channel.create_webhook(name="PluralCord")
            self._webhook_cache[channel.id] = wh
            return wh
        except discord.Forbidden:
            return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Intercept messages and proxy them if proxy tags match."""
        # Ignore bots, DMs, and commands
        if message.author.bot:
            return
        if not message.guild:
            return
        if message.content.startswith(('/', 'pc!')):
            return

        db = self.bot.db
        system = await db.get_system(str(message.author.id), str(message.guild.id))
        if not system:
            return

        content = message.content
        member, proxied_content = await db.get_member_by_proxy(system['id'], content)

        if not member or not proxied_content:
            return

        # Get webhook
        if not isinstance(message.channel, discord.TextChannel):
            return

        webhook = await self.get_or_create_webhook(message.channel)
        if not webhook:
            return

        # Build display name
        display = member['display_name'] or member['name']
        system_tag = system.get('system_tag') or ''
        username = f"{display} {system_tag}".strip()
        if len(username) > 80:
            username = username[:80]

        avatar = member['avatar_url'] or None

        # Handle attachments
        files = []
        for att in message.attachments:
            try:
                f = await att.to_file()
                files.append(f)
            except Exception:
                pass

        # Handle embeds (e.g. linked embeds) — pass through
        try:
            await message.delete()
        except discord.Forbidden:
            pass

        try:
            await webhook.send(
                content=proxied_content or '\u200b',
                username=username,
                avatar_url=avatar,
                files=files,
                allowed_mentions=discord.AllowedMentions.all()
            )
        except discord.HTTPException:
            pass

        # Log this as a front if not already fronting
        # (optional quality of life — don't auto-set front to avoid noise)

    proxy_group = discord.app_commands.Group(name="proxy", description="Manage proxy tags for members")

    @proxy_group.command(name="set", description="Set proxy tags for a member")
    @discord.app_commands.describe(
        member="Member name",
        prefix="Prefix (e.g. 'A:' or 'Alice:')",
        suffix="Suffix (e.g. '-A' or '-Alice')"
    )
    async def proxy_set(self, interaction: discord.Interaction,
                        member: str, prefix: str = None, suffix: str = None):
        from utils.helpers import require_system, get_member_display
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        if not prefix and not suffix:
            await interaction.response.send_message(
                "❌ You must provide at least a prefix or suffix.", ephemeral=True
            )
            return

        results = await self.bot.db.search_member(system['id'], member)
        if not results:
            await interaction.response.send_message(f"❌ Member `{member}` not found.", ephemeral=True)
            return

        m = results[0]
        updates = {}
        if prefix is not None:
            updates['proxy_prefix'] = prefix
        if suffix is not None:
            updates['proxy_suffix'] = suffix

        await self.bot.db.update_member(m['id'], **updates)

        prefix_disp = prefix or ''
        suffix_disp = suffix or ''
        await interaction.response.send_message(
            f"✅ Proxy for **{get_member_display(m)}** set to: `{prefix_disp}text{suffix_disp}`\n\n"
            f"Make sure I have **Manage Webhooks** permission in the channels where you want to proxy!",
            ephemeral=True
        )

    @proxy_group.command(name="clear", description="Remove proxy tags from a member")
    @discord.app_commands.describe(member="Member name")
    async def proxy_clear(self, interaction: discord.Interaction, member: str):
        from utils.helpers import require_system, get_member_display
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        results = await self.bot.db.search_member(system['id'], member)
        if not results:
            await interaction.response.send_message(f"❌ Member `{member}` not found.", ephemeral=True)
            return

        m = results[0]
        await self.bot.db.update_member(m['id'], proxy_prefix=None, proxy_suffix=None)
        await interaction.response.send_message(
            f"✅ Proxy tags cleared for **{get_member_display(m)}**.",
            ephemeral=True
        )

    @proxy_group.command(name="list", description="List all proxy tags in your system")
    async def proxy_list(self, interaction: discord.Interaction):
        from utils.helpers import require_system, parse_color, get_member_display
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        members = await self.bot.db.get_members(system['id'])
        proxied = [m for m in members if m['proxy_prefix'] or m['proxy_suffix']]

        if not proxied:
            await interaction.response.send_message(
                "No proxy tags set. Use `/proxy set` to configure them.", ephemeral=True
            )
            return

        color = parse_color(system['color'])
        embed = discord.Embed(title=f"🏷️ {system['system_name']} — Proxy Tags", color=color)

        for m in proxied:
            prefix = m['proxy_prefix'] or ''
            suffix = m['proxy_suffix'] or ''
            embed.add_field(
                name=get_member_display(m),
                value=f"`{prefix}text{suffix}`",
                inline=True
            )

        embed.set_footer(text="Make sure the bot has Manage Webhooks permission!")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @proxy_group.command(name="test", description="Test if your proxy tags are set up correctly")
    @discord.app_commands.describe(member="Member name to test proxy for")
    async def proxy_test(self, interaction: discord.Interaction, member: str):
        from utils.helpers import require_system, get_member_display
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        results = await self.bot.db.search_member(system['id'], member)
        if not results:
            await interaction.response.send_message(f"❌ Member `{member}` not found.", ephemeral=True)
            return

        m = results[0]
        prefix = m['proxy_prefix'] or ''
        suffix = m['proxy_suffix'] or ''

        if not prefix and not suffix:
            await interaction.response.send_message(
                f"**{get_member_display(m)}** has no proxy tags set. Use `/proxy set` to add some.",
                ephemeral=True
            )
            return

        # Check webhook perms
        if isinstance(interaction.channel, discord.TextChannel):
            perms = interaction.channel.permissions_for(interaction.guild.me)
            can_webhook = perms.manage_webhooks
        else:
            can_webhook = False

        status = "✅ Webhook permission: **granted**" if can_webhook else "❌ Webhook permission: **missing** — please give the bot Manage Webhooks in this channel!"

        await interaction.response.send_message(
            f"**{get_member_display(m)}** proxy: `{prefix}text{suffix}`\n\n"
            f"To proxy as them, type: `{prefix}Hello, world!{suffix}`\n\n"
            f"{status}",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(ProxyingCog(bot))
