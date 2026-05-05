# 综合秘书机器人 操作手册 & 技术文档

**版本**: v2.1  
**更新日期**: 2026-05-05

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

本系统是一个以**飞书**为主平台的个人综合秘书机器人（v2.1），单用户设计，核心特点：

- **双向对话**：不只是推送，还能主动查询
- **卡片交互**：按钮引导操作，无需记忆指令
- **卡片原地刷新**：模块 toggle 等操作直接更新原卡片，不刷屏
- **早晚报分离**：早报可选模块（腾讯组 + AV组），晚报固定内容不耗 AV 配额
- **美国宏观按需查询**：手动触发，异步返回

### 支持的资产类型

| 类型 | 示例 | 数据源 |
|------|------|--------|
| A股 | `600519`（贵州茅台）、`000858` | 腾讯财经 |
| 港股 | `00700`（腾讯控股）、`09988` | 腾讯财经 |
| 全球指数 | `SPX`（标普）、`NDX`（纳指）、`DJI`（道指）、`HSI`（恒生） | 腾讯财经 |

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

### 3.1 飞书应用（必填）

```bash
# .env 格式
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxx
FEISHU_OPEN_ID=ou_xxxxxxxxxxxxxxxx
```

> 通过 `feishu_setup.py` 扫码后自动填写，无需手动获取。

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
/quote SPX           # 全球指数别名
/quote 贵州茅台      # 按名称搜索（模糊匹配）
```

行情卡片底部快捷按钮：**加入自选 ⭐** / **设置预警 🔔**

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
/alert                         # 查看所有预警
```

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

弹出卡片，填写 HH:MM 格式，留空不修改，点「保存」立即生效（热更新无需重启）。

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
| `go_settings` | 推送时间设置卡片 |
| `go_macro` | 异步查询美国宏观指标 |
| `go_morning_modules` | 早报模块选择卡片 |
| `toggle_morning_module` | 切换模块开/关（原地刷新卡片） |
| `save_morning_modules` | 保存早报模块设置 |
| `save_push_times` | 保存推送时间（热更新调度器） |
| `toggle_task_btn` | 暂停/恢复任务（原地刷新） |
| `del_task_btn` | 删除任务（原地刷新） |

### 6.3 bot/scheduler.py — 任务调度引擎

基于 APScheduler BackgroundScheduler，时区 `Asia/Shanghai`。

**内置任务：**

| 任务 | 默认 cron | 说明 |
|------|----------|------|
| 晚报（全量） | `30 15 * * 1-5` | 固定推关注指数 + 自选收盘价，不调 AV |
| 早报（全量） | `0 9 * * 1-5` | 按用户 morning_modules 设置推送 |
| 价格预警检查 | `*/5 * * * *` | 每5分钟轮询 |

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
| `settings_card(cfg_vals)` | 推送时间设置表单 |
| `macro_query_card(data)` | 美国宏观指标结果卡片 |
| `tasks_card(tasks)` | 任务列表（含开/关/删按钮） |

### 6.5 data/sources/alphavantage_source.py — AV 数据源

```python
get_fx_rates()               # 汇率（消耗4次）
get_commodity_prices()       # 大宗商品（消耗3次）
get_news_sentiment(tickers)  # 新闻情绪（消耗1次）
get_macro_summary()          # 宏观指标摘要（消耗4次，串行，约46秒）
is_configured()              # 检查 API Key
is_quota_exhausted()         # 配额耗尽检测（24小时自动重置）
```

> ⚠️ `get_macro_summary()` 串行调4个接口，AV 限速12秒/次，最长约46秒。务必在异步线程中调用。

### 6.6 data/db.py — SQLite 数据层

```python
# 用户 & 设置
upsert_user(user_id, platform, username)
get_user_settings(user_id)         # 含 morning_modules / morning_time / digest_time
update_user_settings(user_id, settings)

# 自选
add_watchlist / remove_watchlist / get_watchlist

# 价格预警
add_alert / get_alerts / toggle_alert / delete_alert

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
│   │   ├── akshare_source.py       # 腾讯财经行情
│   │   └── alphavantage_source.py  # AV 数据（汇率/商品/宏观/新闻）
│   ├── db.py
│   └── secretary.db            # SQLite 数据库（自动生成）
├── config.py                   # 实际配置（不入 Git）
├── config.example.py
├── feishu_setup.py
├── restart.sh
├── stop.sh
├── price-monitor.service
├── requirements.txt
└── price_monitor.log
```

---

## 8. 数据库结构

数据库文件：`data/secretary.db`（SQLite）

| 表名 | 用途 |
|------|------|
| `users` | 用户信息 + settings JSON（quiet_mode / morning_modules / morning_time / digest_time 等） |
| `watchlist` | 自选标的列表 |
| `price_alerts` | 价格预警规则 |
| `scheduled_tasks` | 用户自定义定时任务 |
| `push_log` | 推送记录（用于2小时去重冷却） |

**`users.settings` 关键字段：**

```json
{
  "quiet_mode": false,
  "morning_modules": ["a_stock", "us_stock", "fx"],
  "morning_time": "08:30",
  "digest_time": "16:00"
}
```

---

## 9. 常见问题

**Q: 点击按钮没反应？**  
A: 查看日志 `tail -f price_monitor.log | grep ERROR`。v2.1 已修复按钮回调时 `msg.text=None` 导致崩溃的 bug，确保运行最新版本。

**Q: 美国宏观按了没动静？**  
A: 正常现象——会先收到「🔄 正在查询...约15-50秒」的提示，结果异步返回。AV 限速 12秒/次，4个指标串行约需 48 秒（缓存命中则立即返回）。

**Q: 行情查询返回"查询失败"？**  
A: 腾讯财经 API 偶有限速，稍后重试。

**Q: 修改了推送时间，什么时候生效？**  
A: 通过卡片表单修改的推送时间**立即生效**（热更新，无需重启），并持久化到数据库。`config.py` 中的时间为全局默认值，用户个性化设置优先级更高。

**Q: AV 配额用完了怎么办？**  
A: 配额耗尽后，早报卡片 footer 会显示警告，AV 模块自动跳过（不影响腾讯财经数据）。24小时后自动恢复。

**Q: 价格预警已设置但没收到推送？**  
A: 检查：① 条件是否满足；② 2小时冷却期内是否已推送；③ 免打扰模式是否开启（发 `/quiet` 查看）。

**Q: 想停止某只股票的预警推送？**  
A: `/mute 600519 Xh` 临时屏蔽，或通过 `/alert` 卡片删除对应规则。

---

*综合秘书机器人 v2.1 — 2026-05-04*


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

