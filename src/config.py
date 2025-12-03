import os

class Config:
    TOKEN = os.getenv("TOKEN")
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    OWNER_USERNAME = "sizuka42"
    OWNER_ID = None
    
    BOT_PREFIX = "!"
    DEFAULT_LANGUAGE = "en"
    SUPPORTED_LANGUAGES = ["en", "es", "fr", "de", "pt", "ar", "zh", "ja", "ko", "ru"]
    
    TICKET_CATEGORY_NAME = "Tickets"
    ORDER_CHANNEL_ID = int(os.getenv("ORDER_CHANNEL_ID", "0"))
    STAFF_ROLE_NAME = "Staff"
    
    IGNORED_CATEGORIES = ["chat zone", "more fun"]
    
    PURCHASE_KEYWORDS = [
        "buy", "purchase", "want to buy", "wanna buy", "buying", "i want",
        "how much", "price", "cost", "order", "get this", "interested in",
        "can i get", "looking for", "need", "want this"
    ]
    
    EMBED_COLOR = 0x5865F2
    SUCCESS_COLOR = 0x57F287
    WARNING_COLOR = 0xFEE75C
    ERROR_COLOR = 0xED4245
