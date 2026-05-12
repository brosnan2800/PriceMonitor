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

from bot.adapters.feishu_adapter import CrossAppUserError
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
        # 恢复用户自定义推送时间
        self._restore_user_push_times()
        self._scheduler.start()
        logger.info("任务调度引擎启动")
        # 补发：NAS 时钟可能在开机时偏快，NTP 纠正后早报窗口已过
        # 如果在工作日 08:00-12:00 内启动，延迟 30 秒触发一次早报
        self._schedule_startup_morning_report()

    def stop(self) -> None:
        self._scheduler.shutdown(wait=False)
        logger.info("任务调度引擎停止")

    def _schedule_startup_morning_report(self) -> None:
        """
        NAS 定时开关机场景下，系统时钟可能在开机时偏快，NTP 修正后 APScheduler
        已将今天的早报调度到明天。此方法检测启动时间是否在工作日 08:00-12:00 窗口
        内，若是则注册一个 30 秒后执行的一次性早报任务来补发。
        """
        now = datetime.now()
        if now.weekday() >= 5:
            return
        t = now.hour * 60 + now.minute
        if not (8 * 60 <= t < 12 * 60):
            return
        from datetime import timedelta
        run_at = now + timedelta(seconds=30)
        self._scheduler.add_job(
            self._job_index_report_all,
            "date",
            run_date=run_at,
            id="startup_morning_report",
            replace_existing=True,
            misfire_grace_time=300,
        )
        logger.info(f"检测到工作日早晨启动，将于 {run_at.strftime('%H:%M:%S')} 补发早报")

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

    def update_alert_interval(self, minutes: int) -> None:
        """热更新价格预警检查间隔（无需重启）"""
        minutes = max(1, minutes)
        self._scheduler.reschedule_job(
            "builtin_price_alert",
            trigger=CronTrigger(minute=f"*/{minutes}")
        )
        logger.info(f"价格预警间隔已更新为 {minutes} 分钟")

    # ── 内置任务 ──────────────────────────────────────────────────────

    def _register_builtin_jobs(self) -> None:
        import config_loader as cfg

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

    def _restore_user_push_times(self) -> None:
        """启动时从 users.settings 恢复各用户的个性化推送时间"""
        users = self._get_all_users()
        for user in users:
            uid = user["user_id"]
            try:
                settings = db.get_user_settings(uid)
                morning_time = settings.get("morning_time")
                digest_time  = settings.get("digest_time")
                if morning_time or digest_time:
                    self.reschedule_user_push(uid, morning_time, digest_time)
            except Exception as e:
                logger.warning(f"恢复用户 {uid} 推送时间失败: {e}")

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
            "price_alert":   self._make_price_alert_job,
            "index_report":  self._make_index_report_job,
            "announcement":  self._make_announcement_job,
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

            # 收集所有有新公告的股票
            all_results: List[Dict] = []  # [{symbol, name, announcements}]
            for symbol in symbols:
                anns = get_stock_announcements(symbol, important_only=True)
                if anns:
                    name = anns[0].get("name", symbol)
                    all_results.append({"symbol": symbol, "name": name, "announcements": anns})

            # 没有任何新公告 → 静默跳过
            if not all_results:
                db.update_task_last_run(task["id"])
                return

            # 所有股票合并一张卡，去重推送
            content_hash = hashlib.md5(
                json.dumps([
                    a["title"]
                    for r in all_results
                    for a in r["announcements"]
                ]).encode()
            ).hexdigest()
            if not db.already_pushed(user_id, content_hash, within_hours=24):
                from bot.formatters.cards import multi_announcement_card
                card = multi_announcement_card(all_results)
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

    # ── 内置任务实现 ──────────────────────────────────────────────────

    def _job_daily_digest_all(self) -> None:
        """全量用户收盘日报（内置）；有个人专属 job 的用户跳过，避免重复推送"""
        users = self._get_all_users()
        for user in users:
            uid = user["user_id"]
            # 如果用户已设置专属 digest job，跳过（该 job 自行处理）
            if self._scheduler.get_job(f"user_digest_{uid}"):
                continue
            platform = user.get("platform", "feishu")
            adapter = self.adapters.get(platform)
            if not adapter:
                continue
            try:
                self._send_daily_digest(adapter, uid)
            except CrossAppUserError as e:
                logger.warning(f"日报跳过（跨应用账号）{uid}: {e}")
                self._disable_cross_app_user(uid)
            except Exception as e:
                logger.error(f"日报推送失败 {uid}: {e}")

    def _job_index_report_all(self) -> None:
        """全量用户指数早报（内置）；有个人专属 job 的用户跳过，避免重复推送"""
        users = self._get_all_users()
        for user in users:
            uid = user["user_id"]
            if self._scheduler.get_job(f"user_morning_{uid}"):
                continue
            platform = user.get("platform", "feishu")
            adapter = self.adapters.get(platform)
            if not adapter:
                continue
            try:
                self._send_index_report(adapter, uid)
            except CrossAppUserError as e:
                logger.warning(f"早报跳过（跨应用账号）{uid}: {e}")
                self._disable_cross_app_user(uid)
            except Exception as e:
                logger.error(f"早报推送失败 {uid}: {e}")

    def _disable_cross_app_user(self, user_id: str) -> None:
        """将跨应用账号标记为 disabled，后续不再推送"""
        try:
            settings = db.get_user_settings(user_id)
            settings["disabled"] = True
            db.update_user_settings(user_id, settings)
            logger.info(f"已禁用跨应用账号 {user_id}")
        except Exception as e:
            logger.error(f"禁用用户失败 {user_id}: {e}")

    @staticmethod
    def _is_trading_time() -> bool:
        """判断当前是否在 A 股交易时段（工作日 9:25-11:35 / 12:55-15:05，含缓冲）"""
        now = datetime.now()
        if now.weekday() >= 5:  # 周六/周日
            return False
        t = now.hour * 60 + now.minute
        return (9 * 60 + 25 <= t <= 11 * 60 + 35) or (12 * 60 + 55 <= t <= 15 * 60 + 5)

    def _job_check_price_alerts(self) -> None:
        """检查所有用户价格预警（仅在 A 股交易时段运行）"""
        if not self._is_trading_time():
            return

        all_alerts = db.get_all_alerts()
        for alert in all_alerts:
            try:
                self._check_single_alert(alert)
            except Exception as e:
                logger.error(f"预警检查失败 alert#{alert['id']}: {e}")

    def _check_single_alert(self, alert: Dict) -> None:
        """检查并触发单条价格预警"""
        user_id = alert["user_id"]
        symbol = alert["symbol"]
        condition = alert["condition"]
        threshold = float(alert["threshold"])
        in_trigger = bool(alert.get("in_trigger", 0))

        platform = self._get_user_platform(user_id)
        adapter = self.adapters.get(platform)
        if not adapter or not symbol:
            return

        data = auto_quote(symbol)
        if not data:
            return

        price = data.get("price", 0)
        change_pct = data.get("change_pct", 0)
        name = data.get("name", symbol)

        # 判断当前是否满足触发条件
        meets_condition = False
        if condition == "above":
            meets_condition = price > threshold
        elif condition == "below":
            meets_condition = price < threshold
        elif condition == "change_pct":
            if threshold >= 0:
                meets_condition = change_pct >= threshold
            else:
                meets_condition = change_pct <= threshold

        # 用户设置：触发后是否等待恢复再重推
        settings = db.get_user_settings(user_id)
        pause_until_normal = settings.get("alert_pause_until_normal", True)

        if pause_until_normal:
            if in_trigger:
                # 已触发状态：检查是否已回归正常区间
                if not meets_condition:
                    db.reset_alert_triggered(alert["id"], user_id)
                    logger.debug(f"预警 #{alert['id']} {symbol} 已回归正常，重置触发状态")
                return  # 无论是否恢复，本轮都不推
            # 未触发：正常判断
            if not meets_condition:
                return
            # 触发：推送并标记
            msg, card = self._build_alert_message(name, symbol, condition, threshold, price, change_pct, alert["id"], show_ack=True)
            adapter.send_card(user_id, card)
            db.set_alert_triggered(alert["id"], user_id)
        else:
            # 旧逻辑：时间冷却（每小时最多一次），不显示「知道了」按钮
            if not meets_condition:
                return
            msg, card = self._build_alert_message(name, symbol, condition, threshold, price, change_pct, alert["id"], show_ack=False)
            content_hash = hashlib.md5(
                f"{symbol}{condition}{threshold}{datetime.now().strftime('%Y%m%d%H')}".encode()
            ).hexdigest()
            if not db.already_pushed(user_id, content_hash, within_hours=2):
                adapter.send_card(user_id, card)
                db.log_push(user_id, alert["id"], content_hash)

    @staticmethod
    def _build_alert_message(name: str, symbol: str, condition: str,
                              threshold: float, price: float, change_pct: float,
                              alert_id: int, show_ack: bool = True):
        """构建预警推送卡片，show_ack=True 时含「知道了」按钮"""
        from bot.formatters.cards import OutgoingCard, CardButton
        cond_map = {"above": f"突破 {threshold}", "below": f"跌破 {threshold}",
                    "change_pct": f"涨跌幅达 {change_pct:.2f}%"}
        cond_str = cond_map.get(condition, "")
        if condition == "change_pct":
            price_str = f"当前涨跌幅 **{change_pct:+.2f}%**"
        else:
            price_str = f"当前价格 **{price}**"
        content = f"{price_str}，触发预设条件：{cond_str}"
        msg = f"🚨 {name}({symbol}) {cond_str}"
        buttons = []
        footer = None
        if show_ack:
            buttons = [CardButton("✅ 知道了，暂停提醒", "ack_alert", {"alert_id": alert_id})]
            footer = "点击「知道了」后，等价格回归正常区间才会再次提醒"
        card = OutgoingCard(
            title=f"🚨 价格预警触发：{name}（{symbol}）",
            content=content,
            buttons=buttons,
            footer=footer,
        )
        return msg, card

    # ── 推送内容构建 ──────────────────────────────────────────────────

    def _send_daily_digest(self, adapter: "BaseAdapter", user_id: str) -> None:
        settings = db.get_user_settings(user_id)
        if settings.get("quiet_mode"):
            return

        # 晚报固定内容：关注指数 + 自选收盘价，不调 AV（省配额给早报用）
        index_data = get_index_quotes()

        watchlist_items = db.get_watchlist(user_id)
        watchlist_quotes = []
        for item in watchlist_items:
            q = auto_quote(item["symbol"])
            if q:
                watchlist_quotes.append(q)

        card = daily_digest_card(index_data, watchlist_quotes, [], [])
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
        """获取所有有效用户（排除测试账号和跨应用已禁用账号）"""
        try:
            import sqlite3
            import json as _json
            from data.db import DB_PATH
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM users").fetchall()
            conn.close()
            result = []
            for r in rows:
                user = dict(r)
                if user["user_id"] == "test_user_001":
                    continue
                try:
                    settings = _json.loads(user.get("settings") or "{}")
                except Exception:
                    settings = {}
                if settings.get("disabled"):
                    continue
                result.append(user)
            return result
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

    def reschedule_user_push(self, user_id: str,
                             morning_time: Optional[str] = None,
                             digest_time: Optional[str] = None) -> None:
        """
        为单个用户热更新专属推送时间（无需重启）。
        morning_time / digest_time: "HH:MM"，None 表示不修改该项。
        """
        def _make_send_fn(send_fn, uid: str):
            def job():
                settings = db.get_user_settings(uid)
                if settings.get("quiet_mode"):
                    return
                platform = self._get_user_platform(uid)
                adapter = self.adapters.get(platform)
                if adapter:
                    send_fn(adapter, uid)
            return job

        if morning_time:
            h, m = map(int, morning_time.split(":"))
            job_id = f"user_morning_{user_id}"
            self._scheduler.add_job(
                _make_send_fn(self._send_index_report, user_id),
                CronTrigger(hour=h, minute=m, day_of_week="mon-fri"),
                id=job_id,
                replace_existing=True,
            )
            logger.info(f"用户 {user_id} 早报已调整为 {morning_time}")

        if digest_time:
            h, m = map(int, digest_time.split(":"))
            job_id = f"user_digest_{user_id}"
            self._scheduler.add_job(
                _make_send_fn(self._send_daily_digest, user_id),
                CronTrigger(hour=h, minute=m, day_of_week="mon-fri"),
                id=job_id,
                replace_existing=True,
            )
            logger.info(f"用户 {user_id} 日报已调整为 {digest_time}")


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

    av_needed = modules & {"fx", "commodity", "us_news"}
    if av_needed:
        try:
            from data.sources.alphavantage_source import (
                get_fx_rates_batch, get_commodities_batch, get_news_sentiment,
                is_configured, is_quota_exhausted,
            )
            if is_configured():
                if is_quota_exhausted():
                    extra["av_quota_exhausted"] = True
                else:
                    if "fx" in modules:
                        fx_list = get_fx_rates_batch() or []
                        extra["fx"] = fx_list
                        if is_quota_exhausted():
                            extra["av_quota_exhausted"] = True
                    if "commodity" in modules and not extra.get("av_quota_exhausted"):
                        comm_list = get_commodities_batch(["WTI", "BRENT", "NATURAL_GAS"]) or []
                        extra["commodity"] = comm_list
                        if is_quota_exhausted():
                            extra["av_quota_exhausted"] = True
                    if "us_news" in modules and not extra.get("av_quota_exhausted"):
                        # tickers 从用户自选股动态取（_fetch_extra_modules 为全局函数，无 user_id）
                        # 传空表示查全市场情绪
                        news_list = get_news_sentiment(tickers=[]) or []
                        extra["us_news"] = news_list
                        if is_quota_exhausted():
                            extra["av_quota_exhausted"] = True
        except Exception as e:
            logger.warning(f"Alpha Vantage 模块拉取失败: {e}")

    return extra
