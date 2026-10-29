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

Today we fill in the three STEP blocks below, top to bottom.
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
TOKEN = os.environ["DISCORD_TOKEN"]                         # required
CANVAS_FEED_URL = os.environ["CANVAS_FEED_URL"]             # required
OWNER_ID = int(os.environ["OWNER_ID"])                      # who gets the DMs (you)
GUILD_ID = int(os.getenv("GUILD_ID", "0"))                  # workshop server: instant command sync
WATCH_USER_ID = int(os.getenv("WATCH_USER_ID", "0"))        # friend to watch in voice (optional)
DIGEST_HOUR = int(os.getenv("DIGEST_HOUR", "8"))            # morning DM, local time

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

    # STEP 3b: start the morning_digest loop here (guard with .is_running()).


# STEP 1 — the event-driven part.
# Discord sends `on_voice_state_update(member, before, after)` every time anyone's
# voice state changes. Write a handler that DMs OWNER_ID when WATCH_USER_ID goes
# from no channel (before.channel is None) to a channel (after.channel is not None).
# Hints: bot.fetch_user(OWNER_ID)  →  owner.send("...")   member.display_name, after.channel.name


# ------------------------------------------------------------- commands ----
@bot.tree.command(name="ping", description="Is the bot alive?")
async def ping(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(f"pong — {round(bot.latency * 1000)} ms to the Gateway", ephemeral=True)


# STEP 2 — call an external API.
# Add a /due command with an optional `days` argument (default 7) that replies with
# `await get_digest(CANVAS_FEED_URL, days)`.
# Discord gives you 3 seconds to answer. Fetching Canvas can take longer, so:
#   await interaction.response.defer(ephemeral=True)   ... then ...
#   await interaction.followup.send(text, ephemeral=True)
# Wrap the fetch in try/except so a bad URL gives a message, not a crash.


# ------------------------------------------------------- scheduled task ----
# STEP 3 — scheduled work.
# Write `send_digest()` (fetch_user(OWNER_ID) → owner.send(digest)), then a
#   @tasks.loop(time=time(hour=DIGEST_HOUR, minute=0, tzinfo=TZ))
# task that calls it, with a `.before_loop` that awaits bot.wait_until_ready().
# Add a /digest command that calls send_digest() right now, so you don't have to wait until morning.


if __name__ == "__main__":
    bot.run(TOKEN, log_handler=None)   # logging already configured above
