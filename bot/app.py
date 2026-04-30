#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主入口：启动飞书/Telegram 适配器 + APScheduler 调度引擎

启动方式：
  python -m bot.app              # 生产模式（飞书为主）
  python -m bot.app --telegram   # 仅启动 Telegram
  python -m bot.app --all        # 全渠道

飞书 Webhook 需要公网可访问，本地调试推荐使用 ngrok 或 frp
"""

import argparse
import logging
import signal
import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db import init_db
from bot.handlers.commands import CommandHandler
from bot.scheduler import TaskScheduler

logger = logging.getLogger(__name__)


def _setup_logging():
    try:
        import config as cfg
        level = getattr(logging, getattr(cfg, "LOG_LEVEL", "INFO"))
        log_file = getattr(cfg, "LOG_FILE", "secretary.log")
    except ImportError:
        level = logging.INFO
        log_file = "secretary.log"

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8")
        ]
    )


def _load_config():
    try:
        import config as cfg
        return cfg
    except ImportError:
        logger.error("找不到 config.py，请先运行: cp config.example.py config.py")
        sys.exit(1)


def build_feishu_adapter(cfg):
    """构建飞书适配器（WebSocket 长连接模式，无需公网 IP）"""
    app_id = getattr(cfg, "FEISHU_APP_ID", "")
    app_secret = getattr(cfg, "FEISHU_APP_SECRET", "")
    if not app_id or not app_secret or app_id.startswith("your_"):
        logger.warning("飞书未配置，跳过飞书适配器")
        return None

    from bot.adapters.feishu_adapter import FeishuAdapter
    return FeishuAdapter(app_id=app_id, app_secret=app_secret)


def build_telegram_adapter(cfg):
    """构建 Telegram 适配器"""
    token = getattr(cfg, "TELEGRAM_BOT_TOKEN", "")
    if not token or token.startswith("YOUR_"):
        logger.warning("Telegram 未配置，跳过 Telegram 适配器")
        return None

    from bot.adapters.telegram_adapter import TelegramAdapter
    return TelegramAdapter(bot_token=token)


def main():
    _setup_logging()
    parser = argparse.ArgumentParser(description="综合秘书机器人")
    parser.add_argument("--feishu", action="store_true", help="仅启动飞书（默认）")
    parser.add_argument("--telegram", action="store_true", help="仅启动 Telegram")
    parser.add_argument("--all", action="store_true", help="启动全部渠道")
    parser.add_argument("--no-scheduler", action="store_true", help="不启动定时任务")
    args = parser.parse_args()

    # 初始化数据库
    logger.info("初始化数据库...")
    init_db()

    cfg = _load_config()

    # 确定启动哪些渠道
    enabled = getattr(cfg, "ENABLED_PLATFORMS", ["feishu"])
    if args.all:
        enabled = ["feishu", "telegram"]
    elif args.telegram:
        enabled = ["telegram"]
    elif args.feishu:
        enabled = ["feishu"]

    adapters = {}

    # 构建启用的适配器
    if "feishu" in enabled:
        adapter = build_feishu_adapter(cfg)
        if adapter:
            adapters["feishu"] = adapter

    if "telegram" in enabled:
        adapter = build_telegram_adapter(cfg)
        if adapter:
            adapters["telegram"] = adapter

    if not adapters:
        logger.error("没有可用的渠道适配器，请检查 config.py 配置")
        sys.exit(1)

    # 为每个适配器绑定指令处理器
    handlers = {}
    for platform, adapter in adapters.items():
        handlers[platform] = CommandHandler(adapter)

    def on_message(msg):
        """统一消息入口"""
        handler = handlers.get(msg.platform)
        if handler:
            try:
                handler.handle(msg)
            except Exception as e:
                logger.error(f"消息处理异常 [{msg.platform}] {msg.user_id}: {e}", exc_info=True)

    # 启动调度引擎
    scheduler = None
    if not args.no_scheduler:
        scheduler = TaskScheduler(adapters)
        scheduler.start()

    # 启动所有适配器
    for platform, adapter in adapters.items():
        logger.info(f"启动渠道: {platform}")
        adapter.start(on_message)

    logger.info(f"✅ 综合秘书已启动 | 渠道: {list(adapters.keys())}")

    # 优雅退出
    def _shutdown(sig, frame):
        logger.info("收到退出信号，正在关闭...")
        if scheduler:
            scheduler.stop()
        for adapter in adapters.values():
            adapter.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # 主线程保持运行（飞书 Webhook Flask 服务在子线程中）
    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        _shutdown(None, None)


if __name__ == "__main__":
    main()
