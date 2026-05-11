# 综合秘书机器人 操作手册 & 技术文档

**版本**: v2.2  
**更新日期**: 2026-05-08

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

本系统是一个以**飞书**为主平台的个人综合秘书机器人（v2.2），单用户设计，核心特点：

- **双向对话**：不只是推送，还能主动查询
- **卡片交互**：按钮引导操作，无需记忆指令
- **卡片原地刷新**：模块 toggle 等操作直接更新原卡片，不刷屏
- **早晚报分离**：早报可选模块（腾讯组 + AV组），晚报固定内容不耗 AV 配额
- **价格预警防刷屏**：触发后等价格回归正常区间才重推；仅在交易时段运行
- **美国宏观按需查询**：手动触发，异步返回

### 支持的资产类型

| 类型 | 示例 | 数据源 | 支持名称搜索 |
|------|------|--------|------------|
| A股 | `600519`（贵州茅台）、`000858` | 腾讯财经 | ✅ |
| 港股 | `00700`（腾讯控股）、`09988` | 腾讯财经 | — |
| 美股 | `AAPL`、`NVDA`、`TSLA` | 腾讯财经 | ✅（中文名） |
| 加密货币 | `BTC`、`ETH`、`SOL` | Binance | — |
| 全球指数 | `SPX`（标普）、`NDX`（纳指）、`DJI`（道指）、`HSI`（恒生） | 腾讯财经 | — |

---

## 2. 快速开始

支持两种部署方式，推荐 Docker。

---

### 方式一：Docker 部署（推荐）

> **前提**
> 1. 安装 [Docker Desktop](https://docs.docker.com/get-docker/)（Mac/Windows）或 Docker Engine（Linux）
> 2. 拥有飞书企业账号（个人账号无法创建应用）
>    - 免费注册测试企业：[open.feishu.cn](https://open.feishu.cn) → 立即使用 → 创建企业 → 选"体验版"
>    - 在飞书开发者控制台创建一个自建应用（PersonalAgent 类型），拿到 App ID 和 App Secret

#### 2.1 初次部署

```bash
# 1. 克隆项目
git clone https://github.com/brosnan2800/PriceMonitor.git
cd PriceMonitor

# 2. 创建配置文件（密钥文件，不入 Git）
cp .env.example .env

# 3. 启动容器（首次构建镜像需要约 1-2 分钟）
docker-compose up -d

# 4. 飞书扫码配置（在容器内运行，终端会显示二维码）
#   第一次看到“飞书尚未配置”提示是正常现象
docker exec -it secretary-bot python3 feishu_setup.py
#   → 用飞书 App 扫码授权
#   → 扫码成功后自动将凭据写入 .env

# 5. 重启容器读取新凭据
docker-compose restart

# 6. 查看日志确认连接成功
docker-compose logs -f
```

#### 2.2 Alpha Vantage Key（可选）

用于早报的汇率/原油/新闻情绪模块和手动宏观查询：

1. 访问 [https://www.alphavantage.co/support/#api-key](https://www.alphavantage.co/support/#api-key) 免费注册
2. 复制你的 API Key
3. 编辑 `.env`，填入 `ALPHA_VANTAGE_API_KEY=你的key`
4. `docker-compose restart`

#### 2.3 日常管理

```bash
docker-compose up -d      # 启动（后台）
docker-compose down       # 停止
docker-compose restart    # 重启
docker-compose logs -f    # 实时日志
docker-compose pull && docker-compose up -d --build  # 更新代码后重新构建
```

> ✅ **数据安全**：`data/`（SQLite 数据库）和 `logs/` 目录通过 volume 挂载，
> 容器删除重建不会丢失自选/预警数据。
>
> ✅ **开机自启**：`docker-compose.yml` 使用 `restart: always`，服务器或 NAS 重启（含定时开关机）后 Docker daemon 拉起时会自动重新启动容器，无需人工干预。

---

### 方式二：本地直接运行

#### 2.4 安装依赖

```bash
pip3 install -r requirements.txt
```

#### 2.5 配置飞书机器人（首次使用）

```bash
python3 feishu_setup.py
```

- 终端打印二维码，用飞书 App 扫码授权
- 扫码成功后自动将凭据写入 `config.py` 和 `.env`

> ⚠️ 必须在系统终端（VS Code Terminal 等）中运行，不是在聊天窗口里。

#### 2.6 编辑配置文件

```bash
cp config.example.py config.py
# 如未使用 feishu_setup.py，手动填写飞书凭据
# 可选：填写 ALPHA_VANTAGE_API_KEY 以启用 AV 模块
```

#### 2.7 启动服务

```bash
bash restart.sh
```

服务正常启动后，在飞书向机器人发送 `/menu` 即可看到功能面板。

#### 2.8 停止服务

```bash
bash stop.sh
```

---

## 3. 配置说明

配置支持两种方式，优先级：**环境变量 / `.env` 文件** > `config.py`

- **Docker 部署**：编辑 `.env`（`feishu_setup.py` 扫码后自动填入飞书凭据）
- **本地部署**：编辑 `config.py`（从 `config.example.py` 复制）

> Docker 部署时，**不要进容器里改配置**。应修改宿主机项目目录下的 `.env`（如 `/root/Desktop/priceMonitor/.env`）；`docker-compose.yml` 会把它注入并挂载到容器内。修改后执行 `docker-compose restart` 重新加载。

### 3.1 飞书应用（必填）

```bash
# .env 格式
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxx
FEISHU_OPEN_ID=ou_xxxxxxxxxxxxxxxx
```

> 通过 `feishu_setup.py` 扫码后自动填写，无需手动获取。
> `.env` 修改后执行 `docker-compose restart` 即可重新加载配置。

### 3.2 可选：Alpha Vantage

```bash
ALPHA_VANTAGE_API_KEY=your_key   # 免费 25次/天
```

申请地址：https://www.alphavantage.co/support/#api-key

**AV 配额分配（25次/天）：**
| 早报模块 | 消耗次数 |
|---------|---------|
| 汇率（fx） | 4次 |
| 原油/黄金（commodity） | 3次 |
| 美股新闻情绪（us_news） | 1次 |
| 美国宏观查询（手动） | 4次 |

> 晚报不调 AV，配额全留给早报和手动查询。缓存1小时，命中不重复消耗。

### 3.3 调度配置

```bash
PRICE_ALERT_INTERVAL_MINUTES=5   # 价格预警检查频率（分钟）
DAILY_DIGEST_HOUR=15             # 晚报时间
DAILY_DIGEST_MINUTE=30
MORNING_REPORT_HOUR=9            # 早报时间
MORNING_REPORT_MINUTE=0
```

> 可通过菜单「新建定制 → 推送时间」卡片动态修改，无需重启，仅影响自己。

### 3.4 可选：Telegram

```bash
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=你的Chat ID
```

### 3.5 日志

```bash
LOG_LEVEL=INFO
LOG_FILE=logs/secretary.log   # Docker 模式建议写到 logs/ 目录
```

---

## 4. 运行方式

### 4.1 Docker 管理（推荐）

```bash
docker-compose up -d       # 后台启动
docker-compose down        # 停止
docker-compose restart     # 重启
docker-compose logs -f     # 实时日志
docker-compose up -d --build  # 更新代码后重新构建镜像
```

### 4.2 本地脚本管理

```bash
bash restart.sh            # 后台启动
bash stop.sh               # 停止所有服务
tail -f secretary.log      # 查看实时日志
```

### 4.3 直接运行（调试用）

```bash
python3 bot/app.py
```

### 4.4 systemd 服务（Linux 长期运行，非 Docker）

修改 `price-monitor.service` 中的 `WorkingDirectory` 为实际路径后：

```bash
sudo cp price-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable price-monitor
sudo systemctl start price-monitor
```

---

## 5. 使用指南

### 5.1 主菜单

发送 `/menu` 或 `菜单`：

| 按钮 | 功能 |
|------|------|
| 查行情 🔍 | 提示输入代码/名称 |
| 我的自选 ⭐ | 显示自选列表（含删除、最高/最低价） |
| 定制任务 ⏰ | 显示任务列表（价格预警等） |
| 新建定制 ➕ | 进入三项快捷配置（见下） |
| 🇺🇸 美国宏观 | 异步查询宏观指标（约15-50秒） |
| 免打扰 🔕 | 切换免打扰模式 |
| 重启服务 🔄 | 触发后台重启 |

**新建定制** 卡片包含：

| 按钮 | 功能 |
|------|------|
| 🔔 价格预警 | 设置价格突破提醒 |
| 📋 自定义早报 | 选择早报包含的模块 |
| ⏰ 推送时间 | 修改早报/晚报推送时间 |

### 5.2 行情查询

```
/quote 600519        # A股（6位数字）
/quote 00700         # 港股（5位以内数字）
/quote AAPL          # 美股代码（英文字母，1-5位）
/quote SPX           # 全球指数别名
/quote BTC           # 加密货币
/quote 贵州茅台      # A股按名称搜索
/quote 英伟达        # 美股按中文名搜索（返回 NVDA）
```

> ⚠️ **名称搜索说明**：名称搜索依赖东方财富搜索接口（≤5秒超时）。若网络波动导致超时，会提示"未找到，请改用代码查询"——此时直接输入代码（如 `NVDA`）即可正常查询。

### 5.3 自选管理

```
/watchlist      # 查看自选列表（含最高/最低价）
/add 600519     # 添加自选
/remove 600519  # 删除自选
```

### 5.4 价格预警设置

**推荐方式（按钮引导）：**

1. 查询行情 → 点击「设置预警 🔔」
2. 选择预警类型：📈 涨幅 / 📉 跌幅 / ⬆️ 价格上限 / ⬇️ 价格下限
3. 机器人提示输入数值，直接发送数字即可

**文字指令方式：**
```
/alert 600519 above 2000
/alert 600519 below 1500
/alert 600519 change_pct 5     # 涨幅超过5%
/alert 600519 change_pct -5    # 跌幅超过5%
/alert                         # 查看所有预警（含删除按钮）
```

**预警推送机制（防刷屏）：**

| 模式 | 说明 |
|------|------|
| 触发后暂停（默认开启） | 条件满足时推送一次，价格回归正常区间后才能再次触发 |
| 时间冷却（关闭时使用） | 每小时最多推送一次 |

- 触发推送卡片含「✅ 知道了」按钮，点击手动暂停（等价于已处理）
- 仅在 A 股交易时段运行（工作日 9:25–11:35 / 12:55–15:05），减少无效查询
- 可在 `/settings` → 设置卡片调整检查间隔（1–60 分钟，建议 ≥5 分钟防限流）
- 可在 `/settings` 切换「触发后暂停」开关

### 5.5 早报内容自定义

入口：主菜单 → 新建定制 → 📋 自定义早报

**腾讯财经（无次数限制）：**
- 🇨🇳 A股指数 — 上证/深证/创业板指数 + 涨跌幅
- 🌏 港股恒生 — 恒生指数 + 国企指数 + 涨跌幅
- 🇺🇸 美股三大 — 道琼斯/纳斯达克/标普500 + 涨跌幅

**Alpha Vantage（⚠️ 共25次/天，缓存1小时）：**
- 💵 汇率 `消耗4次` — USD/CNY · EUR/USD · USD/JPY 等4组
- 🛢️ 原油/黄金 `消耗3次` — WTI原油 · 布伦特原油 · 天然气
- 📰 美股新闻情绪 `消耗1次` — 自选股相关新闻情绪

点击模块按钮切换开/关，再点「💾 保存设置」生效。

### 5.6 推送时间修改

入口：主菜单 → 新建定制 → ⏰ 推送时间（或发送 `/settings`）

弹出设置卡片，支持：
- 修改早报/晚报推送时间（HH:MM 格式，留空不修改），点「保存」立即生效
- 修改价格预警检查间隔（1–60 分钟整数，建议 ≥5 分钟防限流）
- 切换「触发后暂停」开关（开启/关闭后立即生效）

### 5.7 美国宏观查询

入口：主菜单 → 🇺🇸 美国宏观（或发送 `/macro`）

- 查询 **CPI / 失业率 / 联邦基金利率 / 10年期国债收益率**
- 消耗 4 次 AV 配额，24小时缓存命中不重复消耗
- 由于 AV 限速，异步返回，先收到「查询中」提示，约15-50秒后推送结果

### 5.8 任务管理

```
/tasks          # 查看所有任务及状态（含开/关/删按钮）
/newtask        # 新建任务
/deltask 3      # 删除 #3 号任务
/pause 3        # 暂停/恢复 #3 号任务
```

**支持的任务类型：**

| 类型 | 说明 |
|------|------|
| `daily_report` | 每日收盘晚报（固定内容） |
| `index_report` | 每日指数早报（可选模块） |
| `price_alert` | 价格突破预警（实时） |

### 5.9 其他控制

```
/quiet              # 开启/关闭免打扰（全局静音）
/mute 600519 2h     # 屏蔽 600519 推送2小时
/restart            # 触发后台重启
```

---

## 6. 功能模块说明

### 6.1 bot/adapters/feishu_adapter.py — 飞书适配器

| 功能 | 说明 |
|------|------|
| 连接方式 | lark-oapi WebSocket 长连接，无需公网 IP |
| 卡片原地刷新 | `update_card(message_id, card)` 调用 `PATCH /im/v1/messages/{id}` |
| 消息发送 | `send_card()` 返回 `message_id`（用于后续 PATCH 刷新） |
| 回调解析 | 从 `ev.open_message_id` 提取来源消息 ID，存入 `msg.card_message_id` |

### 6.2 bot/handlers/commands.py — 指令处理器

- **文字指令路由**：解析 `/command` 并调用对应方法
- **按钮回调路由**：根据 `action` 字段分发处理（routing dict）
- **多步对话状态机**：`_pending_input` 记录等待输入状态

**主要回调 action：**

| action | 说明 |
|--------|------|
| `go_quote` | 提示输入代码查询 |
| `go_watchlist` | 显示自选列表 |
| `go_tasks` | 显示任务列表 |
| `go_newtask` | 新建定制卡片（价格预警/自定义早报/推送时间） |
| `go_settings` | 推送时间/预警设置卡片 |
| `go_macro` | 异步查询美国宏观指标 |
| `go_morning_modules` | 早报模块选择卡片 |
| `toggle_morning_module` | 切换模块开/关（原地刷新卡片） |
| `save_morning_modules` | 保存早报模块设置 |
| `save_push_times` | 保存推送时间/预警间隔（热更新调度器） |
| `toggle_alert_pause` | 切换「触发后暂停」开关 |
| `del_alert_select` | 展示删除预警选择列表 |
| `do_del_alert` | 删除指定预警 |
| `ack_alert` | 用户点击「知道了」，手动暂停预警直到恢复 |
| `toggle_task_btn` | 暂停/恢复任务（原地刷新） |
| `del_task_btn` | 删除任务（原地刷新） |

### 6.3 bot/scheduler.py — 任务调度引擎

基于 APScheduler BackgroundScheduler，时区 `Asia/Shanghai`。

**内置任务：**

| 任务 | 默认 cron | 说明 |
|------|----------|------|
| 晚报（全量） | `30 15 * * 1-5` | 固定推关注指数 + 自选收盘价，不调 AV |
| 早报（全量） | `0 9 * * 1-5` | 按用户 morning_modules 设置推送 |
| 价格预警检查 | `*/5 * * * *` | 每5分钟轮询（仅交易时段执行） |

**价格预警检查逻辑（`_check_single_alert`）：**
1. 非交易时段（工作日 9:25–11:35 / 12:55–15:05 以外）直接跳过全量检查
2. 读 `alerts` 表中 `enabled=1` 的预警逐条检查
3. 若 `alert_pause_until_normal=True`（默认）：
   - 已触发（`in_trigger=1`）：检查价格是否回归 → 回归则重置，否则跳过
   - 未触发：条件满足 → 推送卡片 + 标记 `in_trigger=1`
4. 若 `alert_pause_until_normal=False`：使用时间冷却（同小时内最多推一次）

**间隔热更新：** `update_alert_interval(minutes)` 直接修改 APScheduler job trigger，无需重启。

**用户个性化推送时间：**
- 设置后创建 `user_morning_{uid}` / `user_digest_{uid}` 专属 job
- 全局 job 自动跳过有专属 job 的用户，避免重复

### 6.4 bot/formatters/cards.py — 卡片模板

| 函数 | 说明 |
|------|------|
| `menu_card()` | 主菜单 |
| `quote_card(data)` | 单支行情 |
| `watchlist_card(items, quotes)` | 自选列表（含最高/最低价） |
| `daily_digest_card(...)` | 晚报卡片（不含 AV 数据） |
| `morning_modules_card(report_type, selected)` | 早报模块选择（分腾讯/AV 两组，含详细说明） |
| `newtask_type_card()` | 新建定制（价格预警/自定义早报/推送时间） |
| `settings_card(cfg_vals)` | 推送时间+预警间隔设置表单 + 触发后暂停切换按钮 |
| `del_alert_card(alerts)` | 删除预警选择列表 |
| `macro_query_card(data)` | 美国宏观指标结果卡片 |
| `tasks_card(tasks)` | 任务列表（含开/关/删按钮） |

### 6.5 data/sources/akshare_source.py — 行情数据源

主数据源为**腾讯财经 API**（`qt.gtimg.cn`），覆盖 A股/港股/指数；加密货币走 **Binance**；美股行情也走腾讯财经。

```python
auto_quote(symbol)      # 自动识别资产类型，返回行情字典
                        # 支持：A股6位数字 / 港股5位数字 / 美股1-5位英文 / BTC等 / SPX等指数
search_stock(keyword)   # 按名称搜索，返回 [{symbol, name}, ...]
                        # 方案A：东方财富搜索接口（5s超时）→ 支持A股+美股中文名
                        # 方案B：同花顺AKShare（5s超时，A股备用）
                        # 方案C：pytdx通达信TCP（需安装pytdx，A股）
                        # 注：全市场扫描（方案D）已禁用，避免2+分钟卡住
get_index_quotes()      # 批量获取主要指数行情
get_stock_announcements(symbol)  # 获取A股公告（AKShare，不稳定）
```

**`auto_quote` 返回的行情字典格式：**

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
    "asset_type": "a_stock",   # a_stock / hk_stock / us_stock / crypto / index
    "source": "腾讯财经",
    "timestamp": "15:02:33"
}
```

### 6.6 data/db.py — SQLite 数据层

```python
# 用户 & 设置
upsert_user(user_id, platform, username)
get_user_settings(user_id)         # 含 morning_modules / morning_time / digest_time
update_user_settings(user_id, settings)

# 自选
add_watchlist / remove_watchlist / get_watchlist

# 价格预警
add_alert / get_alerts / get_all_alerts / toggle_alert / delete_alert
set_alert_triggered(alert_id, user_id)   # 标记触发状态（含权限校验）
reset_alert_triggered(alert_id, user_id) # 重置为未触发（价格回归后自动调用）

# 定时任务
add_task / get_tasks / get_all_enabled_tasks
toggle_task / delete_task / update_task_last_run

# 推送去重
log_push / already_pushed(user_id, content_hash, within_hours)
```

---

## 7. 文件结构

```
.
├── bot/
│   ├── app.py
│   ├── adapters/
│   │   ├── base.py             # BaseAdapter / IncomingMessage / OutgoingCard / CardButton
│   │   ├── feishu_adapter.py   # 飞书 WebSocket 适配器 + PATCH 卡片刷新
│   │   └── telegram_adapter.py
│   ├── handlers/
│   │   └── commands.py
│   ├── scheduler.py
│   └── formatters/
│       └── cards.py
├── data/
│   ├── sources/
│   │   ├── akshare_source.py       # 腾讯财经/Binance 行情 + 东方财富名称搜索
│   │   └── alphavantage_source.py  # AV 数据（汇率/商品/宏观/新闻）
│   ├── db.py
│   └── secretary.db            # SQLite 数据库（自动生成）
├── config.py                   # 实际配置（不入 Git）
├── config.example.py
├── feishu_setup.py
├── restart.sh
├── stop.sh
├── Dockerfile
├── docker-compose.yml
├── docker-entrypoint.sh
├── price-monitor.service
├── requirements.txt
└── secretary.log               # 运行日志（自动生成）
```

---

## 8. 数据库结构

数据库文件：`data/secretary.db`（SQLite）

| 表名 | 用途 |
|------|------|
| `users` | 用户信息 + settings JSON（quiet_mode / morning_modules / morning_time / digest_time / alert_pause_until_normal 等） |
| `watchlist` | 自选标的列表 |
| `alerts` | 价格预警规则（含 `in_trigger` 触发状态字段） |
| `tasks` | 用户自定义定时任务 |
| `push_log` | 推送记录（用于时间冷却去重） |

**`users.settings` 关键字段：**

```json
{
  "quiet_mode": false,
  "morning_modules": ["a_stock", "us_stock", "fx"],
  "morning_time": "08:30",
  "digest_time": "16:00",
  "alert_pause_until_normal": true
}
```

**`alerts` 表关键字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `symbol` | TEXT | 股票代码（必须为代码，不能为中文名） |
| `condition` | TEXT | `above` / `below` / `change_pct` |
| `threshold` | REAL | 触发阈值（change_pct 为百分比，负数为跌幅） |
| `enabled` | INTEGER | 1=启用，0=暂停 |
| `in_trigger` | INTEGER | 1=当前已触发，等价格回归正常才重推；0=正常监控 |
| `triggered_count` | INTEGER | 累计触发次数 |

---

## 9. 常见问题

**Q: 点击按钮没反应？**  
A: Docker 部署用 `docker-compose logs -f bot | grep ERROR`，本地部署用 `tail -f secretary.log | grep ERROR`。常见原因：服务未运行、飞书 WebSocket 断连。Docker 可执行 `docker-compose restart`，本地可执行 `bash restart.sh`。

**Q: 按名称搜索股票，bot 没反应或返回"未找到"？**  
A: 名称搜索走东方财富接口，超时上限5秒。若网络波动导致超时，会提示"未找到，请改用代码查询"——此时直接输入代码（如 `NVDA`、`600519`）即可正常查询。名称搜索**不支持港股**，港股请直接输入代码（如 `00700`）。

**Q: 美国宏观按了没动静？**  
A: 正常现象——会先收到「🔄 正在查询...约15-50秒」的提示，结果异步返回。AV 限速 12秒/次，4个指标串行约需 48 秒（缓存命中则立即返回）。

**Q: 行情查询返回"查询失败"？**  
A: 腾讯财经 API 偶有限速，稍后重试。加密货币走 Binance API，需要网络能访问 `api.binance.com`。

**Q: 修改了推送时间，什么时候生效？**  
A: 通过卡片表单修改的推送时间**立即生效**（热更新，无需重启），并持久化到数据库。`config.py` 中的时间为全局默认值，用户个性化设置优先级更高。

**Q: AV 配额用完了怎么办？**  
A: 配额耗尽后，早报卡片 footer 会显示警告，AV 模块自动跳过（不影响腾讯财经数据）。24小时后自动恢复。

**Q: Docker 里提示 `ALPHA_VANTAGE_API_KEY` 未配置，应该改哪里？**  
A: 不用进容器改。请编辑**宿主机项目目录**下的 `.env`（例如 `cd /root/Desktop/priceMonitor && vi .env`），填写 `ALPHA_VANTAGE_API_KEY=你的key`，然后执行 `docker-compose restart`。容器里的 `/app/.env` 是宿主机 `.env` 的映射文件。

**Q: 价格预警已设置但没收到推送？**  
A: 检查：① 是否在 A 股交易时段（工作日 9:30–11:30 / 13:00–15:00）；② 条件是否满足；③ 该预警是否处于 `in_trigger=1` 状态（触发后暂停）；④ 免打扰模式是否开启（发 `/quiet` 查看）。

**Q: 设置了预警但每5分钟一直提醒？**  
A: 「触发后暂停」默认开启，触发一次后等价格回归正常才重推。可通过 `/settings` 切换该开关。

**Q: 想停止某只股票的预警推送？**  
A: 方案一：点击推送卡片的「✅ 知道了」手动暂停（等价格恢复后自动重启）。  
方案二：`/tasks` → 任务卡片 → 「➖ 删除预警」→ 选择对应预警删除。

**Q: Docker 构建很慢，或 `docker-compose build` 拉镜像超时？**  
A: 常见于服务器访问 Docker Hub 网络不稳定，报错通常类似 `Client.Timeout exceeded while awaiting headers`。优先配置 Docker 镜像加速器后重试；如果机器网络较差，可在本地先构建镜像，再用 `docker save | scp | docker load` 传到服务器。

**Q: 服务器/NAS 定时关机重启后，早报/日报没有推送？**  
A: 这是 Docker 重启策略配置问题。检查 `docker-compose.yml` 中是否设置了 `restart: always`：  
```yaml
services:
  bot:
    restart: always   # ← 必须是 always，不能是 unless-stopped
```  
`unless-stopped` 在 OS 关机时会把容器标记为"主动停止"，重启后不会自动拉起。`always` 则保证 Docker daemon 启动后无论任何原因停机都自动重启容器。  
修改后执行 `docker-compose up -d --force-recreate` 应用新策略，下次重启即生效。

---

*综合秘书机器人 v2.2 — 本文档随代码同步维护*
