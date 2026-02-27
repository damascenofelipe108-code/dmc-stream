import asyncio
import logging
import sys
import io

from config import WEB_PORT
from web_server import start_web_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)-12s] %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(
        io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    )],
)
logger = logging.getLogger("main")


async def main():
    logger.info("Starting DMC Stream (webhook mode)")
    logger.info("Web UI at http://localhost:%d", WEB_PORT)

    queue: asyncio.Queue = asyncio.Queue()
    await start_web_server(queue)


if __name__ == "__main__":
    asyncio.run(main())
