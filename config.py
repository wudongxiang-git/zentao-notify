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
    # REST API：Bug 列表 browseType（禅道 param 名为 status），默认 all 拉全部状态
    ZENTAO_BUG_BROWSE_STATUS = (os.getenv("ZENTAO_BUG_BROWSE_STATUS", "all") or "all").strip()
    # REST API 分页每页条数（产品、Bug 列表）
    ZENTAO_API_PAGE_LIMIT = max(20, int(os.getenv("ZENTAO_API_PAGE_LIMIT", "100")))
    # Bug 详情链接：path_info（bug-view-1.html）或 get（index.php?m=bug&f=view&bugID=1）
    ZENTAO_URL_STYLE = (os.getenv("ZENTAO_URL_STYLE", "path_info") or "path_info").strip().lower()

    FEISHU_WEBHOOK_URL = os.getenv("FEISHU_WEBHOOK_URL", "").strip() or None

    POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "300"))
    STATE_FILE = os.getenv("STATE_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json"))
