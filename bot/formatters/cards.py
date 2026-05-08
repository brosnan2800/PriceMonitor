#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
消息格式化模块

feishu_card.py  → 飞书 MessageCard 专用模板（最终由 FeishuAdapter 渲染）
本模块提供：OutgoingCard 快速构建函数，供 handlers 调用
"""

from datetime import datetime
from typing import Dict, List, Optional

from bot.adapters.base import CardButton, CardForm, CardFormField, CardInput, OutgoingCard


# ── 行情展示 ──────────────────────────────────────────────────────────

def _trend(change_pct: float) -> str:
    if change_pct > 0:
        return f"📈 +{change_pct:.2f}%"
    elif change_pct < 0:
        return f"📉 {change_pct:.2f}%"
    return "➡️ 0.00%"


def quote_input_card() -> OutgoingCard:
    """查行情输入卡片（input 组件 + 确认按钮）"""
    return OutgoingCard(
        title="📈 查询行情",
        content=(
            "请在下方输入股票代码或名称：\n\n"
            "　**A股** — `600519` 或 `贵州茅台`\n"
            "　**港股** — `00700`\n"
            "　**美股** — `AAPL`\n"
            "　**加密** — `BTC`\n"
            "　**指数** — `SPX`（标普500）/ `HSI`（恒指）"
        ),
        input_field=CardInput(
            name="do_quote.symbol",
            placeholder="输入代码或名称，如 600519 / BTC / AAPL",
            action="do_quote",
        ),
        footer="输入后按 Enter 查询，或直接发送 /quote 600519"
    )



def add_input_card() -> OutgoingCard:
    """添加自选输入卡片"""
    return OutgoingCard(
        title="⭐ 添加自选",
        content=(
            "请在下方输入要添加的代码：\n\n"
            "　**A股** — `600519` 或 `贵州茅台`\n"
            "　**港股** — `00700`\n"
            "　**美股** — `AAPL`\n"
            "　**加密** — `BTC`"
        ),
        input_field=CardInput(
            name="do_add.symbol",
            placeholder="输入代码或名称，如 600519 / BTC / AAPL",
            action="do_add",
        ),
        footer="输入后按 Enter 添加，或直接发送 /add 600519"
    )


def quote_card(data: Dict) -> OutgoingCard:
    name = data.get("name", data.get("symbol", ""))
    symbol = data.get("symbol", "")
    price = data.get("price", 0)
    change_pct = data.get("change_pct", 0)
    change = data.get("change", 0)
    high = data.get("high", 0)
    low = data.get("low", 0)
    pe = data.get("pe_ratio", 0)
    ts = data.get("timestamp", datetime.now().strftime("%H:%M:%S"))

    trend = _trend(change_pct)
    sign = "+" if change > 0 else ""

    content_lines = [
        f"**价格**　{price}",
        f"**涨跌** 　{trend}　({sign}{change:.3f})",
    ]
    if high:
        content_lines.append(f"**最高/最低** 　{high} / {low}")
    if pe:
        content_lines.append(f"**市盈率(动)** 　{pe:.2f}")
    content_lines.append(f"**更新时间** 　{ts}")

    return OutgoingCard(
        title=f"{name}  ({symbol})",
        content="\n".join(content_lines),
        buttons=[
            CardButton("加入自选 ⭐", "add_watchlist", {"symbol": symbol}),
            CardButton("设置预警 🔔", "add_alert", {"symbol": symbol, "nm": name}),
        ],
        footer=f"数据来源：{data.get('source', 'AKShare')}"
    )


def watchlist_card(items: List[Dict], quote_map: Dict[str, Dict]) -> OutgoingCard:
    """自选列表卡片（每条标的带删除按钮）"""
    if not items:
        return OutgoingCard(
            title="📋 我的自选",
            content="还没有添加任何标的\n\n发送 `/add 600519` 或 `/quote 600519` 来添加",
            buttons=[CardButton("查行情 🔍", "go_quote", {})]
        )

    lines = []
    for item in items:
        sym = item["symbol"]
        q = quote_map.get(sym)
        if q:
            trend = _trend(q.get("change_pct", 0))
            high = q.get("high", 0)
            low  = q.get("low", 0)
            hl = f"　↑{high} ↓{low}" if high and low else ""
            lines.append(f"**{q.get('name', sym)}** `{sym}`　{q['price']}　{trend}{hl}")
        else:
            lines.append(f"**{item.get('name', sym)}** `{sym}`　数据获取中...")

    # 每条自选一个删除按钮，末尾加"添加"按钮
    del_buttons = []
    for item in items:
        sym = item["symbol"]
        label = item.get("name", sym) or sym
        del_buttons.append(
            CardButton(f"🗑 {label}", "remove_watchlist", {"symbol": sym}, style="danger")
        )
    del_buttons.append(CardButton("➕ 添加自选", "go_add", {}, style="primary"))

    return OutgoingCard(
        title=f"📋 我的自选  ({len(items)} 只)",
        content="\n".join(lines),
        buttons=del_buttons,
        footer=f"更新时间：{datetime.now().strftime('%H:%M:%S')}  |  点击🗑删除对应标的"
    )


def daily_digest_card(index_data: List[Dict], watchlist_data: List[Dict],
                      announcements: List[Dict], forex_data: List[Dict],
                      extra_modules: Optional[Dict] = None) -> OutgoingCard:
    """
    每日聚合日报卡片
    extra_modules: {"crypto": [...], "fx": [...], "commodity": [...]}
    """
    extra_modules = extra_modules or {}
    lines = []

    # 指数
    if index_data:
        lines.append("**📊 主要指数**")
        for idx in index_data:
            trend = _trend(idx.get("change_pct", 0))
            lines.append(f"　{idx['name']}　{idx['price']}　{trend}")
        lines.append("")

    # 自选
    if watchlist_data:
        lines.append("**⭐ 我的自选**")
        for q in watchlist_data:
            trend = _trend(q.get("change_pct", 0))
            lines.append(f"　{q.get('name', q['symbol'])}　{q['price']}　{trend}")
        lines.append("")

    # 公告
    if announcements:
        lines.append(f"**📢 今日公告 ({len(announcements)} 条)**")
        for ann in announcements[:3]:
            lines.append(f"　• {ann['symbol']} {ann['title'][:20]}...")
        lines.append("")

    # 加密货币模块
    crypto_list = extra_modules.get("crypto", [])
    if crypto_list:
        lines.append("**₿ 加密货币**")
        for c in crypto_list:
            trend = _trend(c.get("change_pct", 0))
            lines.append(f"　{c.get('name', c.get('symbol', ''))}　${c['price']}　{trend}")
        lines.append("")

    # 汇率模块（AV 或旧 forex_data）
    fx_list = extra_modules.get("fx", forex_data or [])
    if fx_list:
        lines.append("**💱 汇率**")
        for f in fx_list:
            rate = f.get("rate") or f.get("price", 0)
            name = f.get("name", "")
            chg = f.get("change_pct", 0)
            trend = _trend(chg) if chg else ""
            lines.append(f"　{name}　{rate}　{trend}".rstrip())
        lines.append("")

    # 大宗商品模块
    commodity_list = extra_modules.get("commodity", [])
    if commodity_list:
        lines.append("**🛢️ 大宗商品**")
        for c in commodity_list:
            trend = _trend(c.get("change_pct", 0))
            unit = c.get("unit", "")
            lines.append(f"　{c['name']}　{c['price']}{'/'+unit if unit else ''}　{trend}")

    # 配额提示
    av_quota_note = ""
    if extra_modules.get("av_quota_exhausted"):
        av_quota_note = "  |  ⚠️ AV配额已耗尽，汇率/商品数据将于明日恢复"

    return OutgoingCard(
        title=f"📊 金融日报 · {datetime.now().strftime('%m/%d %H:%M')}",
        content="\n".join(lines) if lines else "暂无数据",
        buttons=[
            CardButton("⚙️ 自定义内容", "go_morning_modules", {"report_type": "daily"}),
            CardButton("⚙️ 管理推送", "go_tasks", {}),
        ],
        footer=f"默认推送：工作日收盘后  |  /digest 切换推送模式{av_quota_note}"
    )


def menu_card() -> OutgoingCard:
    """主菜单卡片（全功能按钮入口）"""
    return OutgoingCard(
        title="🤖 综合秘书 · 主菜单",
        content="请选择要操作的功能：",
        buttons=[
            CardButton("查行情 🔍", "go_quote", {}, style="primary"),
            CardButton("我的自选 ⭐", "go_watchlist", {}),
            CardButton("定制任务 ⏰", "go_tasks", {}, style="primary"),
            CardButton("新建定制 ➕", "go_newtask", {}),
            CardButton("🇺🇸 美国宏观", "go_macro", {}),
            CardButton("免打扰 🔕", "go_quiet", {}),
            CardButton("重启服务 🔄", "go_restart", {}),
        ],
        footer="发送 /help 查看所有文字指令"
    )


def help_card() -> OutgoingCard:
    """帮助卡片（纯文字指令说明）"""
    content = (
        "**📈 金融查询**\n"
        "　`/quote 600519` 　A股实时行情\n"
        "　`/quote 00700` 　港股行情\n"
        "　`/quote BTC` 　　加密货币\n"
        "　`/quote SPX` 　　美股指数\n"
        "　`/quote 贵州茅台` 按名称搜索\n"
        "　`/watchlist` 　　我的自选列表\n"
        "　`/add 600519` 　添加自选\n"
        "　`/remove 600519` 移除自选\n\n"
        "**🔔 价格预警**\n"
        "　`/alert` 　　　　　　　　　查看预警列表\n"
        "　`/alert 600519 above 2000`  价格超过触发\n"
        "　`/alert 600519 below 1500`  价格跌破触发\n"
        "　`/alert 600519 change_pct 5` 涨跌幅超过触发\n\n"
        "**⏰ 定制任务**\n"
        "　`/tasks` 　　查看所有定制任务\n"
        "　`/newtask` 　新建定制任务\n"
        "　`/deltask 3` 删除任务\n"
        "　`/pause 3` 　暂停/恢复任务\n\n"
        "**🔕 推送控制**\n"
        "　`/quiet` 　　　　　免打扰模式开关\n"
        "　`/mute 600519 2h`  屏蔽标的推送2小时\n\n"
        "**⚙️ 系统**\n"
        "　`/settings` 　　　　　　　查看当前推送配置\n"
        "　`/settings alert_interval 5`  预警检查间隔(分钟)\n"
        "　`/settings digest_time 15:30` 日报推送时间\n"
        "　`/settings morning_time 9:00` 早报推送时间\n"
        "　`/restart` 　　　　　　　重启服务（修改配置后生效）\n\n"
        "💡 发送 `/menu` 调出按钮面板"
    )
    return OutgoingCard(
        title="🤖 综合秘书 · 指令手册",
        content=content,
        footer="发送 /menu 调出操作按钮"
    )


def alert_setup_card(symbol: str, name: str) -> OutgoingCard:
    """价格预警设置卡片 — 已知股票代码时直接进入阈值配置（多输入框）"""
    display = f"{name} ({symbol})" if name and name != symbol else symbol
    fields = [
        CardFormField("price_above", "价格上限（选填）",
                      placeholder="价格高于此值时提醒，如 2000"),
        CardFormField("price_below", "价格下限（选填）",
                      placeholder="价格低于此值时提醒，如 1500"),
        CardFormField("rise_pct",    "涨幅预警 % （选填）",
                      placeholder="当日涨幅超过此百分比时提醒，如 5"),
        CardFormField("fall_pct",    "跌幅预警 % （选填）",
                      placeholder="当日跌幅超过此百分比时提醒，如 3"),
    ]
    return OutgoingCard(
        title="🔔 设置价格预警",
        content=f"**标的：{display}**\n\n至少填写一项条件，空白项不生效：",
        form=CardForm(
            fields=fields,
            submit_label="确认设置 ✓",
            submit_action="do_alert_setup",
            submit_data={"symbol": symbol, "nm": name},
        ),
        footer="填写完成后点击「确认设置」",
    )


def alert_input_card() -> OutgoingCard:
    """价格预警设置卡片 — 未知股票代码时，从股票代码开始填（多输入框）"""
    fields = [
        CardFormField("symbol",      "股票代码 *（必填）",
                      placeholder="如 600519 / NVDA / BTC / 贵州茅台", required=True),
        CardFormField("price_above", "价格上限（选填）",
                      placeholder="价格高于此值时提醒，如 2000"),
        CardFormField("price_below", "价格下限（选填）",
                      placeholder="价格低于此值时提醒，如 1500"),
        CardFormField("rise_pct",    "涨幅预警 % （选填）",
                      placeholder="当日涨幅超过此百分比时提醒，如 5"),
        CardFormField("fall_pct",    "跌幅预警 % （选填）",
                      placeholder="当日跌幅超过此百分比时提醒，如 3"),
    ]
    return OutgoingCard(
        title="🔔 设置价格预警",
        content="输入股票代码并设置至少一项提醒条件：",
        form=CardForm(
            fields=fields,
            submit_label="确认设置 ✓",
            submit_action="do_alert_setup",
        ),
        footer="填写完成后点击「确认设置」",
    )


def tasks_card(tasks: List[Dict], alerts: Optional[List[Dict]] = None) -> OutgoingCard:
    """定制任务列表卡片：分两区显示推送任务 + 价格预警"""
    alerts = alerts or []

    task_type_names = {
        "daily_report": "📊 每日行情报告",
        "announcement": "📢 股票公告监控",
        "index_report": "📈 指数早报",
        "us_news":      "📰 美股新闻情绪",
        "macro_report": "🌐 宏观指标月报",
    }
    cond_map = {"above": "高于", "below": "低于", "change_pct": "涨跌幅超"}

    sections = []

    # ── 系统默认任务区（内置，始终推送）─────────────────
    sections.append(
        "**🔧 系统默认任务**\n"
        "🟢 📈 指数早报　`工作日 09:00`\n"
        "🟢 📊 金融日报　`工作日 15:30`"
    )

    # ── 自定义推送任务区 ──────────────────────────────
    task_buttons = []
    if tasks:
        lines = ["\n**📋 我的推送任务**\n"]
        for t in tasks:
            status = "🟢" if t.get("enabled") else "⏸️"
            type_name = task_type_names.get(t.get("task_type", ""), t.get("task_type", ""))
            cron = t.get("cron_expr", "")
            task_type = t.get("task_type", "")

            # 公告监控：额外显示股票列表
            if task_type == "announcement":
                symbols = t.get("config", {}).get("symbols", [])
                symbols_str = "、".join(symbols) if symbols else "无"
                lines.append(f"{status} #{t['id']} {type_name}　`{cron}`")
                lines.append(f"　　监控股票：{symbols_str}")
            else:
                lines.append(f"{status} #{t['id']} {type_name}　`{cron}`")

            toggle_label = "⏸ 暂停" if t.get("enabled") else "▶ 恢复"
            task_buttons.append(
                CardButton(f"{toggle_label} #{t['id']}", "toggle_task_btn", {"task_id": t["id"]})
            )
            # 公告监控：增加「删除一只股票」按钮
            if task_type == "announcement":
                task_buttons.append(
                    CardButton(f"➖ 移除股票", "del_announcement_stock", {"task_id": t["id"]})
                )
            task_buttons.append(
                CardButton(f"🗑 删除 #{t['id']}", "del_task_btn", {"task_id": t["id"]}, style="danger")
            )
        sections.append("\n".join(lines))
    else:
        sections.append("\n**📋 我的推送任务**\n暂无自定义推送任务")

    # ── 价格预警区 ─────────────────────────────────────
    alert_buttons = []
    if alerts:
        lines = ["\n**🔔 价格预警**\n"]
        for a in alerts:
            status = "🟢" if a.get("enabled") else "⏸️"
            cond = cond_map.get(a["condition"], a["condition"])
            lines.append(f"{status} #{a['id']} **{a['symbol']}** {cond} {a['threshold']}")
        sections.append("\n".join(lines))
        alert_buttons.append(
            CardButton("➖ 删除预警", "del_alert", {}, style="danger")
        )
    else:
        sections.append("\n**🔔 价格预警**\n暂无价格预警")

    return OutgoingCard(
        title="⏰ 我的定制任务",
        content="\n".join(sections),
        buttons=[
            CardButton("新建定制 ➕", "go_newtask", {}, style="primary"),
            *task_buttons,
            *alert_buttons,
        ]
    )


def newtask_type_card() -> OutgoingCard:
    """新建定制任务：价格预警 + 公告监控 + 早报内容 + 推送时间"""
    return OutgoingCard(
        title="➕ 新建定制 / 配置推送",
        content=(
            "**🔔 价格预警** — 价格/涨跌幅达到阈值时提醒\n\n"
            "**📢 公告监控** — A股重要公告自动推送（年报/分红/重大事项）\n\n"
            "**📋 自定义早报** — 选择早报包含哪些指数/数据\n\n"
            "**⏰ 推送时间** — 修改早报/晚报的推送时间"
        ),
        buttons=[
            CardButton("🔔 价格预警", "go_alert_input", {}, style="primary"),
            CardButton("📢 公告监控", "go_newtask_announcement", {}),
            CardButton("📋 自定义早报", "go_morning_modules", {"report_type": "morning"}),
            CardButton("⏰ 推送时间", "go_settings", {}),
        ]
    )


def newtask_time_card(task_type: str, options: List[Dict]) -> OutgoingCard:
    """新建定制任务：选择推送时间（按钮选项）"""
    type_names = {
        "daily_report": "每日行情报告",
        "index_report": "指数早报",
    }
    type_name = type_names.get(task_type, task_type)
    buttons = [
        CardButton(opt["label"], "newtask_confirm",
                   {"type": task_type, "cron": opt["cron"], "desc": opt["label"]})
        for opt in options
    ]
    return OutgoingCard(
        title=f"⏰ {type_name} · 选择推送时间",
        content="请选择何时推送：",
        buttons=buttons,
    )


def newtask_announcement_card() -> OutgoingCard:
    """新建股票公告监控：股票代码 + 检查时间点"""
    return OutgoingCard(
        title="📢 股票公告监控",
        content=(
            "设置后，在指定时间点自动检查重要公告（年报/分红/重大事项等）并推送。\n\n"
            "**检查时间点**示例：`9,12,15` = 每天9点、12点、15点各检查一次（工作日）"
        ),
        form=CardForm(
            fields=[
                CardFormField(
                    name="symbols",
                    label="📌 股票代码（必填）",
                    placeholder="多只用逗号分隔，如 600519,000858",
                    required=True,
                ),
                CardFormField(
                    name="check_times",
                    label="⏰ 检查时间点（选填，默认 9,12,15）",
                    placeholder="填小时数，如 9,15 或 9,12,15",
                ),
            ],
            submit_label="✅ 创建监控",
            submit_action="do_newtask_announcement",
        ),
        footer="仅推送重要公告，普通公告不打扰"
    )


def announcement_card(symbol: str, name: str, announcements: List[Dict]) -> OutgoingCard:
    """公告推送卡片（单股，手动查询用）"""
    if not announcements:
        return OutgoingCard(
            title=f"📢 {name}({symbol}) 暂无重要公告",
            content="今日暂无重要公告"
        )
    lines = []
    for ann in announcements:
        lines.append(f"**{ann['date']}** {ann['title']}")
        if ann.get("url"):
            lines.append(f"　[查看全文]({ann['url']})")
    return OutgoingCard(
        title=f"📢 {name}({symbol}) 最新公告",
        content="\n".join(lines),
        footer="仅显示重大事项/年报/分红等重要公告"
    )


def multi_announcement_card(results: List[Dict]) -> "OutgoingCard":
    """合并公告推送卡片 — 所有有新公告的股票显示在同一张卡片上
    results: [{"symbol": str, "name": str, "announcements": List[Dict]}, ...]
    """
    from datetime import datetime
    lines = []
    for r in results:
        sym, nm = r["symbol"], r["name"]
        lines.append(f"**📌 {nm}（{sym}）**")
        for ann in r["announcements"][:3]:  # 每只最多3条
            lines.append(f"　• {ann['date']} {ann['title']}")
            if ann.get("url"):
                lines.append(f"　　[查看全文]({ann['url']})")
        lines.append("")

    total = sum(len(r["announcements"]) for r in results)
    stocks_str = "、".join(r["name"] for r in results)
    return OutgoingCard(
        title=f"📢 公告监控 · {datetime.now().strftime('%m/%d')}",
        content="\n".join(lines).strip(),
        footer=f"共 {len(results)} 只股票有新公告（{stocks_str}），共 {total} 条 | 每只最多展示3条"
    )


def del_announcement_stock_card(task_id: int, symbols: List[str]) -> "OutgoingCard":
    """选择要移除的股票 — 每只一个按钮"""
    buttons = [
        CardButton(sym, "do_del_announcement_stock", {"task_id": task_id, "symbol": sym})
        for sym in symbols
    ]
    return OutgoingCard(
        title="➖ 移除监控股票",
        content=f"当前监控：{'、'.join(symbols)}\n\n点击要移除的股票代码：",
        buttons=buttons,
    )


def del_alert_card(alerts: List[Dict]) -> "OutgoingCard":
    """选择要删除的价格预警 — 每条一个按钮"""
    cond_map = {"above": "高于", "below": "低于", "change_pct": "涨跌幅超"}
    buttons = [
        CardButton(
            f"#{a['id']} {a['symbol']} {cond_map.get(a['condition'], a['condition'])} {a['threshold']}",
            "do_del_alert",
            {"alert_id": a["id"]}
        )
        for a in alerts
    ]
    return OutgoingCard(
        title="➖ 删除价格预警",
        content="点击要删除的预警条目：",
        buttons=buttons,
    )


def settings_card(cfg_vals: Dict) -> OutgoingCard:
    """系统设置卡片：早报/晚报推送时间 + 价格预警间隔 + 触发后暂停开关"""
    digest_h  = cfg_vals.get("digest_h", 15)
    digest_m  = cfg_vals.get("digest_m", 30)
    morning_h = cfg_vals.get("morning_h", 9)
    morning_m = cfg_vals.get("morning_m", 0)
    alert_min = cfg_vals.get("alert_min", 5)
    pause_until_normal = cfg_vals.get("pause_until_normal", True)

    pause_label = "触发后暂停：✅ 开启" if pause_until_normal else "触发后暂停：⬜ 关闭"

    return OutgoingCard(
        title="⚙️ 推送设置",
        content="推送时间：24 小时制 `HH:MM`，留空不修改；预警间隔：1~60 分钟整数",
        form=CardForm(
            fields=[
                CardFormField(
                    name="morning_time",
                    label="🌅 早报时间",
                    placeholder=f"当前 {morning_h:02d}:{morning_m:02d}，如 08:30",
                ),
                CardFormField(
                    name="digest_time",
                    label="🌙 晚报时间",
                    placeholder=f"当前 {digest_h:02d}:{digest_m:02d}，如 16:00",
                ),
                CardFormField(
                    name="alert_interval",
                    label="🔔 价格预警检查间隔（分钟）",
                    placeholder=f"当前 {alert_min} 分钟，建议 5~15，防止数据源限流",
                ),
            ],
            submit_label="💾 保存",
            submit_action="save_push_times",
        ),
        buttons=[
            CardButton(pause_label, "toggle_alert_pause", {})
        ],
        footer=f"早报/晚报时间修改立即生效；预警间隔修改立即生效；价格预警仅在交易时段（9:30~11:30 / 13:00~15:00）运行"
    )


# ── 早报/日报内容模块选择 ─────────────────────────────────────────────

# 所有可选模块定义
# 早报模块定义：(id, label, source, needs_av)
# 分两组：腾讯（无限制）和 Alpha Vantage（25次/天）
_TENCENT_MODULES = [
    ("a_stock",   "🇨🇳 A股指数",     "腾讯财经", False),
    ("hk_stock",  "🌏 港股恒生",     "腾讯财经", False),
    ("us_stock",  "🇺🇸 美股三大",    "腾讯财经", False),
]
_AV_MODULES = [
    ("fx",        "💵 汇率",          "Alpha Vantage", True),
    ("commodity", "🛢️ 原油/黄金",    "Alpha Vantage", True),
    ("us_news",   "📰 美股新闻情绪", "Alpha Vantage", True),
]
_ALL_MODULES = _TENCENT_MODULES + _AV_MODULES

DEFAULT_MORNING_MODULES = {"a_stock", "us_stock"}
DEFAULT_DAILY_MODULES   = {"a_stock", "us_stock"}

def morning_modules_card(report_type: str, selected: List[str]) -> OutgoingCard:
    """
    早报内容模块选择卡片（分腾讯/AV两组）
    report_type: "morning" | "daily"
    selected: 已选模块 id 列表（当前用户设置）
    """
    title_map = {"morning": "🌅 自定义早报内容", "daily": "📊 自定义日报内容"}
    title = title_map.get(report_type, "⚙️ 自定义推送内容")

    selected_set = set(selected)
    # 每个模块的详细说明
    _MODULE_DESC = {
        "a_stock":   "上证/深证/创业板指数 + 涨跌幅",
        "hk_stock":  "恒生指数 + 国企指数 + 涨跌幅",
        "us_stock":  "道琼斯/纳斯达克/标普500 + 涨跌幅",
        "fx":        "USD/CNY · EUR/USD · USD/JPY 等4组汇率",
        "commodity": "WTI原油 · 布伦特原油 · 天然气，共3条",
        "us_news":   "自选股相关新闻情绪（看多/看空/中性），共1次",
    }

    buttons = []

    lines = [
        "点击模块切换 **开启/关闭**，再点「保存」：\n",
        "**── 腾讯财经（无次数限制）──**",
    ]
    for mod_id, label, source, _ in _TENCENT_MODULES:
        is_on = mod_id in selected_set
        mark = "✅" if is_on else "⬜"
        desc = _MODULE_DESC.get(mod_id, "")
        lines.append(f"　{mark} **{label}** — {desc}")
        btn_label = f"{'关' if is_on else '开'} {label}"
        buttons.append(CardButton(
            btn_label, "toggle_morning_module",
            {"report_type": report_type, "module": mod_id,
             "current": ",".join(sorted(selected_set))},
        ))

    lines.append("\n**── Alpha Vantage（⚠️ 共25次/天，缓存1小时）──**")
    av_costs = {"fx": "消耗4次", "commodity": "消耗3次", "us_news": "消耗1次"}
    for mod_id, label, source, _ in _AV_MODULES:
        is_on = mod_id in selected_set
        mark = "✅" if is_on else "⬜"
        cost = av_costs.get(mod_id, "")
        desc = _MODULE_DESC.get(mod_id, "")
        lines.append(f"　{mark} **{label}** `{cost}` — {desc}")
        btn_label = f"{'关' if is_on else '开'} {label}"
        buttons.append(CardButton(
            btn_label, "toggle_morning_module",
            {"report_type": report_type, "module": mod_id,
             "current": ",".join(sorted(selected_set))},
        ))

    buttons.append(CardButton(
        "💾 保存设置", "save_morning_modules",
        {"report_type": report_type, "modules": ",".join(sorted(selected_set))},
        style="primary"
    ))

    return OutgoingCard(
        title=title,
        content="\n".join(lines),
        buttons=buttons,
        footer="AV 免费版 25次/天；每次推送按已选模块实际调用，缓存命中不重复消耗"
    )


# ── 美股新闻情绪卡片 ──────────────────────────────────────────────────

def news_sentiment_card(items: List[Dict], tickers: List[str] = None) -> OutgoingCard:
    """美股新闻情绪推送卡片"""
    if not items:
        return OutgoingCard(
            title="📰 美股新闻情绪",
            content="暂无相关新闻"
        )

    lines = []
    for item in items[:8]:
        sentiment = item.get("sentiment", "Neutral")
        emoji = {"Bullish": "📈", "Bearish": "📉", "Neutral": "➡️",
                 "Somewhat-Bullish": "🔼", "Somewhat-Bearish": "🔽"}.get(sentiment, "➡️")
        tickers_str = " ".join(item.get("tickers", [])[:3])
        lines.append(f"{emoji} **{item['title'][:50]}**")
        if tickers_str:
            lines.append(f"　{tickers_str}　{item.get('source', '')}")
        lines.append("")

    ticker_label = f"({', '.join(tickers)})" if tickers else ""
    return OutgoingCard(
        title=f"📰 美股新闻情绪 {ticker_label} · {datetime.now().strftime('%m/%d')}",
        content="\n".join(lines).rstrip(),
        footer="数据来源: Alpha Vantage · 情绪: 📈看多 ➡️中性 📉看空"
    )


# ── 宏观经济指标卡片 ──────────────────────────────────────────────────

def macro_report_card(data: List[Dict]) -> OutgoingCard:
    """宏观经济指标卡片"""
    if not data:
        return OutgoingCard(
            title="📊 宏观经济指标",
            content="暂无数据"
        )

    lines = []
    for item in data:
        value = item.get("value", 0)
        unit = item.get("unit", "")
        change = item.get("change", 0)
        date = item.get("date", "")[:7]  # YYYY-MM

        change_str = ""
        if change != 0:
            arrow = "▲" if change > 0 else "▼"
            change_str = f"　{arrow}{abs(change):.3f}"

        lines.append(f"**{item['name']}**　{value}{unit}{change_str}　`{date}`")

    return OutgoingCard(
        title=f"🌐 宏观经济指标 · {datetime.now().strftime('%m/%d')}",
        content="\n".join(lines),
        footer="数据来源: Alpha Vantage · 月度/季度更新（消耗4次配额，当日内缓存）"
    )


def macro_query_card(data: List[Dict]) -> OutgoingCard:
    """美国宏观指标按需查询卡片（手动触发）"""
    if not data:
        return OutgoingCard(
            title="🇺🇸 美国宏观指标",
            content="⚠️ 暂无数据，可能是 Alpha Vantage 未配置或配额已耗尽",
            footer="Alpha Vantage 免费版 25次/天"
        )

    lines = []
    indicator_desc = {
        "FEDERAL_FUNDS_RATE": "联邦基金利率",
        "CPI":                "CPI（消费者物价）",
        "UNEMPLOYMENT":       "失业率",
        "TREASURY_YIELD":     "10年期国债收益率",
    }
    for item in data:
        name = indicator_desc.get(item.get("indicator", ""), item.get("name", ""))
        value = item.get("value", 0)
        unit = item.get("unit", "")
        change = item.get("change", 0)
        date = item.get("date", "")[:7]
        change_str = ""
        if change != 0:
            arrow = "▲" if change > 0 else "▼"
            change_str = f"　{arrow}{abs(change):.3f}"
        lines.append(f"**{name}**　{value}{unit}{change_str}　`{date}`")

    return OutgoingCard(
        title=f"🇺🇸 美国宏观指标 · {datetime.now().strftime('%m/%d')}",
        content="\n".join(lines),
        footer="数据来源: Alpha Vantage · 每次查询消耗4次配额，当日内缓存"
    )
