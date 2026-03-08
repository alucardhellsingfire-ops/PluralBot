"""
Proxying cog — send messages as system members using proxy tags via webhooks.
"""

import discord
from discord.ext import commands
from discord import app_commands


class ProxyingCog(commands.Cog, name="Proxying"):

    def __init__(self, bot):
        self.bot = bot
        self._webhook_cache = {}

    async def get_or_create_webhook(self, channel):
        if channel.id in self._webhook_cache:
            return self._webhook_cache[channel.id]
        try:
            webhooks = await channel.webhooks()
            for wh in webhooks:
                if wh.name == "PluralCord":
                    self._webhook_cache[channel.id] = wh
                    return wh
            wh = await channel.create_webhook(name="PluralCord")
            self._webhook_cache[channel.id] = wh
            return wh
        except discord.Forbidden:
            return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.content.startswith(('/', 'pc!')):
            return

        db = self.bot.db
        system = await db.get_system(str(message.author.id), str(message.guild.id))
        if not system:
            return

        member, proxied_content = await db.get_member_by_proxy(system['id'], message.content)
        if not member or not proxied_content:
            return

        if not isinstance(message.channel, discord.TextChannel):
            return

        webhook = await self.get_or_create_webhook(message.channel)
        if not webhook:
            return

        display = member['display_name'] or member['name']
        system_tag = system.get('system_tag') or ''
        username = f"{display} {system_tag}".strip()[:80]
        avatar = member['avatar_url'] or None

        files = []
        for att in message.attachments:
            try:
                files.append(await att.to_file())
            except Exception:
                pass

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

    proxy_group = app_commands.Group(name="proxy", description="Manage proxy tags for members")

    @proxy_group.command(name="set", description="Set proxy tags for a member")
    @app_commands.describe(member="Member name", prefix="Prefix (e.g. 'A:')", suffix="Suffix (e.g. '-A')")
    async def proxy_set(self, interaction: discord.Interaction, member: str, prefix: str = None, suffix: str = None):
        await interaction.response.defer(ephemeral=True)
        from utils.helpers import require_system, get_member_display
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        if not prefix and not suffix:
            await interaction.followup.send("❌ You must provide at least a prefix or suffix.", ephemeral=True)
            return

        results = await self.bot.db.search_member(system['id'], member)
        if not results:
            await interaction.followup.send(f"❌ Member `{member}` not found.", ephemeral=True)
            return

        m = results[0]
        updates = {}
        if prefix is not None: updates['proxy_prefix'] = prefix
        if suffix is not None: updates['proxy_suffix'] = suffix
        await self.bot.db.update_member(m['id'], **updates)

        prefix_d = prefix or ''
        suffix_d = suffix or ''
        await interaction.followup.send(
            f"✅ Proxy for **{get_member_display(m)}** set to: `{prefix_d}text{suffix_d}`\n\n"
            f"Make sure I have **Manage Webhooks** permission in channels where you want to proxy!",
            ephemeral=True
        )

    @proxy_group.command(name="clear", description="Remove proxy tags from a member")
    @app_commands.describe(member="Member name")
    async def proxy_clear(self, interaction: discord.Interaction, member: str):
        await interaction.response.defer(ephemeral=True)
        from utils.helpers import require_system, get_member_display
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        results = await self.bot.db.search_member(system['id'], member)
        if not results:
            await interaction.followup.send(f"❌ Member `{member}` not found.", ephemeral=True)
            return

        await self.bot.db.update_member(results[0]['id'], proxy_prefix=None, proxy_suffix=None)
        await interaction.followup.send(f"✅ Proxy tags cleared for **{get_member_display(results[0])}**.", ephemeral=True)

    @proxy_group.command(name="list", description="List all proxy tags in your system")
    async def proxy_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        from utils.helpers import require_system, parse_color, get_member_display
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        members = await self.bot.db.get_members(system['id'])
        proxied = [m for m in members if m['proxy_prefix'] or m['proxy_suffix']]

        if not proxied:
            await interaction.followup.send("No proxy tags set. Use `/proxy set` to configure them.", ephemeral=True)
            return

        embed = discord.Embed(title=f"🏷️ {system['system_name']} — Proxy Tags", color=parse_color(system['color']))
        for m in proxied:
            prefix = m['proxy_prefix'] or ''
            suffix = m['proxy_suffix'] or ''
            embed.add_field(name=get_member_display(m), value=f"`{prefix}text{suffix}`", inline=True)
        embed.set_footer(text="Make sure the bot has Manage Webhooks permission!")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @proxy_group.command(name="test", description="Test if your proxy tags are set up correctly")
    @app_commands.describe(member="Member name to test proxy for")
    async def proxy_test(self, interaction: discord.Interaction, member: str):
        await interaction.response.defer(ephemeral=True)
        from utils.helpers import require_system, get_member_display
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        results = await self.bot.db.search_member(system['id'], member)
        if not results:
            await interaction.followup.send(f"❌ Member `{member}` not found.", ephemeral=True)
            return

        m = results[0]
        prefix = m['proxy_prefix'] or ''
        suffix = m['proxy_suffix'] or ''

        if not prefix and not suffix:
            await interaction.followup.send(f"**{get_member_display(m)}** has no proxy tags set. Use `/proxy set` to add some.", ephemeral=True)
            return

        can_webhook = False
        if isinstance(interaction.channel, discord.TextChannel):
            can_webhook = interaction.channel.permissions_for(interaction.guild.me).manage_webhooks

        status = "✅ Webhook permission: **granted**" if can_webhook else "❌ Webhook permission: **missing** — please give the bot Manage Webhooks in this channel!"
        await interaction.followup.send(
            f"**{get_member_display(m)}** proxy: `{prefix}text{suffix}`\n\n"
            f"To proxy, type: `{prefix}Hello, world!{suffix}`\n\n{status}",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(ProxyingCog(bot))
