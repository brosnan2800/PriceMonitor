#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
APScheduler 任务调度引擎
替代原有的 time.sleep 循环，支持 cron 表达式

内置任务：
  - 工作日15:30 每日收盘日报
  - 每日09:00 指数早报
  - 每5分钟 价格预警检查

用户自定义任务从数据库动态加载
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

if TYPE_CHECKING:
    from bot.adapters.base import BaseAdapter

from bot.formatters.cards import (
    daily_digest_card, announcement_card,
    morning_modules_card, news_sentiment_card, macro_report_card,
    DEFAULT_MORNING_MODULES, DEFAULT_DAILY_MODULES,
)
from data import db
from data.sources.akshare_source import (
    auto_quote, get_index_quotes, get_stock_announcements
)

logger = logging.getLogger(__name__)


class TaskScheduler:
    """任务调度引擎"""

    _instance: Optional["TaskScheduler"] = None

    @classmethod
    def get_instance(cls) -> Optional["TaskScheduler"]:
        return cls._instance

    def __init__(self, adapters: Dict[str, "BaseAdapter"]):
        """
        adapters: {"feishu": FeishuAdapter实例, "telegram": TelegramAdapter实例}
        """
        self.adapters = adapters
        self._scheduler = BackgroundScheduler(
            timezone="Asia/Shanghai",
            job_defaults={"coalesce": True, "max_instances": 1}
        )
        TaskScheduler._instance = self

    def start(self) -> None:
        # 内置系统任务
        self._register_builtin_jobs()
        # 从数据库加载用户自定义任务
        self._load_user_jobs()
        self._scheduler.start()
        logger.info("任务调度引擎启动")

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
        logger.info("任务调度引擎停止")

    def reload_user_jobs(self) -> None:
        """重新加载用户任务（新建/删除任务后调用）"""
        for job in self._scheduler.get_jobs():
            if job.id.startswith("user_task_"):
                self._scheduler.remove_job(job.id)
        self._load_user_jobs()

    def register_task_by_id(self, task_id: int) -> None:
        """热注册单个新任务（用户新建任务后立即生效，无需重启）"""
        tasks = db.get_all_enabled_tasks()
        task = next((t for t in tasks if t["id"] == task_id), None)
        if task:
            self._register_task(task)
            logger.info(f"热注册用户任务 #{task_id}")

    # ── 内置任务 ──────────────────────────────────────────────────────

    def _register_builtin_jobs(self) -> None:
        try:
            import config as cfg
        except ImportError:
            cfg = None

        alert_min = getattr(cfg, "PRICE_ALERT_INTERVAL_MINUTES", 5)
        digest_h  = getattr(cfg, "DAILY_DIGEST_HOUR", 15)
        digest_m  = getattr(cfg, "DAILY_DIGEST_MINUTE", 30)
        morning_h = getattr(cfg, "MORNING_REPORT_HOUR", 9)
        morning_m = getattr(cfg, "MORNING_REPORT_MINUTE", 0)

        # 工作日收盘日报
        self._scheduler.add_job(
            self._job_daily_digest_all,
            CronTrigger(hour=digest_h, minute=digest_m, day_of_week="mon-fri"),
            id="builtin_daily_digest",
            replace_existing=True
        )
        # 工作日早报
        self._scheduler.add_job(
            self._job_index_report_all,
            CronTrigger(hour=morning_h, minute=morning_m, day_of_week="mon-fri"),
            id="builtin_index_morning",
            replace_existing=True
        )
        # 价格预警（可配置间隔）
        self._scheduler.add_job(
            self._job_check_price_alerts,
            CronTrigger(minute=f"*/{max(1, alert_min)}"),
            id="builtin_price_alert",
            replace_existing=True
        )
        logger.info(f"内置定时任务已注册（预警每{alert_min}分钟，日报{digest_h}:{digest_m:02d}，早报{morning_h}:{morning_m:02d}）")

    # ── 用户自定义任务 ────────────────────────────────────────────────

    def _load_user_jobs(self) -> None:
        tasks = db.get_all_enabled_tasks()
        for task in tasks:
            self._register_task(task)
        logger.info(f"已加载 {len(tasks)} 个用户任务")

    def _register_task(self, task: Dict) -> None:
        job_id = f"user_task_{task['id']}"
        task_type = task.get("task_type", "")
        cron_expr = task.get("cron_expr", "0 15 * * 1-5")

        # 将 cron 字符串解析为 CronTrigger
        try:
            parts = cron_expr.split()
            trigger = CronTrigger(
                minute=parts[0], hour=parts[1],
                day=parts[2], month=parts[3], day_of_week=parts[4]
            )
        except Exception as e:
            logger.error(f"无效 cron 表达式 {cron_expr}: {e}")
            return

        handler_map = {
            "daily_report":  self._make_daily_report_job,
            "announcement":  self._make_announcement_job,
            "price_alert":   self._make_price_alert_job,
            "index_report":  self._make_index_report_job,
            "us_news":       self._make_us_news_job,
            "macro_report":  self._make_macro_report_job,
        }

        make_fn = handler_map.get(task_type)
        if not make_fn:
            logger.warning(f"未知任务类型: {task_type}")
            return

        job_fn = make_fn(task)
        self._scheduler.add_job(
            job_fn, trigger, id=job_id, replace_existing=True
        )

    # ── 任务工厂 ──────────────────────────────────────────────────────

    def _make_daily_report_job(self, task: Dict) -> Callable:
        def job():
            user_id = task["user_id"]
            platform = self._get_user_platform(user_id)
            adapter = self.adapters.get(platform)
            if not adapter:
                return
            self._send_daily_digest(adapter, user_id)
            db.update_task_last_run(task["id"])
        return job

    def _make_announcement_job(self, task: Dict) -> Callable:
        def job():
            user_id = task["user_id"]
            config = task.get("config", {})
            symbols = config.get("symbols", [])
            platform = self._get_user_platform(user_id)
            adapter = self.adapters.get(platform)
            if not adapter or not symbols:
                return
            for symbol in symbols:
                anns = get_stock_announcements(symbol, important_only=True)
                if anns:
                    name = anns[0].get("name", symbol) if anns else symbol
                    card = announcement_card(symbol, name, anns)
                    content_hash = hashlib.md5(
                        json.dumps([a["title"] for a in anns]).encode()
                    ).hexdigest()
                    if not db.already_pushed(user_id, content_hash, within_hours=24):
                        adapter.send_card(user_id, card)
                        db.log_push(user_id, task["id"], content_hash)
            db.update_task_last_run(task["id"])
        return job

    def _make_price_alert_job(self, task: Dict) -> Callable:
        def job():
            user_id = task["user_id"]
            config = task.get("config", {})
            symbol = config.get("symbol", "")
            condition = config.get("condition", "change_pct")
            threshold = float(config.get("threshold", 5.0))

            platform = self._get_user_platform(user_id)
            adapter = self.adapters.get(platform)
            if not adapter or not symbol:
                return

            data = auto_quote(symbol)
            if not data:
                return

            triggered = False
            price = data.get("price", 0)
            change_pct = data.get("change_pct", 0)

            if condition == "above" and price > threshold:
                triggered = True
                msg = f"🚨 {data.get('name', symbol)} 价格 {price} 已突破 {threshold}"
            elif condition == "below" and price < threshold:
                triggered = True
                msg = f"🚨 {data.get('name', symbol)} 价格 {price} 已跌破 {threshold}"
            elif condition == "change_pct":
                if threshold >= 0 and change_pct >= threshold:
                    triggered = True
                    msg = f"🚨 {data.get('name', symbol)} 上涨 {change_pct:.2f}%，超过阈值 {threshold}%"
                elif threshold < 0 and change_pct <= threshold:
                    triggered = True
                    msg = f"🚨 {data.get('name', symbol)} 下跌 {abs(change_pct):.2f}%，超过阈值 {abs(threshold)}%"

            if triggered:
                content_hash = hashlib.md5(
                    f"{symbol}{condition}{threshold}{datetime.now().strftime('%Y%m%d%H')}".encode()
                ).hexdigest()
                # 冷却2小时内不重复推送
                if not db.already_pushed(user_id, content_hash, within_hours=2):
                    adapter.send_text(user_id, msg)
                    db.log_push(user_id, task["id"], content_hash)

            db.update_task_last_run(task["id"])
        return job

    def _make_index_report_job(self, task: Dict) -> Callable:
        def job():
            user_id = task["user_id"]
            platform = self._get_user_platform(user_id)
            adapter = self.adapters.get(platform)
            if not adapter:
                return
            self._send_index_report(adapter, user_id)
            db.update_task_last_run(task["id"])
        return job

    def _make_us_news_job(self, task: Dict) -> Callable:
        def job():
            user_id = task["user_id"]
            platform = self._get_user_platform(user_id)
            adapter = self.adapters.get(platform)
            if not adapter:
                return
            try:
                from data.sources.alphavantage_source import (
                    get_news_sentiment, is_configured,
                )
                if not is_configured():
                    adapter.send_text(user_id, "⚠️ Alpha Vantage key 未配置，无法获取新闻情绪")
                    return
                cfg = json.loads(task.get("config") or "{}")
                tickers = cfg.get("tickers", [])
                items = get_news_sentiment(tickers) or []
                card = news_sentiment_card(items, tickers)
                adapter.send_card(user_id, card)
                db.update_task_last_run(task["id"])
            except Exception as e:
                logger.error(f"美股新闻任务失败 task#{task['id']}: {e}")
        return job

    def _make_macro_report_job(self, task: Dict) -> Callable:
        def job():
            user_id = task["user_id"]
            platform = self._get_user_platform(user_id)
            adapter = self.adapters.get(platform)
            if not adapter:
                return
            try:
                from data.sources.alphavantage_source import (
                    get_macro_summary, is_configured,
                )
                if not is_configured():
                    adapter.send_text(user_id, "⚠️ Alpha Vantage key 未配置，无法获取宏观数据")
                    return
                data = get_macro_summary() or []
                card = macro_report_card(data)
                adapter.send_card(user_id, card)
                db.update_task_last_run(task["id"])
            except Exception as e:
                logger.error(f"宏观指标任务失败 task#{task['id']}: {e}")
        return job

    # ── 内置任务实现 ──────────────────────────────────────────────────

    def _job_daily_digest_all(self) -> None:
        """全量用户收盘日报（内置）"""
        users = self._get_all_users()
        for user in users:
            platform = user.get("platform", "feishu")
            adapter = self.adapters.get(platform)
            if not adapter:
                continue
            try:
                self._send_daily_digest(adapter, user["user_id"])
            except Exception as e:
                logger.error(f"日报推送失败 {user['user_id']}: {e}")

    def _job_index_report_all(self) -> None:
        """全量用户指数早报（内置）"""
        users = self._get_all_users()
        for user in users:
            platform = user.get("platform", "feishu")
            adapter = self.adapters.get(platform)
            if not adapter:
                continue
            try:
                self._send_index_report(adapter, user["user_id"])
            except Exception as e:
                logger.error(f"早报推送失败 {user['user_id']}: {e}")

    def _job_check_price_alerts(self) -> None:
        """检查所有用户价格预警"""
        tasks = db.get_all_enabled_tasks()
        for task in tasks:
            if task.get("task_type") == "price_alert":
                try:
                    job_fn = self._make_price_alert_job(task)
                    job_fn()
                except Exception as e:
                    logger.error(f"预警检查失败 task#{task['id']}: {e}")

    # ── 推送内容构建 ──────────────────────────────────────────────────

    def _send_daily_digest(self, adapter: "BaseAdapter", user_id: str) -> None:
        settings = db.get_user_settings(user_id)
        if settings.get("quiet_mode"):
            return

        modules = set(settings.get("daily_modules", list(DEFAULT_DAILY_MODULES)))

        # 指数数据（所有模块基础）
        index_data = get_index_quotes()

        # 自选股
        watchlist_items = db.get_watchlist(user_id)
        watchlist_quotes = []
        for item in watchlist_items:
            q = auto_quote(item["symbol"])
            if q:
                watchlist_quotes.append(q)

        # 公告：仅推送有自选的用户
        announcements = []
        for item in watchlist_items[:3]:
            anns = get_stock_announcements(item["symbol"], limit=2, important_only=True)
            announcements.extend(anns)

        # 动态模块
        extra_modules = _fetch_extra_modules(modules)

        card = daily_digest_card(index_data, watchlist_quotes, announcements, [], extra_modules)
        content_hash = hashlib.md5(
            f"{user_id}{datetime.now().strftime('%Y%m%d%H')}".encode()
        ).hexdigest()
        if not db.already_pushed(user_id, content_hash, within_hours=6):
            adapter.send_card(user_id, card)
            db.log_push(user_id, None, content_hash)

    def _send_index_report(self, adapter: "BaseAdapter", user_id: str) -> None:
        settings = db.get_user_settings(user_id)
        if settings.get("quiet_mode"):
            return

        modules = set(settings.get("morning_modules", list(DEFAULT_MORNING_MODULES)))

        index_data = get_index_quotes()
        extra_modules = _fetch_extra_modules(modules)

        card = daily_digest_card(index_data, [], [], [], extra_modules)
        card.title = f"🌅 指数早报 · {datetime.now().strftime('%m/%d')}"
        adapter.send_card(user_id, card)

    # ── 工具方法 ──────────────────────────────────────────────────────

    def _get_user_platform(self, user_id: str) -> str:
        user = db.get_user(user_id)
        return user.get("platform", "feishu") if user else "feishu"

    def _get_all_users(self) -> List[Dict]:
        """获取所有用户（简单实现）"""
        try:
            import sqlite3
            from data.db import DB_PATH
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM users").fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"获取用户列表失败: {e}")
            return []

    def add_user_task(self, task: Dict) -> None:
        """动态添加新任务（用户通过 /newtask 创建后调用）"""
        self._register_task(task)

    def remove_user_task(self, task_id: int) -> None:
        """动态移除任务"""
        job_id = f"user_task_{task_id}"
        if self._scheduler.get_job(job_id):
            self._scheduler.remove_job(job_id)


# ── 模块数据拉取 ───────────────────────────────────────────────────────

def _fetch_extra_modules(modules: set) -> Dict:
    """
    根据用户选择的模块集合拉取对应数据。
    腾讯财经模块由 _send_index_report/_send_daily_digest 的 index_data 直接处理；
    此函数负责 crypto / fx / commodity 的补充数据。
    """
    extra: Dict = {}

    if "crypto" in modules:
        try:
            from data.sources.akshare_source import get_crypto_quote
            crypto_list = []
            for symbol in ["BTC", "ETH"]:
                q = get_crypto_quote(symbol)
                if q:
                    crypto_list.append(q)
            extra["crypto"] = crypto_list
        except Exception as e:
            logger.warning(f"crypto 模块拉取失败: {e}")

    av_needed = modules & {"fx", "commodity"}
    if av_needed:
        try:
            from data.sources.alphavantage_source import (
                get_fx_rates_batch, get_commodities_batch, is_configured,
            )
            if is_configured():
                if "fx" in modules:
                    # get_fx_rates_batch returns List[Dict] with rate/name fields
                    fx_list = get_fx_rates_batch() or []
                    extra["fx"] = fx_list
                if "commodity" in modules:
                    # get_commodities_batch returns List[Dict] with name/price/unit fields
                    comm_list = get_commodities_batch(["WTI", "BRENT", "NATURAL_GAS"]) or []
                    extra["commodity"] = comm_list
        except Exception as e:
            logger.warning(f"Alpha Vantage 模块拉取失败: {e}")

    return extra
