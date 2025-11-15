import os
from dotenv import load_dotenv

load_dotenv()


def get_bot_token():
    token = os.getenv("MAX_BOT_TOKEN", "").strip()
    return token.strip('"').strip("'")


def get_ai_tunnel_key():
    key = os.getenv("AI_TUNNEL_API_KEY", "").strip().strip('"').strip("'")
    if not key:
        return None
    return key
