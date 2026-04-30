# 综合秘书机器人 操作手册 & 技术文档

**版本**: v2.0  
**更新日期**: 2026-04-30

---

## 目录

1. [系统概述](#1-系统概述)
2. [快速开始](#2-快速开始)
3. [配置说明](#3-配置说明)
4. [运行方式](#4-运行方式)
5. [使用指南](#5-使用指南)
6. [功能模块说明](#6-功能模块说明)
7. [文件结构](#7-文件结构)
8. [数据库结构](#8-数据库结构)
9. [常见问题](#9-常见问题)

---

## 1. 系统概述

本系统是一个以**飞书**为主平台的个人综合秘书机器人（v2），核心特点：

- **双向对话**：不只是推送，还能主动查询
- **卡片交互**：按钮引导操作，无需记忆指令
- **多步对话状态机**：复杂操作（如预警设置）通过对话逐步引导完成
- **灵活的定时推送**：支持多种任务类型，自定义触发时间

### 支持的资产类型

| 类型 | 示例 | 数据源 |
|------|------|--------|
| A股 | `600519`（贵州茅台）、`000858` | 腾讯财经 |
| 港股 | `00700`（腾讯控股）、`09988` | 腾讯财经 |
| 加密货币 | `BTC`、`ETH`、`SOL` | Binance |
| 全球指数 | `SPX`（标普）、`NDX`（纳指）、`DJI`（道指） | 腾讯财经 |

---

## 2. 快速开始

### 2.1 安装依赖

```bash
pip3 install -r requirements.txt
```

### 2.2 配置飞书机器人（首次使用）

```bash
python feishu_setup.py
```

- 终端打印二维码，用飞书 App 扫码授权
- 扫码成功后自动将 `FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_OPEN_ID` 写入 `config.py`

> ⚠️ 必须在系统终端（VS Code Terminal 等）中运行，不是在聊天窗口里。

### 2.3 编辑配置文件

```bash
cp config.example.py config.py
# 如未使用 feishu_setup.py，手动填写飞书凭据
```

### 2.4 启动服务

```bash
bash restart.sh
```

服务正常启动后，在飞书向机器人发送 `/menu` 即可看到功能面板。

### 2.5 停止服务

```bash
bash stop.sh
```

---

## 3. 配置说明

所有配置在 `config.py`（从 `config.example.py` 复制）。

### 3.1 飞书应用（必填）

```python
FEISHU_APP_ID     = "cli_xxxxxxxxxxxxxxxx"  # 飞书应用 App ID
FEISHU_APP_SECRET = "xxxxxxxxxxxxxxxxxxxxxxx"  # 飞书应用 App Secret
FEISHU_OPEN_ID    = "ou_xxxxxxxxxxxxxxxx"   # 你的飞书用户 Open ID
```

> 通过 `feishu_setup.py` 扫码后自动填写，无需手动获取。

### 3.2 可选：Alpha Vantage

```python
ALPHA_VANTAGE_API_KEY = "your_key"  # 汇率/原油数据，免费500次/天
```

申请地址：https://www.alphavantage.co/support/#api-key

### 3.3 调度配置

```python
# 价格预警检查频率（分钟）
PRICE_ALERT_INTERVAL_MINUTES = 5

# 每日行情报告推送时间
DAILY_DIGEST_HOUR   = 15
DAILY_DIGEST_MINUTE = 30

# 指数早报推送时间
MORNING_REPORT_HOUR   = 9
MORNING_REPORT_MINUTE = 0
```

> 修改调度时间后需重启生效：`bash restart.sh`

也可通过指令动态修改（重启前临时生效）：

```
/settings digest_time 16:00
/settings morning_time 08:30
/settings alert_interval 10
```

### 3.4 可选：Telegram

```python
TELEGRAM_BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
TELEGRAM_CHAT_ID   = "你的Chat ID"
```

### 3.5 日志

```python
LOG_LEVEL = "INFO"              # DEBUG / INFO / WARNING / ERROR
LOG_FILE  = "price_monitor.log"
```

---

## 4. 运行方式

### 4.1 脚本管理

```bash
# 后台启动（推荐）
bash restart.sh

# 停止所有服务
bash stop.sh

# 查看实时日志
tail -f price_monitor.log
```

### 4.2 直接运行（调试用）

```bash
python3 bot/app.py
```

### 4.3 systemd 服务（Linux 长期运行）

```bash
sudo cp price-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable price-monitor
sudo systemctl start price-monitor
sudo systemctl status price-monitor
```

---

## 5. 使用指南

### 5.1 主入口：菜单卡片

发送 `/menu` 或 `菜单` 调出全功能按钮面板：

| 按钮 | 功能 |
|------|------|
| 查行情 🔍 | 提示输入代码/名称 |
| 我的自选 ⭐ | 显示自选列表（含删除按钮） |
| 删除自选 🗑 | 同上，显示带删除按钮的列表 |
| 价格预警 🔔 | 显示当前预警列表 |
| 定时任务 ⏰ | 显示任务列表 |
| 新建任务 ➕ | 进入任务类型选择卡片 |
| 系统设置 ⚙️ | 显示当前配置 |
| 免打扰 🔕 | 切换免打扰模式 |

### 5.2 行情查询

```
/quote 600519        # A股（6位数字）
/quote 00700         # 港股（5位以内数字）
/quote BTC           # 加密货币
/quote SPX           # 全球指数别名
/quote 贵州茅台      # 按名称搜索（模糊匹配）
```

行情卡片底部有两个快捷按钮：
- **加入自选 ⭐** — 直接添加到自选列表
- **设置预警 🔔** — 跳转到预警设置卡片

### 5.3 自选管理

```
/watchlist      # 查看自选列表
/add 600519     # 添加自选
/remove 600519  # 删除自选
```

自选列表卡片中，每条标的旁有 `🗑 删除` 按钮，点击后立即删除并刷新列表。

### 5.4 价格预警设置

**推荐方式（按钮引导）：**

1. 查询行情 → 点击「设置预警 🔔」
2. 弹出预警卡片，选择预警类型：
   - 📈 **涨幅预警** — 当日涨幅超过 X%
   - 📉 **跌幅预警** — 当日跌幅超过 X%
   - ⬆️ **价格上限** — 价格超过 X 时提醒
   - ⬇️ **价格下限** — 价格低于 X 时提醒
3. 机器人提示输入数值，直接发送数字即可
4. 发送 `/cancel` 取消等待

**文字指令方式：**

```
/alert 600519 above 2000       # 价格超过2000提醒
/alert 600519 below 1500       # 价格低于1500提醒
/alert 600519 change_pct 5     # 涨幅超过5%提醒
/alert 600519 change_pct -5    # 跌幅超过5%提醒
/alert                         # 查看所有预警
```

**预警触发说明：**
- 每5分钟检查一次（可配置）
- 同一预警2小时内不重复推送
- 仅当满足条件时推送，不产生噪音

### 5.5 定时任务管理

```
/tasks          # 查看所有任务及状态
/newtask        # 新建任务（卡片选择类型）
/deltask 3      # 删除 #3 号任务
/pause 3        # 暂停/恢复 #3 号任务
```

**任务类型：**

| 类型 | 说明 | 状态 |
|------|------|------|
| `daily_report` | 每日收盘行情报告 | ✅ 可用 |
| `index_report` | 每日指数早报 | ✅ 可用 |
| `price_alert` | 价格突破预警（实时） | ✅ 可用 |
| `announcement` | 股票公告监控 | ⚠️ 数据源不稳定 |

### 5.6 推送控制

```
/quiet              # 开启/关闭免打扰（全局静音）
/mute 600519 2h     # 屏蔽 600519 推送2小时（仅对该标的）
```

### 5.7 系统设置

```
/settings                           # 查看当前配置
/settings alert_interval 10         # 预警检查间隔改为10分钟
/settings digest_time 16:00         # 日报时间改为16:00
/settings morning_time 08:30        # 早报时间改为08:30
```

---

## 6. 功能模块说明

### 6.1 bot/app.py — 主入口

- 初始化飞书适配器 + 调度引擎
- 注册消息处理回调
- 优雅退出（SIGINT/SIGTERM）

### 6.2 bot/adapters/feishu_adapter.py — 飞书适配器

| 功能 | 说明 |
|------|------|
| 连接方式 | lark-oapi WebSocket 长连接，无需公网 IP |
| 自动重连 | `auto_reconnect=True`，断线自动恢复 |
| 消息接收 | 文本消息 + 卡片按钮回调 |
| 消息发送 | 纯文本 / 富交互卡片（按钮）|
| 卡片渲染 | 按钮自动每3个换一行，避免挤在一行 |

**关键方法：**

```python
adapter.send_text(user_id, "消息内容")
adapter.send_card(user_id, OutgoingCard(...))
adapter.send_success(user_id, "操作成功")
```

### 6.3 bot/handlers/commands.py — 指令处理器

- **文字指令路由**：解析 `/command` 并调用对应方法
- **按钮回调路由**：根据 `action` 字段分发处理
- **多步对话状态机**：`_pending_input` 字典记录等待输入的用户
  - 用于预警数值输入等需要多轮交互的场景
  - 发送 `/cancel` 可取消任何挂起状态

**回调 action 一览：**

| action | 触发 | 说明 |
|--------|------|------|
| `go_quote` | 菜单 | 提示输入代码查询 |
| `go_watchlist` | 菜单 | 显示自选列表 |
| `go_remove_watchlist` | 菜单 | 显示带删除按钮的自选列表 |
| `go_alerts` | 菜单 | 显示预警列表 |
| `go_tasks` | 菜单 | 显示任务列表 |
| `go_newtask` | 菜单 | 新建任务选择卡片 |
| `go_settings` | 菜单 | 显示系统设置 |
| `go_quiet` | 菜单 | 切换免打扰 |
| `go_add` | 自选卡片 | 提示输入添加代码 |
| `add_watchlist` | 行情卡片 | 立即添加到自选 |
| `remove_watchlist` | 自选列表 | 立即删除指定标的 |
| `add_alert` | 行情卡片 | 显示预警类型卡片 |
| `alert_type` | 预警卡片 | 设置 pending 状态等待数值输入 |
| `newtask_type` | 任务卡片 | 任务类型选定后提示配置 |

### 6.4 bot/scheduler.py — 任务调度引擎

基于 APScheduler BackgroundScheduler，时区 `Asia/Shanghai`。

**内置任务：**

| 任务 | cron | 说明 |
|------|------|------|
| 每日行情报告 | `30 15 * * 1-5` | 工作日 15:30 |
| 指数早报 | `0 9 * * 1-5` | 工作日 09:00 |
| 价格预警检查 | `*/5 * * * *` | 每5分钟 |

**预警检查逻辑：**
- 拉取所有用户启用的预警
- 查询实时行情
- 条件匹配：`above` / `below` / `change_pct`（正值=涨幅，负值=跌幅）
- 2小时内相同预警不重复推送（通过 MD5 hash + push_log 表实现）

### 6.5 bot/formatters/cards.py — 卡片模板

| 函数 | 说明 |
|------|------|
| `menu_card()` | 主菜单（8个按钮，3列布局） |
| `help_card()` | 指令手册（纯文字） |
| `quote_card(data)` | 单支行情卡片 |
| `watchlist_card(items, quotes)` | 自选列表（含删除按钮） |
| `alert_setup_card(symbol, name)` | 预警类型选择卡片 |
| `tasks_card(tasks)` | 任务列表卡片 |
| `newtask_type_card()` | 新建任务类型选择 |
| `daily_digest_card(...)` | 每日日报卡片 |
| `settings_card(cfg_vals)` | 系统设置展示卡片 |

### 6.6 data/db.py — SQLite 数据层

```python
# 用户
upsert_user(user_id, platform, username)
get_user_settings(user_id)
update_user_settings(user_id, settings)

# 自选
add_watchlist(user_id, symbol, asset_type, name)
remove_watchlist(user_id, symbol)
get_watchlist(user_id)

# 价格预警
add_alert(user_id, symbol, condition, threshold)
get_alerts(user_id, enabled_only)
toggle_alert(alert_id, enabled)

# 定时任务
add_task(user_id, task_type, config, cron_expr)
get_tasks(user_id, enabled_only)
get_all_enabled_tasks()
toggle_task(task_id, enabled)
delete_task(task_id)

# 推送去重
log_push(user_id, task_id, content_hash)
already_pushed(user_id, content_hash, within_hours)
```

### 6.7 data/sources/akshare_source.py — 行情数据

```python
auto_quote(symbol)      # 自动识别资产类型，返回行情字典
search_stock(keyword)   # 按名称搜索 A股代码
get_index_quotes()      # 批量获取主要指数行情
get_stock_announcements(symbol)  # 获取公告（AKShare，不稳定）
```

**返回的行情字典格式：**

```python
{
    "symbol": "600519",
    "name": "贵州茅台",
    "price": 1680.0,
    "change": 12.5,
    "change_pct": 0.75,
    "high": 1690.0,
    "low": 1665.0,
    "pe_ratio": 28.5,
    "source": "腾讯财经",
    "timestamp": "15:02:33"
}
```

---

## 7. 文件结构

```
.
├── bot/
│   ├── app.py                  # 主入口
│   ├── adapters/
│   │   ├── base.py             # BaseAdapter / IncomingMessage / OutgoingCard / CardButton
│   │   ├── feishu_adapter.py   # 飞书 WebSocket 适配器（主）
│   │   └── telegram_adapter.py # Telegram 适配器（次）
│   ├── handlers/
│   │   └── commands.py         # 指令路由 + 按钮回调 + 多步对话
│   ├── scheduler.py            # APScheduler 调度引擎
│   └── formatters/
│       └── cards.py            # 卡片模板
├── data/
│   ├── sources/
│   │   └── akshare_source.py   # 行情数据（腾讯财经 + Binance）
│   ├── db.py                   # SQLite 操作层
│   └── secretary.db            # SQLite 数据库（自动生成）
├── config.py                   # 实际配置（不入 Git）
├── config.example.py           # 配置模板
├── feishu_setup.py             # 飞书扫码一键配置工具
├── restart.sh                  # 后台重启脚本
├── stop.sh                     # 停止所有服务脚本
├── price-monitor.service       # systemd 服务配置（Linux）
├── requirements.txt
├── price_monitor.log           # 运行日志（自动生成）
├── README.md                   # 项目说明
└── MANUAL.md                   # 本文档
```

---

## 8. 数据库结构

数据库文件：`data/secretary.db`（SQLite）

| 表名 | 用途 |
|------|------|
| `users` | 用户信息 + 设置（quiet_mode 等） |
| `watchlist` | 自选标的列表 |
| `price_alerts` | 价格预警规则 |
| `scheduled_tasks` | 用户自定义定时任务 |
| `push_log` | 推送记录（用于去重冷却） |

---

## 9. 常见问题

**Q: 发送 `/menu` 后卡片按钮点了没反应？**  
A: 检查日志是否有报错：`tail -f price_monitor.log | grep ERROR`。常见原因：服务未运行、飞书 WebSocket 断连。重启服务：`bash restart.sh`

**Q: 行情查询返回"查询失败"？**  
A: 腾讯财经 API 免费但偶有限速，稍后重试。加密货币走 Binance API，需要网络能访问 `api.binance.com`。

**Q: 修改了配置，什么时候生效？**  
A: `config.py` 中的调度时间类配置（`DAILY_DIGEST_HOUR` 等）需重启生效。通过 `/settings` 指令修改的值立即生效但不持久化，重启后恢复 `config.py` 中的值。

**Q: 日经指数查不到？**  
A: 部分非主流全球指数腾讯财经 API 不支持。目前支持的指数别名：`SPX`（标普500）、`NDX`（纳指100）、`DJI`（道琼斯）、`HSI`（恒生）、`000001`（上证）、`399001`（深证成指）。

**Q: 价格预警已设置但没收到推送？**  
A: 检查：① 条件是否已满足（行情是否达到阈值）；② 2小时冷却期内是否已推送过；③ 免打扰模式是否开启（发送 `/quiet` 查看状态）。

**Q: 想停止某只股票的所有预警推送？**  
A: 使用 `/mute 600519 Xh` 临时屏蔽（X 为小时数），或通过 `/alert` 查询后手动删除对应预警规则。

---

*综合秘书机器人 v2.0 — 本文档随代码同步维护*

