#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置加载器 — 统一读取接口

优先级：环境变量 > .env 文件 > config.py（本地开发）> 默认值

Docker 部署：只需提供 .env 文件（由 feishu_setup.py 自动写入，或手动填写）
本地部署：继续使用 config.py，无需任何改动
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 加载 .env 文件（如果存在）────────────────────────────────────────
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path, override=False)  # 不覆盖已有的系统环境变量
    except ImportError:
        pass  # dotenv 未安装时跳过，直接靠系统环境变量

# ── 读取 config.py 作为回退 ────────────────────────────────────────────
_cfg = None
try:
    import config as _cfg
except ImportError:
    pass


def _get(key: str, default=None):
    """读取配置：环境变量 > config.py > default"""
    val = os.environ.get(key)
    if val is not None:
        return val
    if _cfg is not None:
        return getattr(_cfg, key, default)
    return default


def _get_int(key: str, default: int = 0) -> int:
    val = _get(key, default)
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _get_list(key: str, default=None) -> list:
    """读取列表配置：支持 JSON 数组或逗号分隔字符串"""
    if default is None:
        default = []
    val = os.environ.get(key)
    if val is not None:
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        return [p.strip() for p in val.split(",") if p.strip()]
    if _cfg is not None:
        cfg_val = getattr(_cfg, key, default)
        if isinstance(cfg_val, list):
            return cfg_val
    return default


# ══════════════════════════════════════════════════════════════════════
# 飞书配置（必填）
# ══════════════════════════════════════════════════════════════════════
FEISHU_APP_ID = _get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = _get("FEISHU_APP_SECRET", "")
FEISHU_OPEN_ID = _get("FEISHU_OPEN_ID", "")
FEISHU_CHAT_ID = _get("FEISHU_CHAT_ID", "")

# ══════════════════════════════════════════════════════════════════════
# Telegram（可选）
# ══════════════════════════════════════════════════════════════════════
TELEGRAM_BOT_TOKEN = _get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = _get("TELEGRAM_CHAT_ID", "")

# ══════════════════════════════════════════════════════════════════════
# 启用平台列表
# ══════════════════════════════════════════════════════════════════════
ENABLED_PLATFORMS = _get_list("ENABLED_PLATFORMS", ["feishu"])

# ══════════════════════════════════════════════════════════════════════
# Alpha Vantage（可选）
# ══════════════════════════════════════════════════════════════════════
ALPHA_VANTAGE_API_KEY = _get("ALPHA_VANTAGE_API_KEY", "")
ALPHA_VANTAGE_BASE_URL = _get(
    "ALPHA_VANTAGE_BASE_URL", "https://www.alphavantage.co/query"
)
API_REQUEST_INTERVAL_SECONDS = _get_int("API_REQUEST_INTERVAL_SECONDS", 2)

# ══════════════════════════════════════════════════════════════════════
# 日志
# ══════════════════════════════════════════════════════════════════════
LOG_LEVEL = _get("LOG_LEVEL", "INFO")
LOG_FILE = _get("LOG_FILE", "secretary.log")

# ══════════════════════════════════════════════════════════════════════
# 调度配置
# ══════════════════════════════════════════════════════════════════════
PRICE_ALERT_INTERVAL_MINUTES = _get_int("PRICE_ALERT_INTERVAL_MINUTES", 5)
DAILY_DIGEST_HOUR = _get_int("DAILY_DIGEST_HOUR", 15)
DAILY_DIGEST_MINUTE = _get_int("DAILY_DIGEST_MINUTE", 30)
MORNING_REPORT_HOUR = _get_int("MORNING_REPORT_HOUR", 9)
MORNING_REPORT_MINUTE = _get_int("MORNING_REPORT_MINUTE", 0)
MONITOR_INTERVAL_MINUTES = _get_int("MONITOR_INTERVAL_MINUTES", 5)
