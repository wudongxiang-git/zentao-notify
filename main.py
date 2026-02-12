"""
zentao-notify 入口：常驻轮询或单次执行
"""
import argparse
import logging
import sys
import time

from config import Config
from notifier import run_once
from zentao_client import ZenTaoClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="禅道 Bug 推送到飞书群")
    parser.add_argument(
        "--once",
        action="store_true",
        help="只执行一次后退出（适合 cron）",
    )
    parser.add_argument(
        "--webhook",
        type=str,
        default=None,
        help="飞书 Webhook URL（覆盖环境变量 FEISHU_WEBHOOK_URL）",
    )
    args = parser.parse_args()

    if args.once:
        run_once(webhook_url=args.webhook)
        return

    # 常驻轮询（复用同一客户端，避免每轮重复登录）
    interval = max(60, Config.POLL_INTERVAL)
    logger.info("常驻轮询模式，间隔 %s 秒", interval)
    client = ZenTaoClient()
    while True:
        try:
            run_once(webhook_url=args.webhook, client=client)
        except Exception as e:
            logger.error("本轮执行异常: %s", e, exc_info=True)
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("已退出")
            break


if __name__ == "__main__":
    main()
