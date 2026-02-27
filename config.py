import os
from dotenv import load_dotenv

load_dotenv()

TWITTERAPI_KEY = os.getenv("TWITTERAPI_KEY", "")
WEB_PORT = int(os.getenv("WEB_PORT", "8080"))
WS_URL = "wss://ws.twitterapi.io/twitter/tweet/websocket"
