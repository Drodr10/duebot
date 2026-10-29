"""
check.py — run this BEFORE bot.py. It tells you which of the four .env values is wrong,
instead of making you guess from a traceback.

    python check.py
"""

import asyncio
import os
import re
import sys

import aiohttp
from dotenv import load_dotenv

from canvas import fetch_feed, parse_feed, upcoming

load_dotenv()
OK, BAD = "  ok   ", "  FAIL "
problems = 0


def report(good: bool, label: str, detail: str = "") -> None:
    global problems
    problems += 0 if good else 1
    print((OK if good else BAD), label, ("— " + detail) if detail else "")


def is_snowflake(v: str) -> bool:
    return v.isdigit() and 17 <= len(v) <= 20


async def main() -> None:
    print("DueBot preflight\n")

    # 1. .env present and the four required lines filled
    if not os.path.exists(".env"):
        report(False, ".env file", "not found — run `cp .env.example .env` in the repo folder")
        return
    token = os.getenv("DISCORD_TOKEN", "")
    feed = os.getenv("CANVAS_FEED_URL", "")
    owner = os.getenv("OWNER_ID", "")
    guild = os.getenv("GUILD_ID", "")

    report(bool(token), "DISCORD_TOKEN set")
    if token:
        report(len(token.split(".")) == 3 and " " not in token and '"' not in token,
               "DISCORD_TOKEN looks like a token", "expect three dot-separated parts, no quotes or spaces")
    report(is_snowflake(owner), "OWNER_ID is a Discord id", "17–20 digits; right-click yourself → Copy User ID")
    report(is_snowflake(guild) or guild == "", "GUILD_ID is a Discord id or blank",
           "blank means global command sync (slow); set it for the workshop server")
    report(feed.startswith("https://") and feed.endswith(".ics"), "CANVAS_FEED_URL is a feed URL",
           "should start with https:// and end with .ics (the whole link, not just the user_ part)")

    # 2. The token actually works (REST call, no Gateway connection)
    if token:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get("https://discord.com/api/v10/users/@me",
                                 headers={"Authorization": f"Bot {token}"},
                                 timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status == 200:
                        me = await r.json()
                        report(True, "Discord accepts the token", f"logged in as {me.get('username')}")
                    else:
                        report(False, "Discord accepts the token", f"HTTP {r.status} — reset the token in the portal and paste it again")
        except Exception as e:
            report(False, "Discord reachable", type(e).__name__)

    # 3. The Canvas feed downloads and parses
    if feed.startswith("https://"):
        try:
            items = parse_feed(await fetch_feed(feed))
            soon = upcoming(items, days=14)
            report(len(items) > 0, "Canvas feed downloads and parses",
                   f"{len(items)} entries, {len(soon)} assignments due in the next 14 days")
        except Exception as e:
            report(False, "Canvas feed downloads", f"{type(e).__name__} — copy the link again from Canvas → Calendar → Calendar Feed")

    print()
    print("All good. Run:  python bot.py" if problems == 0 else f"{problems} problem(s). Fix them in .env and run check.py again.")
    sys.exit(0 if problems == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
