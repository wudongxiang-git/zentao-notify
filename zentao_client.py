"""
禅道 API 客户端：支持 v1 / v2 / 传统 Session（开源版 21.7.6 为 v1）
"""
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode, urljoin

import requests

from config import Config

logger = logging.getLogger(__name__)


class ZenTaoClientError(Exception):
    """禅道 API 调用异常"""
    pass


class ZenTaoAuthError(ZenTaoClientError):
    """认证失效（如 token 过期），清空登录状态后可由调用方重试"""
    pass


def parse_zentao_datetime(value):
    """解析禅道时间字段（本地 Y-m-d H:i:s 或 API 默认 UTC ISO）。"""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s == "0000-00-00 00:00:00":
        return None
    if s.endswith("Z"):
        try:
            dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            return dt.astimezone().replace(tzinfo=None)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _display_user(val):
    if isinstance(val, dict):
        return val.get("realname") or val.get("account") or ""
    return str(val) if val is not None else ""


def _normalize_bug(b):
    """将禅道 Bug 对象统一为含 openedDate、lastEditedDate、product、module 等字段的字典。"""
    opened = b.get("openedDate")
    if opened is None or opened == "0000-00-00 00:00:00":
        opened = ""
    else:
        opened = str(opened).strip()

    last_edited = b.get("lastEditedDate")
    if last_edited is None or last_edited == "0000-00-00 00:00:00":
        last_edited = ""
    else:
        last_edited = str(last_edited).strip()

    product = b.get("productName") or b.get("product") or ""
    if isinstance(product, dict):
        product = product.get("name") or product.get("id") or ""

    module = b.get("moduleTitle") or b.get("module") or ""
    if isinstance(module, dict):
        module = module.get("name") or ""

    return {
        "id": str(b.get("id", "")),
        "title": b.get("title") or "",
        "severity": b.get("severity") or "",
        "status": b.get("statusName") or b.get("status") or "",
        "openedBy": _display_user(b.get("openedBy")),
        "openedDate": opened,
        "lastEditedDate": last_edited,
        "product": product,
        "module": module,
    }


def bug_changed_since(bug, since_datetime_str):
    """Bug 的创建或最后编辑时间是否不早于上次检查时刻（含等于）。"""
    since_dt = parse_zentao_datetime(since_datetime_str)
    if since_dt is None:
        return True
    for key in ("openedDate", "lastEditedDate"):
        dt = parse_zentao_datetime(bug.get(key))
        if dt is not None and dt >= since_dt:
            return True
    return False


class ZenTaoClient:
    """
    禅道 API 客户端：
    - 优先 v2（api.php/v2/users/login），适用于 21.7.8+
    - 若 v2 返回 404，尝试 v1（api.php/v1/tokens），适用于开源版 21.7.6
    - 若 v1 也不可用，使用传统 Session API（index.php?m=api&f=getSessionID 等）
    """

    def __init__(self, base_url=None, account=None, password=None, api_key=None, use_legacy=None):
        self.base_url = (base_url or Config.ZENTAO_BASE_URL).rstrip("/")
        self.account = account or Config.ZENTAO_ACCOUNT
        self.password = password or Config.ZENTAO_PASSWORD
        self.api_key = api_key or Config.ZENTAO_API_KEY
        self._use_legacy = use_legacy if use_legacy is not None else getattr(Config, "ZENTAO_USE_LEGACY_API", None)
        self._token = None
        self._api_version = None  # "v1" | "v2"
        self._logged_in = False
        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"
        self._product_name_cache = {}

    def _url(self, path):
        return urljoin(self.base_url + "/", path.lstrip("/"))

    def _try_v2_login(self):
        """REST v2 登录。成功返回 True，404 返回 False。"""
        url = self._url("api.php/v2/users/login")
        password = self.password or self.api_key
        if not password:
            raise ZenTaoClientError("未配置 ZENTAO_PASSWORD 或 ZENTAO_API_KEY")
        try:
            resp = self._session.post(
                url,
                json={"account": self.account, "password": password},
                timeout=15,
            )
            if resp.status_code == 404:
                return False
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            if getattr(e, "response", None) and getattr(e.response, "status_code", None) == 404:
                return False
            raise ZenTaoClientError(f"登录请求失败: {e}") from e

        if data.get("status") != "success":
            raise ZenTaoClientError(data.get("message", "登录失败"))
        self._token = data.get("token")
        if not self._token:
            raise ZenTaoClientError("登录响应中无 token")
        self._session.headers["Token"] = self._token
        self._api_version = "v2"
        self._logged_in = True
        return True

    def _try_v1_login(self):
        """REST v1 登录（开源版 21.7.6：POST /api.php/v1/tokens）。成功返回 True，404 返回 False。"""
        url = self._url("api.php/v1/tokens")
        password = self.password or self.api_key
        if not password:
            raise ZenTaoClientError("未配置 ZENTAO_PASSWORD 或 ZENTAO_API_KEY")
        try:
            resp = self._session.post(
                url,
                json={"account": self.account, "password": password},
                timeout=15,
            )
            if resp.status_code == 404:
                return False
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            if getattr(e, "response", None) and getattr(e.response, "status_code", None) == 404:
                return False
            raise ZenTaoClientError(f"v1 登录请求失败: {e}") from e

        if isinstance(data, dict) and data.get("error"):
            raise ZenTaoClientError(str(data["error"]))

        self._token = data.get("token")
        if not self._token:
            raise ZenTaoClientError("v1 登录响应中无 token")
        self._session.headers["Token"] = self._token
        self._api_version = "v1"
        self._logged_in = True
        logger.info("禅道 REST v1 登录成功")
        return True

    def _legacy_login(self):
        """传统 Session 登录（getSessionID + user-login）。"""
        get_session_url = self._url("index.php?m=api&f=getSessionID&t=json")
        try:
            r = self._session.get(get_session_url, timeout=15)
            r.raise_for_status()
            data = r.json()
        except requests.RequestException as e:
            raise ZenTaoClientError(f"getSessionID 失败: {e}") from e

        if data.get("status") != "success":
            raise ZenTaoClientError(data.get("message", "getSessionID 失败"))
        inner = data.get("data") or data
        session_name = inner.get("sessionName") or "zentaosid"
        session_id = inner.get("sessionID")
        if not session_id:
            raise ZenTaoClientError("getSessionID 未返回 sessionID")

        self._session.cookies.set(session_name, session_id, domain="", path="/")
        self._session.headers.pop("Token", None)

        login_url = self._url("index.php?m=user&f=login&t=json")
        password = self.password or self.api_key
        if not password:
            raise ZenTaoClientError("未配置 ZENTAO_PASSWORD 或 ZENTAO_API_KEY")
        try:
            r = self._session.post(
                login_url,
                data={"account": self.account, "password": password},
                timeout=15,
            )
            r.raise_for_status()
            login_data = r.json()
        except requests.RequestException as e:
            raise ZenTaoClientError(f"登录失败: {e}") from e

        if login_data.get("status") == "fail" or login_data.get("status") == 0:
            raise ZenTaoClientError(login_data.get("message", login_data.get("msg", "登录失败")))
        self._logged_in = True
        logger.info("禅道传统 Session 登录成功")
        return True

    def login(self):
        """登录：v2 -> v1 -> 传统 Session。"""
        if not self.base_url or not self.account:
            raise ZenTaoClientError("未配置 ZENTAO_BASE_URL 或 ZENTAO_ACCOUNT")

        if self._use_legacy is True:
            self._legacy_login()
            return

        try:
            if self._try_v2_login():
                logger.info("禅道 REST v2 登录成功")
                return
        except ZenTaoClientError:
            raise

        try:
            if self._try_v1_login():
                return
        except ZenTaoClientError:
            raise

        logger.info("未检测到 REST v1/v2，改用传统 Session API")
        self._legacy_login()

    def _ensure_login(self):
        if not self._logged_in:
            self.login()

    def _clear_login(self):
        """清空登录状态（token 失效时调用，便于重试时重新登录）。"""
        self._logged_in = False
        self._token = None
        self._session.headers.pop("Token", None)

    def _is_auth_fail(self, status_code, data):
        """判断是否为认证/授权失败，需重登。"""
        if status_code == 401:
            return True
        if status_code == 403:
            return True
        if not isinstance(data, dict):
            return False
        if data.get("status") == "fail":
            msg = (data.get("message") or data.get("msg") or "").lower()
            if "token" in msg or "登录" in msg or "auth" in msg or "unauthorized" in msg:
                return True
        if status_code == 401 and data.get("error"):
            return True
        return False

    def _get_json(self, url, params=None, timeout=30):
        """GET 并解析 JSON，处理认证失败。"""
        resp = self._session.get(url, params=params, timeout=timeout)
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if self._is_auth_fail(resp.status_code, data):
            self._clear_login()
            raise ZenTaoAuthError("认证失效，请重新登录")
        resp.raise_for_status()
        if not isinstance(data, dict):
            data = {}
        return data

    @staticmethod
    def _v1_raise_if_error(data, default_msg):
        """v1 成功体无 status 字段，失败时为 {error: ...}。"""
        if "error" in data:
            err = data["error"]
            raise ZenTaoClientError(err if isinstance(err, str) else str(err))
        return data

    @staticmethod
    def _v2_raise_if_error(data, default_msg):
        if data.get("status") != "success":
            raise ZenTaoClientError(data.get("message", default_msg))

    def _paginate_v1_list(self, url, list_key, extra_params=None):
        """拉取 v1 分页列表（products / bugs 等）。"""
        limit = Config.ZENTAO_API_PAGE_LIMIT
        page = 1
        all_items = []
        base_params = dict(extra_params or {})
        base_params.setdefault("timeFormat", "local")

        while True:
            params = {**base_params, "limit": limit, "page": page}
            data = self._get_json(url, params=params)
            data = self._v1_raise_if_error(data, f"获取 {list_key} 失败")
            chunk = data.get(list_key) or []
            if not isinstance(chunk, list):
                chunk = list(chunk.values()) if isinstance(chunk, dict) else []
            all_items.extend(chunk)
            total = int(data.get("total") or 0)
            if not chunk:
                break
            if total and page * limit >= total:
                break
            if len(chunk) < limit:
                break
            page += 1

        return all_items

    def _v2_get_products(self):
        url = self._url("api.php/v2/products")
        data = self._get_json(url)
        self._v2_raise_if_error(data, "获取产品列表失败")
        products = data.get("products") or []
        return [{"id": str(p.get("id", "")), "name": p.get("name", "")} for p in products]

    def _v1_get_products(self):
        url = self._url("api.php/v1/products")
        products = self._paginate_v1_list(url, "products")
        result = []
        for p in products:
            pid = str(p.get("id", ""))
            name = p.get("name", "")
            result.append({"id": pid, "name": name})
            if pid:
                self._product_name_cache[pid] = name
        return result

    def _bug_list_params(self):
        return {
            "status": Config.ZENTAO_BUG_BROWSE_STATUS,
            "timeFormat": "local",
            "order": "id_desc",
        }

    def _v2_get_bugs_for_product(self, product_id):
        url = self._url(f"api.php/v2/products/{product_id}/bugs")
        limit = Config.ZENTAO_API_PAGE_LIMIT
        page = 1
        all_bugs = []
        while True:
            params = {**self._bug_list_params(), "limit": limit, "page": page}
            data = self._get_json(url, params=params)
            self._v2_raise_if_error(data, "获取 Bug 列表失败")
            chunk = data.get("bugs") or []
            all_bugs.extend(chunk)
            pager = data.get("pager") or {}
            total = int(data.get("total") or (pager.get("recTotal") if isinstance(pager, dict) else 0) or 0)
            if not chunk:
                break
            if total and page * limit >= total:
                break
            if len(chunk) < limit:
                break
            page += 1
        return all_bugs

    def _v1_get_bugs_for_product(self, product_id):
        url = self._url(f"api.php/v1/products/{product_id}/bugs")
        return self._paginate_v1_list(url, "bugs", extra_params=self._bug_list_params())

    def _legacy_get_products(self):
        url = self._url("index.php?m=product&f=getList&t=json")
        try:
            resp = self._session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException:
            return self._legacy_get_products_from_bugs()
        result = data.get("result")
        if result is None:
            return self._legacy_get_products_from_bugs()
        if isinstance(result, list):
            return [{"id": str(p.get("id", "")), "name": p.get("name", "")} for p in result]
        if isinstance(result, dict):
            return [{"id": str(k), "name": v} for k, v in result.items() if k and v]
        return self._legacy_get_products_from_bugs()

    def _legacy_get_products_from_bugs(self):
        url = self._url("index.php?m=bug&f=getList&t=json&productID=1&branch=0")
        resp = self._session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        result = data.get("result") or {}
        products = result.get("products") if isinstance(result, dict) else {}
        if not products:
            return [{"id": "1", "name": "默认产品"}]
        return [{"id": str(k), "name": v} for k, v in products.items()]

    def _legacy_get_bugs_for_product(self, product_id):
        url = self._url(f"index.php?m=bug&f=getList&t=json&productID={product_id}&branch=0")
        resp = self._session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == 0 or data.get("msg") == "error":
            raise ZenTaoClientError(data.get("msg", data.get("message", "获取 Bug 列表失败")))
        result = data.get("result")
        if not isinstance(result, dict):
            return []
        bugs = result.get("bugs") or []
        return [_normalize_bug(b) for b in bugs]

    def get_products(self):
        self._ensure_login()
        try:
            if self._api_version == "v1":
                return self._v1_get_products()
            if self._token:
                return self._v2_get_products()
            return self._legacy_get_products()
        except ZenTaoAuthError:
            self.login()
            if self._api_version == "v1":
                return self._v1_get_products()
            if self._token:
                return self._v2_get_products()
            return self._legacy_get_products()

    def get_bugs_for_product(self, product_id):
        self._ensure_login()
        pid = str(product_id)

        def _fetch():
            if self._api_version == "v1":
                raw = self._v1_get_bugs_for_product(pid)
            elif self._token:
                raw = self._v2_get_bugs_for_product(pid)
            else:
                return self._legacy_get_bugs_for_product(pid)
            product_name = self._product_name_cache.get(pid, "")
            normalized = []
            for b in raw:
                bug = _normalize_bug(b)
                if not bug["product"] and product_name:
                    bug["product"] = product_name
                normalized.append(bug)
            return normalized

        try:
            return _fetch()
        except ZenTaoAuthError:
            self.login()
            return _fetch()

    def get_bugs_since(self, since_iso_datetime=None, product_ids=None):
        self._ensure_login()
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

        return [b for b in all_bugs if bug_changed_since(b, since_iso_datetime)]

    def bug_view_url(self, bug_id):
        if Config.ZENTAO_URL_STYLE == "get":
            query = urlencode({"m": "bug", "f": "view", "bugID": bug_id})
            return self._url(f"index.php?{query}")
        return self._url(f"bug-view-{bug_id}.html")
