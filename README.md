# DueBot — a Discord bot that knows when your Canvas work is due

Built live at the SEC workshop. You leave with a bot that:

- replies to `/due` with everything due on Canvas in the next N days
- DMs you a digest every morning, and (optionally) 24 hours and 1 hour before each deadline
- DMs you when a specific friend joins a voice channel
- runs in a container so it keeps working after you close your laptop

Branches: **`start`** is the skeleton we build from in the room. **`main`** is the finished bot.
Lost? `git checkout main`.

## 0. What you need (5 minutes, do this first)

**A Discord account with Developer Mode on.** User Settings → search "developer" → Developer → Developer Mode. This adds
"Copy User ID" / "Copy Server ID" to right-click menus; you'll need both IDs.

**A bot application.** https://discord.com/developers/applications

1. **New Application** → name it → Create.
2. Left sidebar → **Bot** → **Reset Token** (needs your two-factor code) → copy it into `.env` as `DISCORD_TOKEN`. It is shown once.
   Leave all three *Privileged Gateway Intents* OFF — this bot doesn't need them.
3. Left sidebar → **OAuth2** → scroll to **OAuth2 URL Generator**: tick scopes `bot` and `applications.commands`;
   under Bot Permissions tick `Send Messages`, `Embed Links`, `Read Message History`.
   Copy the generated URL, open it, pick the workshop server, Authorize.

**Your Canvas calendar feed.** Canvas → Calendar → **Calendar Feed** (bottom of the right sidebar) →
copy the URL into `.env` as `CANVAS_FEED_URL`. It's a secret: anyone with it can read your calendar.

**IDs.** Right-click yourself → Copy User ID → `OWNER_ID`. Right-click the server icon → Copy Server ID → `GUILD_ID`.

## 1. Run it

Easiest: open this repo in a **GitHub Codespace** (green Code button → Codespaces → Create). Python and
the packages are preinstalled and `.env` is created for you to fill in.

Locally:

```bash
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # fill it in
python check.py                                        # tells you which .env value is wrong, if any
python bot.py
```

You should see `Logged in as DueBot#1234`. In Discord, type `/ping`.

Test the Canvas half without Discord at all:

```bash
python canvas.py "https://ufl.instructure.com/feeds/calendars/user_....ics" 14
```

## 2. The build (what each step teaches)

| Step | You write | The concept |
|---|---|---|
| `/ping` works | nothing — it's in `start` | the **Gateway**: one WebSocket, Discord pushes events to you (`SHOW_GATEWAY=1` to watch heartbeats) |
| `on_voice_state_update` | ~5 lines | **event-driven**: you don't poll for your friend, Discord tells you |
| `/due` | ~10 lines | calling an **external API** (Canvas feed), `defer` because of Discord's 3-second rule |
| `morning_digest` loop + `/digest` | ~10 lines | **scheduled work**, and why the bot must stay running |
| `docker build` / `docker run` | 0 lines | **containers**: same image on your laptop and on a server |

Gotchas you will hit, in order of likelihood (`python check.py` catches the first two):

- **Slash command doesn't appear.** Commands synced *globally* take up to an hour. Set `GUILD_ID` so
  they sync to the workshop server instantly. Also try Ctrl+R / Cmd+R in Discord.
- **"Improper token has been passed."** Token copied wrong, or you reset it in the portal after copying.
- **Bot replies to itself forever.** Not possible here (slash commands only), but it's the classic
  first bug for `on_message` bots: always check `message.author == bot.user`.
- **DM never arrives.** The bot can only DM people who share a server with it and allow DMs from server members.

## 3. Keep it running (deploy)

```bash
docker build -t duebot .
docker run --env-file .env duebot
```

That runs the exact same image a server would. Free hosting for an always-on bot in 2026 is thin:
Fly.io and Render no longer have usable free tiers for background processes, Railway gives a one-time
trial credit (no card) which is enough to see it live tonight, and **Oracle Cloud "Always Free"** or the
**GitHub Student Developer Pack** credits (DigitalOcean, Azure, Heroku) are the real long-term answers.
Any of them takes the Dockerfile as-is: push the repo, set the four env vars in their dashboard, done.

## 4. Stretch: reminders before each deadline

Set `REMIND_HOURS=24,1` in `.env` and the bot DMs you 24 hours and again 1 hour before every
assignment. The logic is in `reminders.py` and is about twenty lines. The interesting part is
**not sending the same reminder twice**: the bot remembers what it sent in `state/sent.json`, and
that file must survive restarts. In Docker that means a volume:

```bash
docker run --env-file .env -v duebot-state:/app/state duebot
```

Without the volume every container restart re-sends every reminder in the window. Try it once
on purpose; it's the clearest "state needs a home" lesson you'll get.

## 5. Bonus: the other direction — webhooks

`webhook_demo.py` is a 60-line server that receives **GitHub** webhooks (push, PR) and relays them to a
Discord channel. It's the mirror image of the bot: the bot *opens* a connection to Discord; a webhook is
another service opening a connection to *you*, which is why it needs a public URL (`ngrok http 8000` on a
laptop). Setup steps are at the top of the file.

## Tests

```bash
python -m unittest discover tests
```
