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
    help_card, menu_card, quote_card, watchlist_card, tasks_card,
    newtask_type_card, announcement_card, settings_card, alert_setup_card
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
            self.adapter.send_text(
                msg.user_id,
                "请输入股票代码或名称，例如：\n`/quote 600519`\n`/quote 贵州茅台`\n`/quote 00700`\n`/quote BTC`"
            )
            return

        keyword = parts[1].strip()
        symbol = keyword.upper()
        self.adapter.send_text(msg.user_id, f"🔍 正在查询 {keyword}...")

        # 先尝试直接按代码查
        data = auto_quote(symbol)

        # 查不到且输入不是纯数字/加密货币代码 → 尝试名称搜索
        if not data and not symbol.isdigit() and symbol not in _SKIP_SEARCH:
            matches = search_stock(keyword)
            if len(matches) == 1:
                # 唯一匹配，直接查
                data = auto_quote(matches[0]["symbol"])
            elif len(matches) > 1:
                # 多个匹配，列出让用户选
                lines = [f"找到 {len(matches)} 个结果，请用代码查询："]
                for m in matches:
                    lines.append(f"　`/quote {m['symbol']}`　{m['name']}")
                self.adapter.send_text(msg.user_id, "\n".join(lines))
                return

        if not data:
            self.adapter.send_text(
                msg.user_id,
                f"❌ 未找到 `{keyword}` 的行情数据\n\n"
                "支持：\n• A股代码（如 `600519`）\n• 港股代码（如 `00700`）\n• 加密货币（如 `BTC`）\n• A股名称（如 `贵州茅台`）"
            )
            return

        self.adapter.send_card(msg.user_id, quote_card(data))

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
            self.adapter.send_text(msg.user_id, "用法：`/add 600519` 或 `/add 贵州茅台`")
            return

        keyword = parts[1].strip()
        symbol = keyword.upper()
        self.adapter.send_text(msg.user_id, f"🔍 正在查询 {keyword}...")

        data = auto_quote(symbol)

        # 代码查不到且不是纯数字/加密货币 → 尝试名称搜索
        if not data and not symbol.isdigit() and symbol not in _SKIP_SEARCH:
            matches = search_stock(keyword)
            if len(matches) == 1:
                data = auto_quote(matches[0]["symbol"])
                symbol = matches[0]["symbol"]
            elif len(matches) > 1:
                lines = [f"找到 {len(matches)} 个结果，请用代码添加："]
                for m in matches:
                    lines.append(f"　`/add {m['symbol']}`　{m['name']}")
                self.adapter.send_text(msg.user_id, "\n".join(lines))
                return

        if not data:
            self.adapter.send_error(msg.user_id, f"未找到 `{keyword}`，请检查代码或名称")
            return

        success = db.add_watchlist(
            msg.user_id, symbol,
            data.get("asset_type", "unknown"),
            data.get("name", symbol)
        )
        if success:
            self.adapter.send_success(
                msg.user_id,
                f"已添加 **{data.get('name', symbol)}** ({symbol}) 到自选"
            )
        else:
            self.adapter.send_text(msg.user_id, f"ℹ️ {symbol} 已在自选中")

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
        self.adapter.send_card(msg.user_id, tasks_card(tasks))

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
            self.adapter.send_text(
                msg.user_id,
                "🔔 当前没有价格预警\n\n"
                "查询行情后点击「设置预警 🔔」按钮，或使用：\n"
                "`/alert 600519 above 2000` — 价格超过2000时提醒\n"
                "`/alert 600519 change_pct 5` — 涨跌幅超5%时提醒"
            )
            return

        cond_map = {"above": "高于", "below": "低于", "change_pct": "涨跌幅超"}
        lines = ["当前价格预警：\n"]
        for a in alerts:
            status = "🟢" if a["enabled"] else "⏸️"
            cond = cond_map.get(a["condition"], a["condition"])
            lines.append(f"{status} **{a['symbol']}** {cond} {a['threshold']}")
        self.adapter.send_text(msg.user_id, "\n".join(lines))

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
            "go_quote":             lambda: self.adapter.send_text(
                msg.user_id,
                "请直接输入代码或名称查询，例如：\n"
                "　`600519`（A股）　`00700`（港股）\n"
                "　`BTC`（加密货币）　`SPX`（标普500）\n"
                "也可发送 `/quote 600519`"
            ),
            "go_watchlist":         lambda: self._cmd_watchlist(msg),
            "go_remove_watchlist":  lambda: self._cmd_watchlist(msg),  # 显示带删除按钮的列表
            "go_tasks":             lambda: self._cmd_tasks(msg),
            "go_newtask":           lambda: self._cmd_newtask(msg),
            "go_add":               lambda: self.adapter.send_text(
                msg.user_id,
                "请输入要添加到自选的代码，例如：\n"
                "　`/add 600519`（A股）\n"
                "　`/add BTC`（加密货币）"
            ),
            "go_alerts":            lambda: self._cmd_alert(msg),
            "go_settings":          lambda: self._cmd_settings(msg),
            "go_quiet":             lambda: self._cmd_quiet(msg),
            "add_watchlist":        lambda: self._add_from_callback(msg, data),
            "add_alert":            lambda: self._alert_from_callback(msg, data),
            "remove_watchlist":     lambda: self._remove_from_callback(msg, data),
            "alert_type":           lambda: self._alert_type_callback(msg, data),
            "newtask_type":         lambda: self._newtask_type_callback(msg, data),
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
        """从行情卡片'设置预警'按钮跳转到预警设置卡片"""
        symbol = data.get("symbol", "")
        name = data.get("nm", symbol)
        if symbol:
            self.adapter.send_card(msg.user_id, alert_setup_card(symbol, name))

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
        type_prompts = {
            "daily_report": "每日行情报告已选定 ✅\n请选择推送时间：\n`A` 每天15:30收盘后\n`B` 每天09:00开盘前\n`C` 早报+收盘（每天2次）\n\n回复 A/B/C 完成设置",
            "announcement": "股票公告监控已选定 ✅\n请输入要监控的股票代码（多个用逗号分隔）：\n例如：`600519, 000858`",
            "price_alert":  "价格突破预警已选定 ✅\n请输入格式：`股票代码 above/below/change_pct 阈值`\n例如：`600519 above 2000`",
            "index_report": "指数早报已选定 ✅\n请选择推送时间：\n`A` 每天09:30开盘\n`B` 每天08:00\n\n回复 A/B 完成设置",
        }
        prompt = type_prompts.get(task_type, "请按提示操作")
        self.adapter.send_text(msg.user_id, prompt)

    def _cmd_settings(self, msg: "IncomingMessage") -> None:
        """查看或修改系统配置"""
        parts = msg.text.split(maxsplit=2)

        # /settings — 显示当前配置
        if len(parts) == 1:
            try:
                import config as cfg
            except ImportError:
                cfg = None
            vals = {
                "alert_min": getattr(cfg, "PRICE_ALERT_INTERVAL_MINUTES", 5),
                "digest_h":  getattr(cfg, "DAILY_DIGEST_HOUR", 15),
                "digest_m":  getattr(cfg, "DAILY_DIGEST_MINUTE", 30),
                "morning_h": getattr(cfg, "MORNING_REPORT_HOUR", 9),
                "morning_m": getattr(cfg, "MORNING_REPORT_MINUTE", 0),
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
                _update_config_value(cfg_path, "DAILY_DIGEST_HOUR", h)
                _update_config_value(cfg_path, "DAILY_DIGEST_MINUTE", m)
                self.adapter.send_text(msg.user_id, f"✅ 收盘日报时间已设为 {h}:{m:02d}\n重启后生效：`bash restart.sh`")

            elif key == "morning_time":
                h, m = map(int, val.split(":"))
                _update_config_value(cfg_path, "MORNING_REPORT_HOUR", h)
                _update_config_value(cfg_path, "MORNING_REPORT_MINUTE", m)
                self.adapter.send_text(msg.user_id, f"✅ 早报时间已设为 {h}:{m:02d}\n重启后生效：`bash restart.sh`")

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
