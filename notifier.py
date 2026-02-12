"""
轮询逻辑：从禅道拉取新/更新 Bug -> 去重 -> 推送飞书
"""
import json
import logging
import os
from datetime import datetime

from config import Config
from feishu_notifier import FeishuNotifier
from zentao_client import ZenTaoClient, ZenTaoClientError

logger = logging.getLogger(__name__)

# 东八区
TIME_FMT = "%Y-%m-%d %H:%M:%S"


def _now_iso():
    return datetime.now().strftime(TIME_FMT)


def load_state(state_file=None):
    """读取 state.json，返回 last_check_time（ISO 字符串）或 None。"""
    path = state_file or Config.STATE_FILE
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("last_check_time")
    except Exception as e:
        logger.warning("读取状态文件失败: %s", e)
        return None


def save_state(last_check_time, state_file=None):
    """写入 last_check_time 到 state.json。"""
    path = state_file or Config.STATE_FILE
    if not path:
        return
    try:
        dir_path = os.path.dirname(path)
        if dir_path and not os.path.isdir(dir_path):
            os.makedirs(dir_path, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"last_check_time": last_check_time}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("写入状态文件失败: %s", e)


def run_once(webhook_url=None, state_file=None):
    """
    执行一次：拉取自上次检查以来的 Bug，推送到飞书，更新状态。
    首次运行（无 state）仅写入当前时间，不推送历史 Bug。
    返回本轮推送的 Bug 数量。
    """
    state_file = state_file or Config.STATE_FILE
    since = load_state(state_file)
    is_first_run = since is None
    if is_first_run:
        since = _now_iso()
        logger.info("首次运行，仅记录检查时间 %s，不推送历史 Bug", since)
    product_ids = None
    if Config.ZENTAO_PRODUCT_IDS:
        product_ids = [x.strip() for x in Config.ZENTAO_PRODUCT_IDS.split(",") if x.strip()]

    client = ZenTaoClient()
    notifier = FeishuNotifier(webhook_url=webhook_url or Config.FEISHU_WEBHOOK_URL)

    if not notifier.webhook_url:
        logger.warning("未配置 FEISHU_WEBHOOK_URL，跳过推送")
        return 0

    try:
        client.login()
    except ZenTaoClientError as e:
        logger.error("禅道登录失败: %s", e)
        return 0

    try:
        bugs = client.get_bugs_since(since_iso_datetime=since, product_ids=product_ids)
    except ZenTaoClientError as e:
        logger.error("获取 Bug 列表失败: %s", e)
        return 0

    # 按 id 去重（同一 Bug 可能因 openedDate 与 lastEditedDate 都满足条件而出现两次）
    seen = set()
    unique_bugs = []
    for b in bugs:
        bid = b.get("id")
        if bid and bid not in seen:
            seen.add(bid)
            unique_bugs.append(b)

    pushed = 0
    for bug in unique_bugs:
        bid = bug.get("id", "")
        bug_url = client.bug_view_url(bid)
        for attempt in range(3):
            if notifier.send_bug_card(bug, bug_url, webhook_url=notifier.webhook_url):
                pushed += 1
                break
            if attempt < 2:
                logger.warning("飞书推送重试 %s/%s", attempt + 1, 2)

    now = _now_iso()
    save_state(now, state_file)
    logger.info("本轮检查完成，推送 %s 条 Bug，下次 since=%s", pushed, now)
    return pushed
