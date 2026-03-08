"""
Friends cog — add other systems as friends to see their current front.
"""

import discord
from discord import app_commands
from discord.ext import commands
from utils.helpers import require_system, front_embed, parse_color


class FriendsCog(commands.Cog, name="Friends"):

    def __init__(self, bot):
        self.bot = bot

    friends_group = app_commands.Group(name="friends", description="Manage system friends")

    @friends_group.command(name="add", description="Send a friend request to another system user")
    @app_commands.describe(user="The Discord user whose system you want to friend")
    async def friends_add(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer()
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        if user.id == interaction.user.id:
            await interaction.followup.send("❌ You can't friend yourself!", ephemeral=True)
            return

        their_system = await self.bot.db.get_system(str(user.id), str(interaction.guild_id))
        if not their_system:
            await interaction.followup.send(f"❌ {user.display_name} doesn't have a system registered in this server.", ephemeral=True)
            return

        success = await self.bot.db.send_friend_request(system['id'], their_system['id'])
        if not success:
            await interaction.followup.send("❌ You've already sent a request or are already friends.", ephemeral=True)
            return

        await interaction.followup.send(
            f"✅ Friend request sent to **{their_system['system_name']}** ({user.mention})!\n"
            f"They can accept with `/friends accept`."
        )
        try:
            embed = discord.Embed(
                title="💜 Friend Request",
                description=f"**{system['system_name']}** ({interaction.user.mention}) sent you a system friend request!\n\nUse `/friends accept @{interaction.user.display_name}` to accept.",
                color=discord.Color(0x5865F2)
            )
            await user.send(embed=embed)
        except discord.Forbidden:
            pass

    @friends_group.command(name="accept", description="Accept a friend request from another system")
    @app_commands.describe(user="The user whose request you want to accept")
    async def friends_accept(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer()
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        their_system = await self.bot.db.get_system(str(user.id), str(interaction.guild_id))
        if not their_system:
            await interaction.followup.send(f"❌ {user.display_name} doesn't have a system here.", ephemeral=True)
            return

        pending = await self.bot.db.get_pending_requests(system['id'])
        req = next((r for r in pending if r['system_id'] == their_system['id']), None)
        if not req:
            await interaction.followup.send(f"❌ No pending friend request from {user.display_name}.", ephemeral=True)
            return

        await self.bot.db.accept_friend_request(system['id'], their_system['id'])
        await interaction.followup.send(
            f"✅ You're now friends with **{their_system['system_name']}**! 💜\n"
            f"Use `/friends front @{user.display_name}` to see who they have fronting."
        )

    @friends_group.command(name="pending", description="View incoming friend requests")
    async def friends_pending(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        pending = await self.bot.db.get_pending_requests(system['id'])
        if not pending:
            await interaction.followup.send("No pending friend requests.", ephemeral=True)
            return

        embed = discord.Embed(title="📬 Pending Friend Requests", color=discord.Color(0x5865F2))
        for req in pending:
            embed.add_field(name=req['system_name'], value=f"From <@{req['user_id']}> • Sent {req['created_at'][:10]}", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @friends_group.command(name="list", description="View your system's friends list")
    async def friends_list(self, interaction: discord.Interaction):
        await interaction.response.defer()
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        friends = await self.bot.db.get_friends(system['id'])
        if not friends:
            await interaction.followup.send("No friends yet! Use `/friends add` to connect with other systems.")
            return

        embed = discord.Embed(title=f"💜 {system['system_name']} — Friends", color=parse_color(system['color']))
        for f in friends:
            embed.add_field(name=f['system_name'], value=f"<@{f['user_id']}> • Since {f['created_at'][:10]}", inline=False)
        await interaction.followup.send(embed=embed)

    @friends_group.command(name="front", description="See who a friend system has fronting")
    @app_commands.describe(user="The friend system's Discord user")
    async def friends_front(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer()
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        their_system = await self.bot.db.get_system(str(user.id), str(interaction.guild_id))
        if not their_system:
            await interaction.followup.send(f"❌ {user.display_name} doesn't have a registered system here.", ephemeral=True)
            return

        friends = await self.bot.db.get_friends(system['id'])
        if not any(f['friend_system_id'] == their_system['id'] for f in friends):
            await interaction.followup.send(f"❌ You're not friends with **{their_system['system_name']}** yet.", ephemeral=True)
            return

        if their_system['privacy_default'] == 'private':
            await interaction.followup.send(f"🔒 **{their_system['system_name']}** has their system set to private.", ephemeral=True)
            return

        fronters = await self.bot.db.get_current_front(their_system['id'])
        embed = front_embed(fronters, their_system['system_name'])
        await interaction.followup.send(embed=embed)

    @friends_group.command(name="remove", description="Remove a system from your friends list")
    @app_commands.describe(user="The user to unfriend")
    async def friends_remove(self, interaction: discord.Interaction, user: discord.Member):
        await interaction.response.defer(ephemeral=True)
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        their_system = await self.bot.db.get_system(str(user.id), str(interaction.guild_id))
        if not their_system:
            await interaction.followup.send(f"❌ {user.display_name} doesn't have a system here.", ephemeral=True)
            return

        await self.bot.db.remove_friend(system['id'], their_system['id'])
        await interaction.followup.send(f"✅ Removed **{their_system['system_name']}** from your friends list.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(FriendsCog(bot))
