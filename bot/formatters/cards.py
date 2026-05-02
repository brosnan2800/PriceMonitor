#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
消息格式化模块

feishu_card.py  → 飞书 MessageCard 专用模板（最终由 FeishuAdapter 渲染）
本模块提供：OutgoingCard 快速构建函数，供 handlers 调用
"""

from datetime import datetime
from typing import Dict, List, Optional

from bot.adapters.base import CardButton, CardInput, OutgoingCard


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
            name="symbol",
            placeholder="输入代码或名称，如 600519 / BTC / AAPL",
            action="do_quote",
            submit_label="查询 🔍",
        ),
        footer="也可直接发送 /quote 600519"
    )



    """单支行情卡片"""
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
            # 预警&任务行
            CardButton("价格预警 🔔", "go_alerts", {}),
            CardButton("定时任务 ⏰", "go_tasks", {}),
            CardButton("新建任务 ➕", "go_newtask", {}),
            # 控制行
            CardButton("系统设置 ⚙️", "go_settings", {}),
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
        "**⏰ 定时任务**\n"
        "　`/tasks` 　　查看所有任务\n"
        "　`/newtask` 　新建推送任务\n"
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
    """价格预警设置卡片（独立卡片，4个分支按钮）"""
    display = f"{name} ({symbol})" if name and name != symbol else symbol
    content = (
        f"**标的：{display}**\n\n"
        "请选择预警类型：\n\n"
        "📈 **涨幅预警** — 当日涨幅超过指定百分比时提醒\n"
        "📉 **跌幅预警** — 当日跌幅超过指定百分比时提醒\n"
        "⬆️ **价格上限** — 价格高于指定值时提醒\n"
        "⬇️ **价格下限** — 价格低于指定值时提醒"
    )
    return OutgoingCard(
        title="🔔 设置价格预警",
        content=content,
        buttons=[
            CardButton("📈 涨幅预警", "alert_type",
                       {"symbol": symbol, "nm": name, "cond": "rise_pct"}, style="primary"),
            CardButton("📉 跌幅预警", "alert_type",
                       {"symbol": symbol, "nm": name, "cond": "fall_pct"}),
            CardButton("⬆️ 价格上限", "alert_type",
                       {"symbol": symbol, "nm": name, "cond": "above"}),
            CardButton("⬇️ 价格下限", "alert_type",
                       {"symbol": symbol, "nm": name, "cond": "below"}),
        ],
        footer="选择后按提示输入数值即可完成设置"
    )


def tasks_card(tasks: List[Dict]) -> OutgoingCard:
    """任务列表卡片"""
    if not tasks:
        return OutgoingCard(
            title="⏰ 我的定时任务",
            content="还没有任何定时任务\n\n发送 `/newtask` 创建第一个任务",
            buttons=[CardButton("新建任务 ➕", "go_newtask", {}, style="primary")]
        )

    task_type_names = {
        "daily_report": "每日行情报告",
        "announcement": "股票公告监控",
        "price_alert": "价格突破预警",
        "index_report": "指数早报",
    }
    lines = []
    for t in tasks:
        status = "🟢" if t.get("enabled") else "⏸️"
        type_name = task_type_names.get(t.get("task_type", ""), t.get("task_type", ""))
        cron = t.get("cron_expr", "")
        lines.append(f"{status} **#{t['id']} {type_name}**　`{cron}`")

    return OutgoingCard(
        title=f"⏰ 我的定时任务 ({len(tasks)} 个)",
        content="\n".join(lines),
        buttons=[
            CardButton("新建任务 ➕", "go_newtask", {}, style="primary"),
            CardButton("管理任务 ⚙️", "go_task_manage", {}),
        ]
    )


def newtask_type_card() -> OutgoingCard:
    """新建任务：选择类型"""
    return OutgoingCard(
        title="➕ 新建定时任务",
        content="请选择任务类型：",
        buttons=[
            CardButton("📊 每日行情报告", "newtask_type", {"type": "daily_report"}, style="primary"),
            CardButton("📢 股票公告监控", "newtask_type", {"type": "announcement"}),
            CardButton("🔔 价格突破预警", "newtask_type", {"type": "price_alert"}),
            CardButton("📈 指数早报", "newtask_type", {"type": "index_report"}),
        ]
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
