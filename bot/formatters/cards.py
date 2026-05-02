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
            lines.append(f"**{q.get('name', sym)}** `{sym}`　{q['price']}　{trend}")
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
                      announcements: List[Dict], forex_data: List[Dict]) -> OutgoingCard:
    """每日聚合日报卡片"""
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

    # 汇率/大宗
    if forex_data:
        lines.append("**💱 汇率 & 大宗**")
        for f in forex_data:
            trend = _trend(f.get("change_pct", 0))
            lines.append(f"　{f.get('name', f.get('symbol', ''))}　{f['price']}　{trend}")

    return OutgoingCard(
        title=f"📊 金融日报 · {datetime.now().strftime('%m/%d %H:%M')}",
        content="\n".join(lines) if lines else "暂无数据",
        buttons=[CardButton("⚙️ 管理推送", "go_tasks", {})],
        footer="默认推送：工作日收盘后  |  /digest 切换推送模式"
    )


def menu_card() -> OutgoingCard:
    """主菜单卡片（全功能按钮入口）"""
    return OutgoingCard(
        title="🤖 综合秘书 · 主菜单",
        content="请选择要操作的功能：",
        buttons=[
            # 金融查询行
            CardButton("查行情 🔍", "go_quote", {}, style="primary"),
            CardButton("我的自选 ⭐", "go_watchlist", {}),
            CardButton("删除自选 🗑", "go_remove_watchlist", {}),
            # 定制任务行
            CardButton("定制任务 ⏰", "go_tasks", {}, style="primary"),
            CardButton("新建定制 ➕", "go_newtask", {}),
            CardButton("系统设置 ⚙️", "go_settings", {}),
            # 控制行
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
    }
    cond_map = {"above": "高于", "below": "低于", "change_pct": "涨跌幅超"}

    sections = []

    # ── 推送任务区 ─────────────────────────────────────
    if tasks:
        lines = ["**📋 推送任务**\n"]
        for t in tasks:
            status = "🟢" if t.get("enabled") else "⏸️"
            type_name = task_type_names.get(t.get("task_type", ""), t.get("task_type", ""))
            cron = t.get("cron_expr", "")
            lines.append(f"{status} #{t['id']} {type_name}　`{cron}`")
        sections.append("\n".join(lines))
    else:
        sections.append("**📋 推送任务**\n暂无推送任务")

    # ── 价格预警区 ─────────────────────────────────────
    if alerts:
        lines = ["\n**🔔 价格预警**\n"]
        for a in alerts:
            status = "🟢" if a.get("enabled") else "⏸️"
            cond = cond_map.get(a["condition"], a["condition"])
            lines.append(f"{status} #{a['id']} **{a['symbol']}** {cond} {a['threshold']}")
        sections.append("\n".join(lines))
    else:
        sections.append("\n**🔔 价格预警**\n暂无价格预警")

    return OutgoingCard(
        title="⏰ 我的定制任务",
        content="\n".join(sections),
        buttons=[
            CardButton("新建定制 ➕", "go_newtask", {}, style="primary"),
        ]
    )


def newtask_type_card() -> OutgoingCard:
    """新建定制任务：选择类型"""
    return OutgoingCard(
        title="➕ 新建定制任务",
        content="请选择任务类型：",
        buttons=[
            CardButton("📊 每日行情报告", "newtask_type", {"type": "daily_report"}, style="primary"),
            CardButton("📢 股票公告监控", "newtask_type", {"type": "announcement"}),
            CardButton("🔔 价格预警设置", "go_alert_input", {}),
            CardButton("📈 指数早报", "newtask_type", {"type": "index_report"}),
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
    """新建股票公告监控：输入股票代码"""
    return OutgoingCard(
        title="📢 股票公告监控 · 输入股票",
        content="请输入要监控的股票代码或名称\n多只股票用逗号分隔，如 `600519, 000858`",
        input_field=CardInput(
            name="do_newtask_announcement.symbols",
            placeholder="如 600519 / 贵州茅台 / 600519,000858",
            action="do_newtask_announcement",
        ),
    )


def announcement_card(symbol: str, name: str, announcements: List[Dict]) -> OutgoingCard:
    """公告推送卡片"""
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


def settings_card(cfg_vals: Dict) -> OutgoingCard:
    """系统设置卡片"""
    alert_min = cfg_vals.get("alert_min", 5)
    digest_h  = cfg_vals.get("digest_h", 15)
    digest_m  = cfg_vals.get("digest_m", 30)
    morning_h = cfg_vals.get("morning_h", 9)
    morning_m = cfg_vals.get("morning_m", 0)

    content = (
        "**⏱ 价格预警检查频率**\n"
        f"　当前：每 **{alert_min}** 分钟检查一次\n"
        "　修改：`/settings alert_interval 分钟数`\n"
        "　例如：`/settings alert_interval 10`\n\n"
        "**📊 收盘日报时间**\n"
        f"　当前：每工作日 **{digest_h}:{digest_m:02d}**\n"
        "　修改：`/settings digest_time HH:MM`\n"
        "　例如：`/settings digest_time 16:00`\n\n"
        "**🌅 早报时间**\n"
        f"　当前：每工作日 **{morning_h}:{morning_m:02d}**\n"
        "　修改：`/settings morning_time HH:MM`\n"
        "　例如：`/settings morning_time 08:30`\n\n"
        "⚠️ 修改后重启机器人生效（`bash restart.sh`）"
    )
    return OutgoingCard(
        title="⚙️ 系统设置",
        content=content,
        footer="配置保存在 config.py"
    )
