"""
webhook_demo.py — the OTHER direction of event-driven: GitHub pushes events to US.

  GitHub ──HTTP POST──▶ this tiny server ──HTTP POST──▶ Discord channel

The Discord bot in bot.py receives events over a WebSocket that *we* opened.
A webhook is the opposite shape: the other service opens a connection to a URL
*we* host. That means we need a public URL — on a laptop that's a tunnel
(`ngrok http 8000`), in production it's wherever you deployed.

Setup (presenter demo):
  1. Discord: channel -> Edit -> Integrations -> Webhooks -> New Webhook -> copy URL
  2. GitHub repo -> Settings -> Webhooks -> Add webhook
       Payload URL = https://<your-tunnel>/github   Content type = application/json
       Secret = anything (put the same string in GITHUB_WEBHOOK_SECRET)
  3. python webhook_demo.py   then push a commit or open a PR.
"""

import hashlib
import hmac
import os

import aiohttp
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()
DISCORD_WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
PORT = int(os.getenv("PORT", "8000"))


def verify(body: bytes, signature: str | None) -> bool:
    """GitHub signs every delivery with your secret. Without this, anyone could POST fake events."""
    if not SECRET:
        return True  # demo mode
    expected = "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def describe(event: str, p: dict) -> str:
    repo = p.get("repository", {}).get("full_name", "?")
    if event == "push":
        n = len(p.get("commits", []))
        branch = p.get("ref", "").split("/")[-1]
        return f"🚀 **{p['pusher']['name']}** pushed {n} commit(s) to `{branch}` in **{repo}**\n{p.get('compare', '')}"
    if event == "pull_request":
        pr = p["pull_request"]
        return f"🔀 PR **{p['action']}** in **{repo}**: [{pr['title']}]({pr['html_url']}) by {pr['user']['login']}"
    if event == "ping":
        return f"🏓 GitHub says hi from **{repo}** — webhook wired up."
    return f"📦 `{event}` event in **{repo}**"


async def github(request: web.Request) -> web.Response:
    body = await request.read()
    if not verify(body, request.headers.get("X-Hub-Signature-256")):
        return web.Response(status=401, text="bad signature")
    event = request.headers.get("X-GitHub-Event", "unknown")
    text = describe(event, await request.json())
    async with aiohttp.ClientSession() as s:
        await s.post(DISCORD_WEBHOOK_URL, json={"content": text})
    return web.Response(text="ok")


def make_app() -> web.Application:
    app = web.Application()
    app.router.add_post("/github", github)
    return app


if __name__ == "__main__":
    print(f"Listening on http://localhost:{PORT}/github")
    web.run_app(make_app(), port=PORT)
