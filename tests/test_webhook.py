"""Fakes both ends: a 'GitHub' POST with a real HMAC signature in, a fake 'Discord' webhook endpoint out."""
import hashlib
import hmac
import json
import os
import unittest

os.environ["DISCORD_WEBHOOK_URL"] = "http://127.0.0.1:8765/discord"
os.environ["GITHUB_WEBHOOK_SECRET"] = "s3cret"

from aiohttp import web
import aiohttp

import webhook_demo


class WebhookTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.received = []

        async def fake_discord(req):
            self.received.append(await req.json())
            return web.Response(text="ok")

        fake = web.Application()
        fake.router.add_post("/discord", fake_discord)
        # Bind both servers to free ports (port 0) so tests never collide.
        self.runner = web.AppRunner(fake)
        await self.runner.setup()
        await web.TCPSite(self.runner, "127.0.0.1", 0).start()
        webhook_demo.DISCORD_WEBHOOK_URL = f"http://127.0.0.1:{self.runner.addresses[0][1]}/discord"
        self.demo = web.AppRunner(webhook_demo.make_app())
        await self.demo.setup()
        await web.TCPSite(self.demo, "127.0.0.1", 0).start()
        self.session = aiohttp.ClientSession(f"http://127.0.0.1:{self.demo.addresses[0][1]}")

    async def asyncTearDown(self):
        await self.session.close()
        await self.demo.cleanup()
        await self.runner.cleanup()

    def sign(self, body: bytes) -> str:
        return "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()

    async def test_push_is_relayed(self):
        payload = {"repository": {"full_name": "Drodr10/duebot"}, "pusher": {"name": "diego"},
                   "ref": "refs/heads/main", "commits": [{}, {}], "compare": "https://github.com/x/compare"}
        body = json.dumps(payload).encode()
        r = await self.session.post("/github", data=body,
                                   headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": self.sign(body),
                                            "Content-Type": "application/json"})
        self.assertEqual(r.status, 200)
        self.assertEqual(len(self.received), 1)
        self.assertIn("**diego** pushed 2 commit(s) to `main`", self.received[0]["content"])

    async def test_bad_signature_rejected(self):
        body = json.dumps({"repository": {"full_name": "x/y"}}).encode()
        r = await self.session.post("/github", data=body,
                                   headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": "sha256=nope",
                                            "Content-Type": "application/json"})
        self.assertEqual(r.status, 401)
        self.assertEqual(self.received, [])

    async def test_pull_request(self):
        payload = {"repository": {"full_name": "x/y"}, "action": "opened",
                   "pull_request": {"title": "Add /due", "html_url": "https://github.com/x/y/pull/1", "user": {"login": "diego"}}}
        body = json.dumps(payload).encode()
        r = await self.session.post("/github", data=body,
                                   headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": self.sign(body),
                                            "Content-Type": "application/json"})
        self.assertEqual(r.status, 200)
        self.assertIn("PR **opened**", self.received[0]["content"])


if __name__ == "__main__":
    unittest.main()
