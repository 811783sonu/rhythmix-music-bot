import os
from typing import Optional

# Telegram API Configuration
API_ID: int = int(os.environ.get("API_ID", "20550203"))
API_HASH: str = os.environ.get("API_HASH", "690778a70966c6f3f1fbacb96a49f360")
BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "8244422744:AAF0ZSEONT7YTpwKldhLGGpZO_tseXlnmYA")
BOT_NAME: str = os.environ.get("BOT_NAME", "Rhythmix X Bot")

# Optional: Session String for User Bot (if needed for private VC)
SESSION_STRING: Optional[str] = os.environ.get("SESSION_STRING", None)

# Logging Configuration
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")

# Download Configuration
DOWNLOAD_DIR: str = "downloads"
MAX_DOWNLOAD_SIZE: int = 500  # MB

# Queue Configuration
MAX_QUEUE_SIZE: int = 50

# Timeout Configuration
DOWNLOAD_TIMEOUT: int = 300  # seconds

# Feature Flags
ENABLE_SPOTIFY: bool = os.environ.get("ENABLE_SPOTIFY", "True").lower() == "true"
ENABLE_SOUNDCLOUD: bool = os.environ.get("ENABLE_SOUNDCLOUD", "True").lower() == "true"

# Admin Configuration (Optional - comma separated user IDs)
SUDO_USERS: list = [int(x) for x in os.environ.get("SUDO_USERS", "").split(",") if x.strip()]

# Health Check Configuration (for Render/Railway)
HEALTH_CHECK_PORT: int = int(os.environ.get("PORT", "8000"))
ENABLE_HEALTH_CHECK: bool = os.environ.get("ENABLE_HEALTH_CHECK", "True").lower() == "true"
