#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指令处理器
处理所有 /command 指令和按钮回调
"""

import json
import logging
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from bot.adapters.base import BaseAdapter, IncomingMessage

from bot.formatters.cards import (
    help_card, menu_card, quote_card, quote_input_card, add_input_card,
    watchlist_card, tasks_card,
    newtask_type_card, newtask_time_card, newtask_announcement_card,
    announcement_card, settings_card,
    alert_setup_card, alert_input_card,
    morning_modules_card, DEFAULT_MORNING_MODULES, DEFAULT_DAILY_MODULES,
)
from data import db
from data.sources.akshare_source import auto_quote, search_stock, _CRYPTO_MAP, _GLOBAL_INDEX_MAP

logger = logging.getLogger(__name__)

# 不需要名称搜索的代码集合（加密货币 + 全球指数别名）
_SKIP_SEARCH = set(_CRYPTO_MAP.keys()) | set(_GLOBAL_INDEX_MAP.keys())


def get_watchlist_quotes(user_id: str) -> dict:
    """批量查询自选列表行情"""
    from data.sources.akshare_source import auto_quote as aq
    items = db.get_watchlist(user_id)
    result = {}
    for item in items:
        q = aq(item["symbol"])
        if q:
            result[item["symbol"]] = q
    return result


class CommandHandler:
    """统一指令处理器（平台无关）"""

    def __init__(self, adapter: "BaseAdapter"):
        self.adapter = adapter
        # 等待用户输入的挂起状态 {user_id: {type, symbol, name, cond}}
        self._pending_input: Dict[str, Dict] = {}

    def handle(self, msg: "IncomingMessage") -> None:
        """分发处理入站消息"""
        # 确保用户存在
        db.upsert_user(msg.user_id, msg.platform, msg.username)

        # 按钮回调
        if msg.callback_data:
            self._handle_callback(msg)
            return

        # 挂起输入（多步对话）
        if msg.user_id in self._pending_input and not msg.callback_data:
            self._handle_pending_input(msg)
            return

        text = msg.text.strip()

        # 指令路由
        if text.startswith("/start"):
            self._cmd_start(msg)
        elif text.startswith("/help") or text == "帮助":
            self._cmd_help(msg)
        elif text.startswith("/menu") or text == "菜单":
            self._cmd_menu(msg)
        elif text.startswith("/quote") or text.startswith("/q "):
            self._cmd_quote(msg)
        elif text.startswith("/watchlist") or text.startswith("/wl"):
            self._cmd_watchlist(msg)
        elif text.startswith("/add "):
            self._cmd_add(msg)
        elif text.startswith("/remove ") or text.startswith("/del "):
            self._cmd_remove(msg)
        elif text.startswith("/tasks"):
            self._cmd_tasks(msg)
        elif text.startswith("/newtask"):
            self._cmd_newtask(msg)
        elif text.startswith("/deltask "):
            self._cmd_deltask(msg)
        elif text.startswith("/pause "):
            self._cmd_pause(msg)
        elif text.startswith("/quiet"):
            self._cmd_quiet(msg)
        elif text.startswith("/alert"):
            self._cmd_alert(msg)
        elif text.startswith("/mute "):
            self._cmd_mute(msg)
        elif text.startswith("/settings"):
            self._cmd_settings(msg)
        elif text.startswith("/macro"):
            self._cmd_macro(msg)
        elif text.startswith("/restart"):
            self._cmd_restart(msg)
        else:
            # 未识别的消息，提示帮助
            self.adapter.send_text(
                msg.user_id,
                "❓ 未识别的指令，发送 /help 查看所有功能"
            )

    # ── 指令实现 ──────────────────────────────────────────────────────

    def _cmd_start(self, msg: "IncomingMessage") -> None:
        card = menu_card()
        card.title = "👋 你好！我是你的综合秘书"
        card.content = (
            "我可以帮你：\n\n"
            "📈 **金融**　实时行情、公告监控、价格预警\n"
            "⏰ **定时推送**　每日日报、自定义任务\n\n"
            "点击下方按钮开始操作，或发送 `/help` 查看文字指令"
        )
        self.adapter.send_card(msg.user_id, card)

    def _cmd_menu(self, msg: "IncomingMessage") -> None:
        """主菜单：全功能按钮卡片"""
        self.adapter.send_card(msg.user_id, menu_card())

    def _cmd_help(self, msg: "IncomingMessage") -> None:
        """指令手册：纯文字说明"""
        self.adapter.send_card(msg.user_id, help_card())

    def _cmd_quote(self, msg: "IncomingMessage") -> None:
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            # 无参数时弹出输入卡片
            self.adapter.send_card(msg.user_id, quote_input_card())
            return
        self._fetch_and_send_quote(msg.user_id, parts[1].strip())

    def _do_quote_from_card(self, msg: "IncomingMessage", data: Dict) -> None:
        """处理 quote_input_card 提交的 form_value"""
        symbol = (data.get("symbol") or "").strip()
        if not symbol:
            self.adapter.send_text(msg.user_id, "❓ 请输入股票代码或名称")
            return
        self._fetch_and_send_quote(msg.user_id, symbol)

    def _fetch_and_send_quote(self, user_id: str, keyword: str) -> None:
        """核心查询逻辑，供 /quote 和卡片输入共用"""
        symbol = keyword.upper()
        self.adapter.send_text(user_id, f"🔍 正在查询 {keyword}...")

        # 非数字且非已知加密/指数代码 → 先名称搜索，避免用名字当代码查询产生误报
        if not symbol.isdigit() and symbol not in _SKIP_SEARCH:
            matches = search_stock(keyword)
            if len(matches) == 1:
                data = auto_quote(matches[0]["symbol"])
            elif len(matches) > 1:
                lines = [f"找到 {len(matches)} 个结果，请用代码查询："]
                for m in matches:
                    lines.append(f"　`/quote {m['symbol']}`　{m['name']}")
                self.adapter.send_text(user_id, "\n".join(lines))
                return
            else:
                # 搜索无结果，最后尝试直接查（如英文股票代码 AAPL）
                data = auto_quote(symbol)
        else:
            data = auto_quote(symbol)

        if not data:
            self.adapter.send_text(
                user_id,
                f"❌ 未找到 `{keyword}` 的行情数据\n\n"
                "支持：\n• A股代码（如 `600519`）\n• 港股代码（如 `00700`）\n• 加密货币（如 `BTC`）\n• A股名称（如 `贵州茅台`）"
            )
            return

        self.adapter.send_card(user_id, quote_card(data))

    def _cmd_watchlist(self, msg: "IncomingMessage") -> None:
        items = db.get_watchlist(msg.user_id)
        quote_map = {}
        if items:
            self.adapter.send_text(msg.user_id, "📋 正在获取自选行情...")
            quote_map = get_watchlist_quotes(msg.user_id)
        self.adapter.send_card(msg.user_id, watchlist_card(items, quote_map))

    def _cmd_add(self, msg: "IncomingMessage") -> None:
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2:
            self.adapter.send_card(msg.user_id, add_input_card())
            return
        self._fetch_and_add(msg.user_id, parts[1].strip())

    def _do_add_from_card(self, msg: "IncomingMessage", data: Dict) -> None:
        """处理 add_input_card 提交的 input 值"""
        symbol = (data.get("symbol") or "").strip()
        if not symbol:
            self.adapter.send_text(msg.user_id, "❓ 请输入股票代码或名称")
            return
        self._fetch_and_add(msg.user_id, symbol)

    def _fetch_and_add(self, user_id: str, keyword: str) -> None:
        """核心添加自选逻辑，供 /add 和卡片输入共用"""
        symbol = keyword.upper()
        self.adapter.send_text(user_id, f"🔍 正在查询 {keyword}...")

        # 非数字且非已知加密/指数代码 → 先名称搜索，避免用名字当代码查询产生误报
        if not symbol.isdigit() and symbol not in _SKIP_SEARCH:
            matches = search_stock(keyword)
            if len(matches) == 1:
                symbol = matches[0]["symbol"]
                data = auto_quote(symbol)
            elif len(matches) > 1:
                lines = [f"找到 {len(matches)} 个结果，请用代码添加："]
                for m in matches:
                    lines.append(f"　`/add {m['symbol']}`　{m['name']}")
                self.adapter.send_text(user_id, "\n".join(lines))
                return
            else:
                data = auto_quote(symbol)
        else:
            data = auto_quote(symbol)

        if not data:
            self.adapter.send_error(user_id, f"未找到 `{keyword}`，请检查代码或名称")
            return

        success = db.add_watchlist(
            user_id, symbol,
            data.get("asset_type", "unknown"),
            data.get("name", symbol)
        )
        if success:
            self.adapter.send_success(
                user_id,
                f"已添加 **{data.get('name', symbol)}** ({symbol}) 到自选"
            )
        else:
            self.adapter.send_text(user_id, f"ℹ️ {symbol} 已在自选中")

    def _cmd_remove(self, msg: "IncomingMessage") -> None:
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2:
            self.adapter.send_text(msg.user_id, "用法：`/remove 600519`")
            return
        symbol = parts[1].strip().upper()
        if db.remove_watchlist(msg.user_id, symbol):
            self.adapter.send_success(msg.user_id, f"已从自选移除 {symbol}")
        else:
            self.adapter.send_text(msg.user_id, f"ℹ️ 自选中没有 {symbol}")

    def _cmd_tasks(self, msg: "IncomingMessage") -> None:
        tasks = db.get_tasks(msg.user_id)
        alerts = db.get_alerts(msg.user_id)
        self.adapter.send_card(msg.user_id, tasks_card(tasks, alerts))

    def _refresh_tasks_card(self, msg: "IncomingMessage") -> None:
        """重新构建任务卡片，优先原地刷新"""
        tasks = db.get_tasks(msg.user_id)
        alerts = db.get_alerts(msg.user_id)
        card = tasks_card(tasks, alerts)
        if msg.card_message_id:
            if not self.adapter.update_card(msg.card_message_id, card):
                self.adapter.send_card(msg.user_id, card)
        else:
            self.adapter.send_card(msg.user_id, card)

    def _cmd_newtask(self, msg: "IncomingMessage") -> None:
        self.adapter.send_card(msg.user_id, newtask_type_card())

    def _cmd_deltask(self, msg: "IncomingMessage") -> None:
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip().isdigit():
            self.adapter.send_text(msg.user_id, "用法：`/deltask 任务编号`，例如 `/deltask 3`")
            return
        task_id = int(parts[1].strip())
        if db.delete_task(task_id):
            self.adapter.send_success(msg.user_id, f"任务 #{task_id} 已删除")
        else:
            self.adapter.send_error(msg.user_id, f"未找到任务 #{task_id}")

    def _cmd_pause(self, msg: "IncomingMessage") -> None:
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip().isdigit():
            self.adapter.send_text(msg.user_id, "用法：`/pause 任务编号`")
            return
        task_id = int(parts[1].strip())
        tasks = db.get_tasks(msg.user_id)
        task = next((t for t in tasks if t["id"] == task_id), None)
        if not task:
            self.adapter.send_error(msg.user_id, f"未找到任务 #{task_id}")
            return
        new_state = not bool(task["enabled"])
        db.toggle_task(task_id, new_state)
        state_str = "▶️ 已恢复" if new_state else "⏸️ 已暂停"
        self.adapter.send_success(msg.user_id, f"任务 #{task_id} {state_str}")

    def _cmd_quiet(self, msg: "IncomingMessage") -> None:
        settings = db.get_user_settings(msg.user_id)
        current = settings.get("quiet_mode", False)
        settings["quiet_mode"] = not current
        db.update_user_settings(msg.user_id, settings)
        if settings["quiet_mode"]:
            self.adapter.send_success(msg.user_id, "🔕 免打扰模式已开启\n仅保留最高级别预警推送")
        else:
            self.adapter.send_success(msg.user_id, "🔔 免打扰模式已关闭")

    def _cmd_alert(self, msg: "IncomingMessage") -> None:
        alerts = db.get_alerts(msg.user_id)
        if not alerts:
            self.adapter.send_card(msg.user_id, alert_input_card())
            return

        cond_map = {"above": "高于", "below": "低于", "change_pct": "涨跌幅超"}
        lines = ["当前价格预警：\n"]
        for a in alerts:
            status = "🟢" if a["enabled"] else "⏸️"
            cond = cond_map.get(a["condition"], a["condition"])
            lines.append(f"{status} **{a['symbol']}** {cond} {a['threshold']}")
        from bot.adapters.base import CardButton, OutgoingCard
        self.adapter.send_card(
            msg.user_id,
            OutgoingCard(
                title="🔔 我的价格预警",
                content="\n".join(lines),
                buttons=[CardButton("新增预警 ➕", "go_alert_input", {}, style="primary")],
            )
        )

    def _cmd_mute(self, msg: "IncomingMessage") -> None:
        # /mute 600519 2h
        parts = msg.text.split()
        if len(parts) < 3:
            self.adapter.send_text(msg.user_id, "用法：`/mute 600519 2h`")
            return
        symbol = parts[1].upper()
        duration = parts[2]
        self.adapter.send_success(msg.user_id, f"已屏蔽 {symbol} 推送 {duration}")

    # ── 按钮回调 ──────────────────────────────────────────────────────

    def _handle_callback(self, msg: "IncomingMessage") -> None:
        try:
            data = json.loads(msg.callback_data or "{}")
        except json.JSONDecodeError:
            data = {"action": msg.callback_data}

        action = data.get("action", "")
        logger.debug(f"回调: {action} {data} from {msg.user_id}")

        routing = {
            "go_quote":             lambda: self.adapter.send_card(
                msg.user_id, quote_input_card()
            ),
            "do_quote":             lambda: self._do_quote_from_card(msg, data),
            "go_watchlist":         lambda: self._cmd_watchlist(msg),
            "go_remove_watchlist":  lambda: self._cmd_watchlist(msg),  # 显示带删除按钮的列表
            "go_tasks":             lambda: self._cmd_tasks(msg),
            "go_newtask":           lambda: self._cmd_newtask(msg),
            "go_add":               lambda: self.adapter.send_card(
                msg.user_id, add_input_card()
            ),
            "do_add":               lambda: self._do_add_from_card(msg, data),
            "go_alerts":            lambda: self._cmd_alert(msg),
            "go_alert_input":       lambda: self.adapter.send_card(
                msg.user_id, alert_input_card()
            ),
            "go_settings":          lambda: self._cmd_settings(msg),
            "go_quiet":             lambda: self._cmd_quiet(msg),
            "go_restart":           lambda: self._cmd_restart(msg),
            "go_macro":             lambda: self._cmd_macro(msg),
            "add_watchlist":        lambda: self._add_from_callback(msg, data),
            "add_alert":            lambda: self._alert_from_callback(msg, data),
            "remove_watchlist":     lambda: self._remove_from_callback(msg, data),
            "alert_type":           lambda: self._alert_type_callback(msg, data),
            "do_alert_setup":       lambda: self._do_alert_setup(msg, data),
            "newtask_type":         lambda: self._newtask_type_callback(msg, data),
            "newtask_confirm":      lambda: self._newtask_confirm_callback(msg, data),
            "do_newtask_announcement": lambda: self._do_newtask_announcement(msg, data),
            "go_morning_modules":   lambda: self._go_morning_modules(msg, data),
            "toggle_morning_module": lambda: self._toggle_morning_module(msg, data),
            "save_morning_modules": lambda: self._save_morning_modules(msg, data),
            "save_push_times":      lambda: self._save_push_times_callback(msg, data),
            "toggle_task_btn":      lambda: self._toggle_task_btn(msg, data),
            "del_task_btn":         lambda: self._del_task_btn(msg, data),
        }

        handler = routing.get(action)
        if handler:
            handler()
        else:
            logger.warning(f"未知回调 action: {action}")

    def _add_from_callback(self, msg: "IncomingMessage", data: Dict) -> None:
        symbol = data.get("symbol", "")
        if symbol:
            msg.text = f"/add {symbol}"
            msg.callback_data = None  # 防止递归
            self._cmd_add(msg)

    def _remove_from_callback(self, msg: "IncomingMessage", data: Dict) -> None:
        """从按钮删除自选"""
        symbol = data.get("symbol", "")
        if not symbol:
            return
        ok = db.remove_watchlist(msg.user_id, symbol)
        if ok:
            self.adapter.send_success(msg.user_id, f"已从自选删除 {symbol}")
        else:
            self.adapter.send_text(msg.user_id, f"❌ 未找到 {symbol}，无需删除")
        # 刷新自选列表
        self._cmd_watchlist(msg)

    def _alert_from_callback(self, msg: "IncomingMessage", data: Dict) -> None:
        """从行情卡片「设置预警 🔔」按钮跳转到预警设置卡片（已知股票代码）"""
        symbol = data.get("symbol", "")
        name = data.get("nm", symbol)
        if symbol:
            self.adapter.send_card(msg.user_id, alert_setup_card(symbol, name))

    def _do_alert_setup(self, msg: "IncomingMessage", data: Dict) -> None:
        """处理多输入框预警表单提交（form_submit 回调）"""
        # symbol 可能来自预填（alert_setup_card）或表单字段（alert_input_card）
        symbol_raw = (data.get("symbol") or data.get("nm") or "").strip()
        form_symbol = (data.get("symbol") or "").strip()
        if not form_symbol:
            self.adapter.send_error(msg.user_id, "请填写股票代码")
            return

        # 尝试解析股票代码/名称
        keyword = form_symbol
        resolved_symbol = keyword.upper()
        resolved_name = keyword

        if keyword not in _SKIP_SEARCH:
            results = search_stock(keyword)
            if results and len(results) == 1:
                resolved_symbol = results[0].get("code", keyword.upper())
                resolved_name = results[0].get("name", keyword)
            elif not results:
                resolved_symbol = keyword.upper()
                resolved_name = keyword

        # 解析各阈值字段
        def _parse_float(val) -> Optional[float]:
            try:
                return float(str(val).strip()) if str(val).strip() else None
            except ValueError:
                return None

        price_above = _parse_float(data.get("price_above"))
        price_below = _parse_float(data.get("price_below"))
        rise_pct    = _parse_float(data.get("rise_pct"))
        fall_pct    = _parse_float(data.get("fall_pct"))

        if all(v is None for v in [price_above, price_below, rise_pct, fall_pct]):
            self.adapter.send_error(msg.user_id, "请至少填写一项提醒条件")
            return

        added = []
        if price_above is not None:
            aid = db.add_alert(msg.user_id, resolved_symbol, "above", price_above)
            added.append(f"⬆️ 价格高于 {price_above}  (#{aid})")
        if price_below is not None:
            aid = db.add_alert(msg.user_id, resolved_symbol, "below", price_below)
            added.append(f"⬇️ 价格低于 {price_below}  (#{aid})")
        if rise_pct is not None:
            aid = db.add_alert(msg.user_id, resolved_symbol, "change_pct", abs(rise_pct))
            added.append(f"📈 涨幅超过 {abs(rise_pct):.1f}%  (#{aid})")
        if fall_pct is not None:
            aid = db.add_alert(msg.user_id, resolved_symbol, "change_pct", -abs(fall_pct))
            added.append(f"📉 跌幅超过 {abs(fall_pct):.1f}%  (#{aid})")

        display = f"{resolved_name} ({resolved_symbol})" if resolved_name != resolved_symbol else resolved_symbol
        conditions = "\n".join(f"  {c}" for c in added)
        self.adapter.send_success(
            msg.user_id,
            f"价格预警已设置！\n\n"
            f"**标的：** {display}\n"
            f"**提醒条件：**\n{conditions}\n\n"
            f"发送 `/alert` 查看所有预警"
        )

    def _alert_type_callback(self, msg: "IncomingMessage", data: Dict) -> None:
        """用户选择了预警类型，进入对话等待数值输入"""
        symbol = data.get("symbol", "")
        name = data.get("nm", symbol)
        cond = data.get("cond", "")
        if not symbol or not cond:
            return

        cond_prompts = {
            "rise_pct": (f"请输入 **{name}({symbol})** 涨幅预警阈值（%）\n"
                         "例如输入 `5` 表示涨幅超过5%时提醒"),
            "fall_pct": (f"请输入 **{name}({symbol})** 跌幅预警阈值（%）\n"
                         "例如输入 `5` 表示跌幅超过5%时提醒"),
            "above":    (f"请输入 **{name}({symbol})** 价格上限\n"
                         "例如输入 `2000` 表示价格超过2000时提醒"),
            "below":    (f"请输入 **{name}({symbol})** 价格下限\n"
                         "例如输入 `1500` 表示价格低于1500时提醒"),
        }
        prompt = cond_prompts.get(cond, "请输入数值：")
        self._pending_input[msg.user_id] = {
            "type": "alert_value",
            "symbol": symbol,
            "name": name,
            "cond": cond,
        }
        self.adapter.send_text(msg.user_id, prompt + "\n\n（发送 `/cancel` 取消）")

    def _handle_pending_input(self, msg: "IncomingMessage") -> None:
        """处理多步对话中的用户输入"""
        state = self._pending_input.get(msg.user_id)
        if not state:
            return

        text = msg.text.strip()

        # 取消
        if text.lower() in ("/cancel", "取消"):
            del self._pending_input[msg.user_id]
            self.adapter.send_text(msg.user_id, "已取消操作")
            return

        if state["type"] == "alert_value":
            symbol = state["symbol"]
            name = state["name"]
            cond = state["cond"]

            try:
                value = float(text)
            except ValueError:
                self.adapter.send_text(msg.user_id, f"❌ 请输入数字，例如 `5` 或 `2000`")
                return

            # 涨跌幅映射为 change_pct，跌幅为负阈值
            db_cond = cond
            db_threshold = value
            if cond == "rise_pct":
                db_cond = "change_pct"
                db_threshold = abs(value)
            elif cond == "fall_pct":
                db_cond = "change_pct"
                db_threshold = -abs(value)

            alert_id = db.add_alert(msg.user_id, symbol, db_cond, db_threshold)
            del self._pending_input[msg.user_id]

            cond_desc = {
                "rise_pct": f"涨幅超过 {value}%",
                "fall_pct": f"跌幅超过 {value}%",
                "above":    f"价格超过 {value}",
                "below":    f"价格低于 {value}",
            }
            self.adapter.send_success(
                msg.user_id,
                f"✅ 价格预警已设置！\n\n"
                f"**标的：** {name}（{symbol}）\n"
                f"**条件：** {cond_desc.get(cond, f'{db_cond} {db_threshold}')}\n"
                f"**预警编号：** #{alert_id}\n\n"
                f"发送 `/alert` 查看所有预警"
            )

    def _newtask_type_callback(self, msg: "IncomingMessage", data: Dict) -> None:
        task_type = data.get("type", "")
        if task_type == "daily_report":
            self.adapter.send_card(msg.user_id, newtask_time_card("daily_report", [
                {"label": "📈 每天 15:30 收盘后", "cron": "30 15 * * 1-5"},
                {"label": "🌅 每天 09:00 开盘前", "cron": "0 9 * * 1-5"},
                {"label": "🔁 每天两次（09:00 + 15:30）", "cron": "0 9,15 * * 1-5"},
            ]))
        elif task_type == "index_report":
            self.adapter.send_card(msg.user_id, newtask_time_card("index_report", [
                {"label": "🔔 每天 09:30 开盘时", "cron": "30 9 * * 1-5"},
                {"label": "🌅 每天 08:00 开盘前", "cron": "0 8 * * 1-5"},
            ]))
        else:
            self.adapter.send_text(msg.user_id, "未知任务类型")

    def _newtask_confirm_callback(self, msg: "IncomingMessage", data: Dict) -> None:
        """用户选了推送时间，写入 tasks 表并注册调度"""
        task_type = data.get("type", "")
        cron = data.get("cron", "")
        desc = data.get("desc", cron)
        if not task_type or not cron:
            self.adapter.send_error(msg.user_id, "参数缺失，请重新选择")
            return

        task_id = db.add_task(msg.user_id, task_type, {}, cron)

        # 通知调度器注册新任务
        from bot.scheduler import TaskScheduler
        scheduler = TaskScheduler.get_instance()
        if scheduler:
            scheduler.register_task_by_id(task_id)

        type_names = {
            "daily_report": "每日行情报告", "index_report": "指数早报",
        }
        type_name = type_names.get(task_type, task_type)
        self.adapter.send_success(
            msg.user_id,
            f"{type_name} 已创建！\n\n"
            f"**推送时间：** {desc}\n"
            f"**任务编号：** #{task_id}\n\n"
            f"发送 `/tasks` 查看所有任务"
        )

    def _do_newtask_announcement(self, msg: "IncomingMessage", data: Dict) -> None:
        """公告监控：用户输入股票代码，写入 tasks 表"""
        raw = data.get("symbols", "").strip()
        if not raw:
            self.adapter.send_error(msg.user_id, "请输入股票代码")
            return

        symbols = [s.strip() for s in raw.replace("，", ",").split(",") if s.strip()]
        if not symbols:
            self.adapter.send_error(msg.user_id, "未识别到有效股票代码")
            return

        config = {"symbols": symbols}
        cron = "0 9,12,15 * * 1-5"   # 每天 09:00 / 12:00 / 15:00 检查
        task_id = db.add_task(msg.user_id, "announcement", config, cron)

        from bot.scheduler import TaskScheduler
        scheduler = TaskScheduler.get_instance()
        if scheduler:
            scheduler.register_task_by_id(task_id)

        symbol_str = "、".join(symbols)
        self.adapter.send_success(
            msg.user_id,
            f"股票公告监控已创建！\n\n"
            f"**监控标的：** {symbol_str}\n"
            f"**推送时间：** 每个交易日 09:00 / 12:00 / 15:00\n"
            f"**任务编号：** #{task_id}\n\n"
            f"发送 `/tasks` 查看所有任务"
        )

    # ── 任务卡片内联操作（暂停/删除）────────────────────────────────

    def _toggle_task_btn(self, msg: "IncomingMessage", data: Dict) -> None:
        """卡片按钮暂停/恢复任务，原地刷新"""
        task_id = int(data.get("task_id", 0))
        if not task_id:
            return
        tasks = db.get_tasks(msg.user_id)
        task = next((t for t in tasks if t["id"] == task_id), None)
        if not task:
            self.adapter.send_error(msg.user_id, f"未找到任务 #{task_id}")
            return
        new_state = not bool(task["enabled"])
        db.toggle_task(task_id, new_state)
        self._refresh_tasks_card(msg)

    def _del_task_btn(self, msg: "IncomingMessage", data: Dict) -> None:
        """卡片按钮删除任务，原地刷新"""
        task_id = int(data.get("task_id", 0))
        if not task_id:
            return
        db.delete_task(task_id)
        self._refresh_tasks_card(msg)

    # ── 早报/日报内容模块定制 ─────────────────────────────────────────

    def _go_morning_modules(self, msg: "IncomingMessage", data: Dict) -> None:
        """打开模块选择卡片"""
        report_type = data.get("report_type", "morning")
        settings = db.get_user_settings(msg.user_id)
        key = "morning_modules" if report_type == "morning" else "daily_modules"
        defaults = list(DEFAULT_MORNING_MODULES if report_type == "morning" else DEFAULT_DAILY_MODULES)
        selected = settings.get(key, defaults)
        card = morning_modules_card(report_type, selected)
        self.adapter.send_card(msg.user_id, card)

    def _toggle_morning_module(self, msg: "IncomingMessage", data: Dict) -> None:
        """切换一个模块的开启/关闭状态，原地刷新选择卡片"""
        report_type = data.get("report_type", "morning")
        module = data.get("module", "")
        current_str = data.get("current", "")
        current = set(current_str.split(",")) if current_str else set()
        current.discard("")  # 去除空字符串

        if module in current:
            current.discard(module)
        else:
            current.add(module)

        card = morning_modules_card(report_type, list(current))
        # 优先原地刷新，失败时发新消息
        if msg.card_message_id:
            if not self.adapter.update_card(msg.card_message_id, card):
                self.adapter.send_card(msg.user_id, card)
        else:
            self.adapter.send_card(msg.user_id, card)

    def _save_morning_modules(self, msg: "IncomingMessage", data: Dict) -> None:
        """保存模块选择到 users.settings"""
        report_type = data.get("report_type", "morning")
        modules_str = data.get("modules", "")
        modules = [m for m in modules_str.split(",") if m]

        settings = db.get_user_settings(msg.user_id)
        key = "morning_modules" if report_type == "morning" else "daily_modules"
        settings[key] = modules
        db.update_user_settings(msg.user_id, settings)

        label = "早报" if report_type == "morning" else "日报"
        module_names = {
            "a_stock": "A股指数", "us_stock": "美股三大", "hk_stock": "港股恒生",
            "fx": "汇率", "commodity": "原油/黄金", "us_news": "美股新闻情绪",
        }
        selected_labels = "、".join(module_names.get(m, m) for m in modules) or "（空）"
        self.adapter.send_success(
            msg.user_id,
            f"✅ {label}内容已更新！\n\n**已选模块：** {selected_labels}\n\n下次推送将按新设置发送。"
        )

    def _save_push_times_callback(self, msg: "IncomingMessage", data: Dict) -> None:
        """从 settings 卡片表单保存推送时间"""
        morning_time = (data.get("morning_time") or "").strip()
        digest_time  = (data.get("digest_time") or "").strip()
        _save_user_push_time(
            self.adapter, msg.user_id,
            morning_time=morning_time or None,
            digest_time=digest_time or None,
        )

    def _cmd_macro(self, msg: "IncomingMessage") -> None:
        """手动查询美国宏观指标（CPI/失业率/联邦利率/国债）"""
        import threading
        from bot.formatters.cards import macro_query_card
        try:
            from data.sources.alphavantage_source import (
                get_macro_summary, is_configured, is_quota_exhausted,
            )
            if not is_configured():
                self.adapter.send_text(
                    msg.user_id, "⚠️ Alpha Vantage key 未配置，无法查询宏观数据\n请在 config.py 中设置 AV_API_KEY"
                )
                return
            if is_quota_exhausted():
                self.adapter.send_text(msg.user_id, "⚠️ Alpha Vantage 配额已耗尽，请明日再试")
                return
        except Exception as e:
            self.adapter.send_text(msg.user_id, f"❌ 初始化失败：{e}")
            return

        # 先回复「查询中」，再异步拉数据（AV 限速 12s/次，4项串行最长约46s）
        self.adapter.send_text(msg.user_id, "🔄 正在查询美国宏观指标，约需 15-50 秒，请稍候...")

        def _fetch():
            try:
                data = get_macro_summary() or []
                card = macro_query_card(data)
                self.adapter.send_card(msg.user_id, card)
            except Exception as e:
                logger.error(f"宏观查询失败: {e}")
                self.adapter.send_text(msg.user_id, f"❌ 查询失败：{e}")

        threading.Thread(target=_fetch, daemon=True).start()

    def _cmd_restart(self, msg: "IncomingMessage") -> None:
        """通过飞书触发后台重启（先回复再重启，确保消息发出）"""
        import subprocess
        import threading
        import os

        restart_sh = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "restart.sh"
        )
        if not os.path.exists(restart_sh):
            self.adapter.send_text(msg.user_id, "❌ 未找到 restart.sh，请手动重启")
            return

        self.adapter.send_text(
            msg.user_id,
            "🔄 正在重启服务...\n\n约 5 秒后重新连接，稍后可发送 `/menu` 验证是否恢复正常。"
        )

        def _do_restart():
            import time
            time.sleep(2)  # 等消息发出
            subprocess.Popen(["bash", restart_sh])

        threading.Thread(target=_do_restart, daemon=True).start()

    def _cmd_settings(self, msg: "IncomingMessage") -> None:
        """查看或修改系统配置"""
        parts = (msg.text or "").split(maxsplit=2)

        # /settings（无参数）或按钮回调 — 显示推送时间配置卡片
        if len(parts) <= 1:
            try:
                import config as cfg
            except ImportError:
                cfg = None
            user_settings = db.get_user_settings(msg.user_id)
            # 用户设置优先，其次 config.py 默认值
            def _parse_hm(time_str, default_h, default_m):
                try:
                    h, m = map(int, time_str.split(":"))
                    return h, m
                except Exception:
                    return default_h, default_m
            morning_h, morning_m = _parse_hm(
                user_settings.get("morning_time", ""),
                getattr(cfg, "MORNING_REPORT_HOUR", 9),
                getattr(cfg, "MORNING_REPORT_MINUTE", 0),
            )
            digest_h, digest_m = _parse_hm(
                user_settings.get("digest_time", ""),
                getattr(cfg, "DAILY_DIGEST_HOUR", 15),
                getattr(cfg, "DAILY_DIGEST_MINUTE", 30),
            )
            vals = {
                "alert_min": getattr(cfg, "PRICE_ALERT_INTERVAL_MINUTES", 5),
                "digest_h":  digest_h,
                "digest_m":  digest_m,
                "morning_h": morning_h,
                "morning_m": morning_m,
            }
            self.adapter.send_card(msg.user_id, settings_card(vals))
            return

        key = parts[1].lower() if len(parts) > 1 else ""
        val = parts[2].strip() if len(parts) > 2 else ""

        try:
            import config as cfg
            cfg_path = cfg.__file__

            if key == "alert_interval":
                minutes = int(val)
                if minutes < 1 or minutes > 60:
                    self.adapter.send_text(msg.user_id, "❌ 间隔范围：1~60 分钟")
                    return
                _update_config_value(cfg_path, "PRICE_ALERT_INTERVAL_MINUTES", minutes)
                self.adapter.send_text(msg.user_id, f"✅ 价格预警间隔已设为 {minutes} 分钟\n重启后生效：`bash restart.sh`")

            elif key == "digest_time":
                h, m = map(int, val.split(":"))
                _save_user_push_time(self.adapter, msg.user_id, digest_time=f"{h:02d}:{m:02d}")

            elif key == "morning_time":
                h, m = map(int, val.split(":"))
                _save_user_push_time(self.adapter, msg.user_id, morning_time=f"{h:02d}:{m:02d}")

            else:
                self.adapter.send_text(
                    msg.user_id,
                    "❓ 未知配置项，支持：\n"
                    "`/settings alert_interval 分钟`\n"
                    "`/settings digest_time HH:MM`\n"
                    "`/settings morning_time HH:MM`"
                )
        except (ValueError, IndexError):
            self.adapter.send_text(msg.user_id, f"❌ 格式错误，例如：`/settings {key} {val}`")
        except Exception as e:
            logger.error(f"settings 修改失败: {e}", exc_info=True)
            self.adapter.send_text(msg.user_id, f"❌ 修改失败：{e}")


def _update_config_value(cfg_path: str, key: str, value) -> None:
    """直接修改 config.py 中某个配置项的值"""
    import re
    with open(cfg_path, "r", encoding="utf-8") as f:
        content = f.read()
    new_content = re.sub(
        rf"^({key}\s*=\s*).*$",
        rf"\g<1>{repr(value)}",
        content,
        flags=re.MULTILINE
    )
    if new_content == content:
        # 不存在则追加
        new_content = content.rstrip() + f"\n{key} = {repr(value)}\n"
    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write(new_content)


def _save_user_push_time(adapter, user_id: str,
                         morning_time: Optional[str] = None,
                         digest_time: Optional[str] = None) -> None:
    """
    验证并保存用户推送时间到 users.settings，
    同时通知调度器动态 reschedule。
    morning_time / digest_time: "HH:MM" 格式，None 表示不修改。
    """
    import re
    TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")

    updates: Dict = {}
    labels = []

    for field_name, time_val, label in [
        ("morning_time", morning_time, "早报"),
        ("digest_time",  digest_time,  "日报"),
    ]:
        if not time_val:
            continue
        m = TIME_RE.match(time_val)
        if not m:
            adapter.send_error(user_id, f"{label}时间格式错误，请用 HH:MM，如 08:30")
            return
        # normalize to HH:MM
        h, mn = int(m.group(1)), int(m.group(2))
        updates[field_name] = f"{h:02d}:{mn:02d}"
        labels.append(f"**{label}** {h:02d}:{mn:02d}")

    if not updates:
        adapter.send_error(user_id, "请至少填写一个推送时间")
        return

    settings = db.get_user_settings(user_id)
    settings.update(updates)
    db.update_user_settings(user_id, settings)

    # 通知调度器热更新
    from bot.scheduler import TaskScheduler
    scheduler = TaskScheduler.get_instance()
    if scheduler:
        scheduler.reschedule_user_push(
            user_id,
            morning_time=updates.get("morning_time"),
            digest_time=updates.get("digest_time"),
        )

    label_str = "、".join(labels)
    adapter.send_success(user_id, f"✅ 推送时间已更新！\n\n{label_str}\n\n**立即生效**，无需重启。")
