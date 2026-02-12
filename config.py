"""
配置管理：从环境变量读取，支持 .env 文件
"""
import os

_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.isfile(_env_path):
    with open(_env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip()
                if k and v and k not in os.environ:
                    os.environ[k] = v


class Config:
    ZENTAO_BASE_URL = (os.getenv("ZENTAO_BASE_URL") or "").rstrip("/")
    ZENTAO_ACCOUNT = os.getenv("ZENTAO_ACCOUNT", "")
    ZENTAO_PASSWORD = os.getenv("ZENTAO_PASSWORD", "")
    ZENTAO_API_KEY = os.getenv("ZENTAO_API_KEY", "")
    ZENTAO_PRODUCT_IDS = os.getenv("ZENTAO_PRODUCT_IDS", "").strip() or None
    ZENTAO_USE_LEGACY_API = os.getenv("ZENTAO_USE_LEGACY_API", "").strip().lower() in ("1", "true", "yes")

    FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL", "").strip() or None

    POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "300"))
    STATE_FILE = os.getenv("STATE_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json"))
