"""
飞书通知：文本 + 交互卡片（禅道 Bug）
"""
import logging

import requests

from config import Config

logger = logging.getLogger(__name__)


def _bug_card(bug, bug_url, header_color="blue"):
    """
    组装单条 Bug 的飞书卡片。
    bug: 禅道 Bug 对象（含 id, title, severity, status, openedBy, openedDate, product, module 等）
    bug_url: 禅道 Bug 详情页链接
    """
    bid = bug.get("id", "")
    title = (bug.get("title") or "无标题")[:80]
    severity = bug.get("severity") or "-"
    status = bug.get("status") or "-"
    opened_by = bug.get("openedBy") or "-"
    opened_date = bug.get("openedDate") or "-"
    product = bug.get("product") or "-"
    module = bug.get("module") or "-"
    if isinstance(module, dict):
        module = module.get("name", "-") if module else "-"
    if isinstance(product, dict):
        product = product.get("name", "-") if product else "-"

    content = (
        f"**严重程度**：{severity}\n"
        f"**状态**：{status}\n"
        f"**所属产品/模块**：{product} / {module}\n"
        f"**创建人**：{opened_by}\n"
        f"**创建时间**：{opened_date}"
    )
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"Bug #{bid} - {title}"},
            "template": header_color,
        },
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": content}},
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "查看 Bug"},
                        "type": "primary",
                        "url": bug_url,
                    }
                ],
            },
        ],
    }
    return card


class FeishuNotifier:
    """飞书通知器（文本 + Bug 卡片）"""

    def __init__(self, webhook_url=None):
        self.webhook_url = (webhook_url or Config.FEISHU_WEBHOOK_URL or "").strip() or None

    def send(self, message, webhook_url=None):
        """发送飞书文本消息"""
        url = (webhook_url or self.webhook_url or "").strip() or None
        if not url:
            logger.warning("未配置飞书 Webhook URL，跳过通知")
            return False
        try:
            payload = {"msg_type": "text", "content": {"text": message}}
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            if result.get("code") != 0:
                logger.error("飞书通知失败: %s", result.get("msg"))
                return False
            logger.info("飞书文本通知发送成功")
            return True
        except Exception as e:
            logger.error("发送飞书通知异常: %s", e, exc_info=True)
            return False

    def send_card(self, card, webhook_url=None):
        """发送飞书交互卡片。card 为 card 对象（不含 msg_type）。"""
        url = (webhook_url or self.webhook_url or "").strip() or None
        if not url:
            logger.warning("未配置飞书 Webhook URL，跳过卡片通知")
            return False
        try:
            payload = {"msg_type": "interactive", "card": card}
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            if result.get("code") != 0:
                logger.error("飞书卡片通知失败: %s", result.get("msg"))
                return False
            logger.info("飞书卡片通知发送成功")
            return True
        except Exception as e:
            logger.error("发送飞书卡片异常: %s", e, exc_info=True)
            return False

    def send_bug_card(self, bug, bug_url, webhook_url=None, header_color="blue"):
        """发送单条 Bug 卡片。"""
        card = _bug_card(bug, bug_url, header_color=header_color)
        return self.send_card(card, webhook_url=webhook_url)
