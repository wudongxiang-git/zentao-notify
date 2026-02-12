"""
禅道 API 客户端：REST v2 Token 认证，获取 Bug 列表
"""
import logging
from urllib.parse import urljoin

import requests

from config import Config

logger = logging.getLogger(__name__)


class ZenTaoClientError(Exception):
    """禅道 API 调用异常"""
    pass


class ZenTaoClient:
    """禅道 REST API v2 客户端（Token 认证）"""

    def __init__(self, base_url=None, account=None, password=None, api_key=None):
        self.base_url = (base_url or Config.ZENTAO_BASE_URL).rstrip("/")
        self.account = account or Config.ZENTAO_ACCOUNT
        self.password = password or Config.ZENTAO_PASSWORD
        self.api_key = api_key or Config.ZENTAO_API_KEY
        self._token = None
        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"

    def _url(self, path):
        return urljoin(self.base_url + "/", path.lstrip("/"))

    def login(self):
        """获取 Token。优先使用 password，其次 api_key。"""
        if not self.base_url or not self.account:
            raise ZenTaoClientError("未配置 ZENTAO_BASE_URL 或 ZENTAO_ACCOUNT")
        password = self.password or self.api_key
        if not password:
            raise ZenTaoClientError("未配置 ZENTAO_PASSWORD 或 ZENTAO_API_KEY")

        url = self._url("api.php/v2/users/login")
        payload = {"account": self.account, "password": password}
        try:
            resp = self._session.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error("禅道登录请求失败: %s", e)
            raise ZenTaoClientError(f"登录请求失败: {e}") from e
        except ValueError as e:
            logger.error("禅道登录响应非 JSON: %s", e)
            raise ZenTaoClientError("登录响应解析失败") from e

        if data.get("status") != "success":
            raise ZenTaoClientError(data.get("message", "登录失败"))
        self._token = data.get("token")
        if not self._token:
            raise ZenTaoClientError("登录响应中无 token")
        self._session.headers["Token"] = self._token
        logger.info("禅道登录成功")
        return self._token

    def _ensure_token(self):
        if not self._token:
            self.login()

    def get_products(self):
        """获取产品列表。返回 [{"id": "1", "name": "..."}, ...]"""
        self._ensure_token()
        url = self._url("api.php/v2/products")
        try:
            resp = self._session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error("获取产品列表失败: %s", e)
            raise ZenTaoClientError(f"获取产品列表失败: {e}") from e

        if data.get("status") != "success":
            raise ZenTaoClientError(data.get("message", "获取产品列表失败"))
        products = data.get("products") or []
        return [{"id": str(p.get("id", "")), "name": p.get("name", "")} for p in products]

    def get_bugs_for_product(self, product_id):
        """获取指定产品的 Bug 列表。返回 Bug 对象列表。"""
        self._ensure_token()
        url = self._url(f"api.php/v2/products/{product_id}/bugs")
        try:
            resp = self._session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.error("获取产品 %s Bug 列表失败: %s", product_id, e)
            raise ZenTaoClientError(f"获取 Bug 列表失败: {e}") from e

        if data.get("status") != "success":
            raise ZenTaoClientError(data.get("message", "获取 Bug 列表失败"))
        return data.get("bugs") or []

    def get_bugs_since(self, since_iso_datetime=None, product_ids=None):
        """
        获取自某时间以来有新增或更新的 Bug（按 openedDate / lastEditedDate 过滤）。
        since_iso_datetime: 例如 "2026-02-01 00:00:00"，None 表示不按时间过滤（返回全部）。
        product_ids: 产品 ID 列表，None 表示全部产品。
        返回: [{"id", "title", "severity", "status", "openedBy", "openedDate", "product", "module", ...}, ...]
        """
        self._ensure_token()
        if product_ids is None:
            products = self.get_products()
            product_ids = [p["id"] for p in products]
        if not product_ids:
            return []

        all_bugs = []
        for pid in product_ids:
            try:
                bugs = self.get_bugs_for_product(pid)
                all_bugs.extend(bugs)
            except ZenTaoClientError:
                raise
            except Exception as e:
                logger.warning("拉取产品 %s 的 Bug 时出错: %s", pid, e)

        if not since_iso_datetime:
            return all_bugs

        since = since_iso_datetime.replace(" ", " ").strip()
        result = []
        for b in all_bugs:
            opened = (b.get("openedDate") or "").strip()
            last_edited = (b.get("lastEditedDate") or "").strip()
            if opened and opened >= since:
                result.append(b)
            elif last_edited and last_edited >= since:
                result.append(b)
        return result

    def bug_view_url(self, bug_id):
        """返回禅道 Bug 详情页 URL"""
        return self._url(f"bug-view-{bug_id}.html")
