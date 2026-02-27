import asyncio
import json
import logging

import aiohttp

from config import TWITTERAPI_KEY, WS_URL

logger = logging.getLogger("stream")

RECONNECT_MIN = 10
RECONNECT_MAX = 120


async def start_stream(on_event):
    """Connect to twitterapi.io WebSocket and emit tweet events in real-time."""
    delay = RECONNECT_MIN

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                logger.info("Connecting to %s", WS_URL)
                async with session.ws_connect(
                    WS_URL,
                    headers={"x-api-key": TWITTERAPI_KEY},
                    heartbeat=25,
                    timeout=aiohttp.ClientWSTimeout(ws_close=30),
                ) as ws:
                    delay = RECONNECT_MIN
                    logger.info("WebSocket connected — waiting for tweets")

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                            except json.JSONDecodeError:
                                logger.warning("Bad JSON: %s", msg.data[:120])
                                continue

                            evt = data.get("event_type") or data.get("type")

                            if evt == "connected":
                                logger.info("Stream confirmed connected")
                                continue

                            if evt == "ping":
                                continue

                            # Tweet event
                            if evt == "tweet" or data.get("id"):
                                data["_event_type"] = "tweet"
                                author = data.get("author", {})
                                username = author.get("userName", "?")
                                text = (data.get("text") or "")[:80]
                                logger.info("Tweet @%s: %s", username, text)
                                await on_event(data)

                        elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                            logger.warning("WebSocket closed/error: %s", msg.data)
                            break

        except aiohttp.ClientError as e:
            logger.error("Connection error: %s", e)
        except asyncio.CancelledError:
            logger.info("Stream cancelled")
            return
        except Exception as e:
            logger.error("Unexpected error: %s", e)

        logger.info("Reconnecting in %ds...", delay)
        await asyncio.sleep(delay)
        delay = min(delay * 2, RECONNECT_MAX)
