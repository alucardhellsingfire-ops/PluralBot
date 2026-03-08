"""
Polls cog — create polls that each system member can vote on separately.
"""

import discord
from discord import app_commands
from discord.ext import commands
import json
from utils.helpers import require_system, parse_color, get_member_display


def build_poll_embed(poll, system_name, color):
    options = json.loads(poll['options'])
    votes = json.loads(poll['votes'])
    status = "🟢 Open" if poll['is_open'] else "🔴 Closed"
    embed = discord.Embed(title=f"📊 {poll['question']}", color=color)
    embed.set_author(name=f"{system_name} — System Poll")

    vote_counts = [0] * len(options)
    for opt_idx in votes.values():
        if 0 <= opt_idx < len(options):
            vote_counts[opt_idx] += 1
    total_votes = sum(vote_counts)

    for i, option in enumerate(options):
        count = vote_counts[i]
        pct = (count / total_votes * 100) if total_votes else 0
        bar = '█' * int(pct / 5) + '░' * (20 - int(pct / 5))
        embed.add_field(name=f"{i+1}. {option}", value=f"`{bar}` {count} vote(s) ({pct:.0f}%)", inline=False)

    if votes:
        voter_lines = [f"**{name}** → {options[idx]}" for name, idx in votes.items() if 0 <= idx < len(options)]
        if voter_lines:
            embed.add_field(name="Votes Cast", value='\n'.join(voter_lines[:20]), inline=False)

    embed.set_footer(text=f"{status} • Poll ID: {poll['id']} • {total_votes} vote(s) cast")
    return embed


class PollsCog(commands.Cog, name="Polls"):

    def __init__(self, bot):
        self.bot = bot

    poll_group = app_commands.Group(name="poll", description="System polls")

    @poll_group.command(name="create", description="Create a new poll for your system to vote on")
    @app_commands.describe(
        question="The question to ask", option1="First option", option2="Second option",
        option3="Third option (optional)", option4="Fourth option (optional)", option5="Fifth option (optional)"
    )
    async def poll_create(self, interaction: discord.Interaction, question: str, option1: str, option2: str,
                          option3: str = None, option4: str = None, option5: str = None):
        await interaction.response.defer()
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        options = [option1, option2] + [o for o in [option3, option4, option5] if o]
        poll_id = await self.bot.db.create_poll(system['id'], question, options)
        poll = await self.bot.db.get_poll(poll_id)
        color = parse_color(system['color'])
        embed = build_poll_embed(poll, system['system_name'], color)

        members = await self.bot.db.get_members(system['id'])

        class VoteSelect(discord.ui.Select):
            def __init__(self_inner):
                member_options = [discord.SelectOption(label=get_member_display(m), value=str(m['id'])) for m in members[:25]]
                super().__init__(placeholder="Who is voting?", options=member_options)
                self_inner.poll_id = poll_id
                self_inner.vote_options = options

            async def callback(self_inner, si: discord.Interaction):
                await si.response.defer(ephemeral=True)
                if si.user.id != interaction.user.id:
                    await si.followup.send("Not your system!", ephemeral=True)
                    return
                member = await self.bot.db.get_member(int(self_inner.values[0]))
                if not member:
                    await si.followup.send("Member not found.", ephemeral=True)
                    return

                opt_buttons = discord.ui.View(timeout=60)
                for i, opt in enumerate(self_inner.vote_options[:5]):
                    btn = discord.ui.Button(label=f"{i+1}. {opt[:60]}", style=discord.ButtonStyle.primary)
                    async def make_vote(btn_i: discord.Interaction, idx=i, m=member):
                        await btn_i.response.defer(ephemeral=True)
                        await self.bot.db.vote_poll(self_inner.poll_id, get_member_display(m), idx)
                        updated_poll = await self.bot.db.get_poll(self_inner.poll_id)
                        updated_system = await self.bot.db.get_system_by_id(system['id'])
                        new_embed = build_poll_embed(updated_poll, updated_system['system_name'], parse_color(updated_system['color']))
                        await btn_i.edit_original_response(content=f"✅ **{get_member_display(m)}** voted!", embed=new_embed, view=None)
                    btn.callback = make_vote
                    opt_buttons.add_item(btn)

                await si.followup.send(f"**{get_member_display(member)}** is voting for:", view=opt_buttons, ephemeral=True)

        view = discord.ui.View(timeout=300)
        if members:
            view.add_item(VoteSelect())

        msg = await interaction.followup.send(embed=embed, view=view)
        await self.bot.db.update_poll_message(poll_id, str(msg.id))

    @poll_group.command(name="results", description="View results of a poll")
    @app_commands.describe(poll_id="Poll ID")
    async def poll_results(self, interaction: discord.Interaction, poll_id: int):
        await interaction.response.defer()
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        poll = await self.bot.db.get_poll(poll_id)
        if not poll or poll['system_id'] != system['id']:
            await interaction.followup.send("❌ Poll not found.", ephemeral=True)
            return

        embed = build_poll_embed(poll, system['system_name'], parse_color(system['color']))
        await interaction.followup.send(embed=embed)

    @poll_group.command(name="close", description="Close a poll (no more votes)")
    @app_commands.describe(poll_id="Poll ID to close")
    async def poll_close(self, interaction: discord.Interaction, poll_id: int):
        await interaction.response.defer()
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        poll = await self.bot.db.get_poll(poll_id)
        if not poll or poll['system_id'] != system['id']:
            await interaction.followup.send("❌ Poll not found.", ephemeral=True)
            return

        await self.bot.db.close_poll(poll_id)
        poll = await self.bot.db.get_poll(poll_id)
        embed = build_poll_embed(poll, system['system_name'], parse_color(system['color']))
        embed.description = "🔴 **Poll closed.** Final results:"
        await interaction.followup.send(embed=embed)

    @poll_group.command(name="list", description="List all active polls for your system")
    async def poll_list(self, interaction: discord.Interaction):
        await interaction.response.defer()
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        polls = await self.bot.db.get_active_polls(system['id'])
        if not polls:
            await interaction.followup.send("No active polls. Use `/poll create` to start one!")
            return

        embed = discord.Embed(title=f"📊 {system['system_name']} — Active Polls", color=parse_color(system['color']))
        for p in polls:
            votes = json.loads(p['votes'])
            embed.add_field(name=f"ID `{p['id']}`: {p['question']}", value=f"{len(votes)} vote(s) cast • Created {p['created_at'][:10]}", inline=False)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(PollsCog(bot))
