"""
week.py — /week: one calendar week of deadlines, with buttons to flip weeks.

The new idea here: a button click is just another event. Discord sends it down
the same Gateway WebSocket as everything else, and discord.py calls the
matching method on the View below. We answer by EDITING the message in place
instead of posting a new one.

The feed is downloaded once, when you run /week. Every click after that only
redraws from `self.items`, so clicks are instant and never hit the 3-second limit.
"""

import discord

from canvas import Deadline, format_week

class WeekView(discord.ui.View):
    def __init__(self, items: list[Deadline], owner_id: int) -> None:
        super().__init__(timeout=600)  # buttons stop working after 10 minutes
        self.items = items
        self.owner_id = owner_id
        self.offset = 0                # 0 = this week, -1 = last week, 1 = next week
        self.message: discord.WebhookMessage | None = None  # set by /week so on_timeout can edit it

    def render(self) -> str:
        return format_week(self.items, self.offset)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Runs before every button. Same rule as /due: only the owner."""
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Not your bot — build your own! 🙂", ephemeral=True)
            return False
        return True

    async def flip(self, interaction: discord.Interaction, offset: int) -> None:
        self.offset = offset
        self.today.disabled = offset == 0  # "This week" does nothing when you're already there
        await interaction.response.edit_message(content=self.render(), view=self)

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary)
    async def earlier(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.flip(interaction, self.offset - 1)

    @discord.ui.button(label="This week", style=discord.ButtonStyle.secondary, disabled=True)
    async def today(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.flip(interaction, 0)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def later(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.flip(interaction, self.offset + 1)

    async def on_timeout(self) -> None:
        """Grey the buttons out so a stale click doesn't just say "interaction failed"."""
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass  # message deleted or too old to edit; nothing to clean up
