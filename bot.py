"""
bot.py — DueBot: a Discord bot that knows when your Canvas work is due.

How a Discord bot works, in one paragraph:
  Your code opens ONE long-lived WebSocket to Discord (the "Gateway") and logs
  in with a token. From then on Discord PUSHES events down that socket — someone
  sent a message, someone joined a voice channel, someone ran your slash
  command. You never poll. Each `@bot.event` / `@bot.tree.command` below is a
  handler for one kind of event. When you want to DO something (send a DM,
  reply) you call Discord's REST API, which discord.py wraps for you.

Run it:   python bot.py          (reads .env — see .env.example)
"""

import logging
import os
from datetime import time

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

from canvas import TZ, get_digest

# ---------------------------------------------------------------- config ----
load_dotenv()                                               # .env -> os.environ


def env_int(name: str, default: int = 0) -> int:
    """An optional number from .env. A blank line like `GUILD_ID=` counts as unset."""
    return int(os.getenv(name) or default)


TOKEN = os.environ["DISCORD_TOKEN"]                         # required
CANVAS_FEED_URL = os.environ["CANVAS_FEED_URL"]             # required
OWNER_ID = int(os.environ["OWNER_ID"])                      # who gets the DMs (you)
GUILD_ID = env_int("GUILD_ID")                              # workshop server: instant command sync
WATCH_USER_ID = env_int("WATCH_USER_ID")                    # friend to watch in voice (optional)
DIGEST_HOUR = env_int("DIGEST_HOUR", 8)                     # morning DM, local time

# Logging. Set SHOW_GATEWAY=1 to watch the WebSocket heartbeats scroll by.
discord.utils.setup_logging(level=logging.INFO)
if os.getenv("SHOW_GATEWAY"):
    logging.getLogger("discord.gateway").setLevel(logging.DEBUG)
log = logging.getLogger("duebot")

# "Intents" = which event types you ask Discord to send you. Default covers
# guilds + voice state. We do NOT need Message Content (a privileged intent)
# because we use slash commands, not "!commands" parsed out of chat.
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


# ---------------------------------------------------------------- events ----
@bot.event
async def on_ready() -> None:
    """Fires once the Gateway handshake is done. The socket is live from here."""
    log.info("Logged in as %s (id=%s)", bot.user, bot.user.id)
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="your deadlines"))

    # Register slash commands. Syncing to ONE guild is instant; a global sync
    # can take up to an hour to show up — the #1 "my command isn't there" bug.
    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    else:
        await bot.tree.sync()

    if not morning_digest.is_running():
        morning_digest.start()


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
    """Discord tells us every time ANYONE's voice state changes. We care about one person joining."""
    joined = before.channel is None and after.channel is not None
    if WATCH_USER_ID and member.id == WATCH_USER_ID and joined:
        owner = await bot.fetch_user(OWNER_ID)
        await owner.send(f"👀 **{member.display_name}** just joined **{after.channel.name}** in {member.guild.name}")


# ------------------------------------------------------------- commands ----
@bot.tree.command(name="ping", description="Is the bot alive?")
async def ping(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(f"pong — {round(bot.latency * 1000)} ms to the Gateway", ephemeral=True)


@bot.tree.command(name="due", description="What's due on Canvas soon?")
@app_commands.describe(days="How many days ahead to look (default 7)")
async def due(interaction: discord.Interaction, days: app_commands.Range[int, 1, 60] = 7) -> None:
    # The server is shared; your Canvas data is not. Only answer the owner.
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("Not your bot — build your own! 🙂", ephemeral=True)
    # Discord gives you 3 seconds to answer an interaction. Fetching Canvas can
    # take longer, so we `defer` (shows "thinking...") and follow up afterwards.
    await interaction.response.defer(ephemeral=True)
    try:
        text = await get_digest(CANVAS_FEED_URL, days)
    except Exception as e:  # bad URL, Canvas down, etc.
        log.exception("Canvas fetch failed")   # full detail stays in YOUR terminal...
        text = f"Couldn't read your Canvas feed ({type(e).__name__}). Check the terminal."  # ...never in chat: errors can echo the URL
    await interaction.followup.send(f"📚 **Due in the next {days} days**\n{text}", ephemeral=True)


@bot.tree.command(name="digest", description="Send me the morning digest right now")
async def digest_now(interaction: discord.Interaction) -> None:
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("Not your bot — build your own! 🙂", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    await send_digest()
    await interaction.followup.send("Sent — check your DMs.", ephemeral=True)


# ------------------------------------------------------- scheduled task ----
@tasks.loop(time=time(hour=DIGEST_HOUR, minute=0, tzinfo=TZ))
async def morning_digest() -> None:
    """Runs every day at DIGEST_HOUR. This only works if the bot is still running — hence deploying it."""
    await send_digest()


@morning_digest.before_loop
async def _wait() -> None:
    await bot.wait_until_ready()


async def send_digest(days: int = 7) -> None:
    owner = await bot.fetch_user(OWNER_ID)
    text = await get_digest(CANVAS_FEED_URL, days)
    await owner.send(f"☀️ **Good morning. Due in the next {days} days:**\n{text}")


if __name__ == "__main__":
    bot.run(TOKEN, log_handler=None)   # logging already configured above
