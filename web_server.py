import asyncio
import json
import logging
from pathlib import Path

from aiohttp import web

from config import WEB_PORT

logger = logging.getLogger("web_server")

STATIC_DIR = Path(__file__).parent / "static"


async def index_handler(request):
    return web.FileResponse(STATIC_DIR / "index.html")


async def webhook_handler(request):
    """Receive tweet from twitterapi.io webhook POST."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)

    seen = request.app["seen_ids"]

    # Filter rules send tweets in a "tweets" array
    tweets = data.get("tweets", [])
    if tweets:
        for tweet in tweets:
            tid = tweet.get("id", "")
            if not tid or tid in seen:
                continue
            seen.add(tid)
            tweet["_event_type"] = "tweet"
            author = tweet.get("author", {})
            username = author.get("userName", "?")
            text = (tweet.get("text") or "")[:80]
            logger.info("WEBHOOK tweet @%s: %s", username, text)
            await request.app["tweet_queue"].put(tweet)
    else:
        # Direct tweet payload (stream monitoring or manual test)
        tid = data.get("id", "")
        if tid and tid in seen:
            return web.json_response({"status": "ok"})
        if tid:
            seen.add(tid)
        data["_event_type"] = "tweet"
        author = data.get("author", {})
        username = author.get("userName", "?")
        text = (data.get("text") or "")[:80]
        if username != "?" or text:
            logger.info("WEBHOOK tweet @%s: %s", username, text)
            await request.app["tweet_queue"].put(data)

    # Keep seen set from growing forever
    if len(seen) > 10000:
        to_keep = list(seen)[-5000:]
        seen.clear()
        seen.update(to_keep)

    return web.json_response({"status": "ok"})


async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    logger.info("Browser connected (%s)", request.remote)
    request.app["ws_clients"].add(ws)
    try:
        async for msg in ws:
            pass
    finally:
        request.app["ws_clients"].discard(ws)
        logger.info("Browser disconnected (%s)", request.remote)
    return ws


async def broadcast_loop(app):
    queue = app["tweet_queue"]
    while True:
        tweet = await queue.get()
        payload = json.dumps(tweet)
        dead = set()
        for ws in app["ws_clients"]:
            try:
                await ws.send_str(payload)
            except Exception:
                dead.add(ws)
        for ws in dead:
            app["ws_clients"].discard(ws)
            try:
                await ws.close()
            except Exception:
                pass


async def on_startup(app):
    app["broadcast_task"] = asyncio.create_task(broadcast_loop(app))


async def on_cleanup(app):
    app["broadcast_task"].cancel()
    for ws in set(app["ws_clients"]):
        await ws.close()


def create_app(tweet_queue: asyncio.Queue) -> web.Application:
    app = web.Application()
    app["tweet_queue"] = tweet_queue
    app["ws_clients"] = set()
    app["seen_ids"] = set()
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    app.router.add_get("/", index_handler)
    app.router.add_post("/webhook", webhook_handler)
    app.router.add_get("/ws", websocket_handler)
    app.router.add_static("/static", STATIC_DIR)
    return app


async def start_web_server(tweet_queue: asyncio.Queue):
    app = create_app(tweet_queue)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", WEB_PORT)
    await site.start()
    logger.info("Web server running on http://localhost:%d", WEB_PORT)
    logger.info("Webhook endpoint: POST /webhook")
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
