"""
Polls cog — create polls that each system member can vote on separately.
Commands: /poll create, vote, results, close, list
"""

import discord
from discord import app_commands
from discord.ext import commands
import json
from utils.helpers import require_system, parse_color, get_member_display


def build_poll_embed(poll, system_name: str, color: discord.Color) -> discord.Embed:
    options = json.loads(poll['options'])
    votes = json.loads(poll['votes'])
    status = "🟢 Open" if poll['is_open'] else "🔴 Closed"

    embed = discord.Embed(
        title=f"📊 {poll['question']}",
        color=color
    )
    embed.set_author(name=f"{system_name} — System Poll")

    vote_counts = [0] * len(options)
    for member_name, opt_idx in votes.items():
        if 0 <= opt_idx < len(options):
            vote_counts[opt_idx] += 1

    total_votes = sum(vote_counts)

    for i, option in enumerate(options):
        count = vote_counts[i]
        pct = (count / total_votes * 100) if total_votes else 0
        bar_len = int(pct / 5)
        bar = '█' * bar_len + '░' * (20 - bar_len)
        embed.add_field(
            name=f"{i+1}. {option}",
            value=f"`{bar}` {count} vote(s) ({pct:.0f}%)",
            inline=False
        )

    # Show who voted what
    if votes:
        voter_lines = []
        for member_name, opt_idx in votes.items():
            if 0 <= opt_idx < len(options):
                voter_lines.append(f"**{member_name}** → {options[opt_idx]}")
        if voter_lines:
            embed.add_field(
                name="Votes Cast",
                value='\n'.join(voter_lines[:20]),
                inline=False
            )

    embed.set_footer(text=f"{status} • Poll ID: {poll['id']} • {total_votes} vote(s) cast")
    return embed


class PollVoteView(discord.ui.View):
    def __init__(self, bot, poll_id: int, system_id: int, options: list):
        super().__init__(timeout=None)
        self.bot = bot
        self.poll_id = poll_id
        self.system_id = system_id

        # Add a button per option (max 5 due to Discord limits in one row)
        for i, option in enumerate(options[:5]):
            label = option[:80]
            btn = discord.ui.Button(
                label=f"{i+1}. {label}",
                style=discord.ButtonStyle.primary,
                custom_id=f"poll_{poll_id}_{i}"
            )
            btn.callback = self._make_callback(i, option)
            self.add_item(btn)

    def _make_callback(self, option_index: int, option_label: str):
        async def callback(interaction: discord.Interaction):
            system = await self.bot.db.get_system(str(interaction.user.id), str(interaction.guild_id))
            if not system or system['id'] != self.system_id:
                await interaction.response.send_message(
                    "❌ Only the system owner can vote in this poll.", ephemeral=True
                )
                return

            # Ask which member is voting
            members = await self.bot.db.get_members(system['id'])
            if not members:
                await interaction.response.send_message("❌ No members found.", ephemeral=True)
                return

            select = MemberVoteSelect(self.bot, self.poll_id, option_index, option_label, members, system)
            view = discord.ui.View(timeout=60)
            view.add_item(select)
            await interaction.response.send_message(
                f"Who is voting for **{option_label}**?",
                view=view,
                ephemeral=True
            )
        return callback


class MemberVoteSelect(discord.ui.Select):
    def __init__(self, bot, poll_id, option_index, option_label, members, system):
        self.bot = bot
        self.poll_id = poll_id
        self.option_index = option_index
        self.option_label = option_label
        self.system = system
        options = [
            discord.SelectOption(label=get_member_display(m), value=str(m['id']))
            for m in members[:25]
        ]
        super().__init__(placeholder="Select which member is voting...", options=options)

    async def callback(self, interaction: discord.Interaction):
        member = await self.bot.db.get_member(int(self.values[0]))
        if not member:
            await interaction.response.send_message("❌ Member not found.", ephemeral=True)
            return

        success = await self.bot.db.vote_poll(self.poll_id, get_member_display(member), self.option_index)
        if not success:
            await interaction.response.send_message("❌ Poll not found.", ephemeral=True)
            return

        await interaction.response.send_message(
            f"✅ **{get_member_display(member)}** voted for **{self.option_label}**!",
            ephemeral=True
        )


class PollsCog(commands.Cog, name="Polls"):
    """Create polls where each system member can vote independently."""

    def __init__(self, bot):
        self.bot = bot

    poll_group = app_commands.Group(name="poll", description="System polls")

    @poll_group.command(name="create", description="Create a new poll for your system to vote on")
    @app_commands.describe(
        question="The question to ask",
        option1="First option",
        option2="Second option",
        option3="Third option (optional)",
        option4="Fourth option (optional)",
        option5="Fifth option (optional)"
    )
    async def poll_create(self, interaction: discord.Interaction,
                          question: str,
                          option1: str,
                          option2: str,
                          option3: str = None,
                          option4: str = None,
                          option5: str = None):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        options = [option1, option2]
        for o in [option3, option4, option5]:
            if o:
                options.append(o)

        poll_id = await self.bot.db.create_poll(system['id'], question, options)
        poll = await self.bot.db.get_poll(poll_id)

        color = parse_color(system['color'])
        embed = build_poll_embed(poll, system['system_name'], color)
        view = PollVoteView(self.bot, poll_id, system['id'], options)

        await interaction.response.send_message(embed=embed, view=view)
        msg = await interaction.original_response()
        await self.bot.db.update_poll_message(poll_id, str(msg.id))

    @poll_group.command(name="vote", description="Cast a vote in a poll")
    @app_commands.describe(
        poll_id="Poll ID to vote in",
        member="Which member is voting",
        option="Option number to vote for (1, 2, 3...)"
    )
    async def poll_vote(self, interaction: discord.Interaction,
                        poll_id: int, member: str, option: int):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        poll = await self.bot.db.get_poll(poll_id)
        if not poll or poll['system_id'] != system['id']:
            await interaction.response.send_message("❌ Poll not found.", ephemeral=True)
            return
        if not poll['is_open']:
            await interaction.response.send_message("❌ This poll is closed.", ephemeral=True)
            return

        options = json.loads(poll['options'])
        if option < 1 or option > len(options):
            await interaction.response.send_message(
                f"❌ Option must be between 1 and {len(options)}.", ephemeral=True
            )
            return

        results = await self.bot.db.search_member(system['id'], member)
        if not results:
            await interaction.response.send_message(f"❌ Member `{member}` not found.", ephemeral=True)
            return

        m = results[0]
        await self.bot.db.vote_poll(poll_id, get_member_display(m), option - 1)
        await interaction.response.send_message(
            f"✅ **{get_member_display(m)}** voted for **{options[option-1]}**!",
            ephemeral=True
        )

    @poll_group.command(name="results", description="View results of a poll")
    @app_commands.describe(poll_id="Poll ID")
    async def poll_results(self, interaction: discord.Interaction, poll_id: int):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        poll = await self.bot.db.get_poll(poll_id)
        if not poll or poll['system_id'] != system['id']:
            await interaction.response.send_message("❌ Poll not found.", ephemeral=True)
            return

        color = parse_color(system['color'])
        embed = build_poll_embed(poll, system['system_name'], color)
        await interaction.response.send_message(embed=embed)

    @poll_group.command(name="close", description="Close a poll (no more votes)")
    @app_commands.describe(poll_id="Poll ID to close")
    async def poll_close(self, interaction: discord.Interaction, poll_id: int):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        poll = await self.bot.db.get_poll(poll_id)
        if not poll or poll['system_id'] != system['id']:
            await interaction.response.send_message("❌ Poll not found.", ephemeral=True)
            return

        await self.bot.db.close_poll(poll_id)
        poll = await self.bot.db.get_poll(poll_id)
        color = parse_color(system['color'])
        embed = build_poll_embed(poll, system['system_name'], color)
        embed.description = "🔴 **Poll closed.** Final results:"
        await interaction.response.send_message(embed=embed)

    @poll_group.command(name="list", description="List all active polls for your system")
    async def poll_list(self, interaction: discord.Interaction):
        system = await require_system(interaction, self.bot.db)
        if not system:
            return

        polls = await self.bot.db.get_active_polls(system['id'])
        if not polls:
            await interaction.response.send_message("No active polls. Use `/poll create` to start one!", ephemeral=True)
            return

        color = parse_color(system['color'])
        embed = discord.Embed(title=f"📊 {system['system_name']} — Active Polls", color=color)
        for p in polls:
            votes = json.loads(p['votes'])
            embed.add_field(
                name=f"ID `{p['id']}`: {p['question']}",
                value=f"{len(votes)} vote(s) cast • Created {p['created_at'][:10]}",
                inline=False
            )
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(PollsCog(bot))
