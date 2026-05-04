# 综合秘书机器人 · Secretary Bot

一个基于**飞书**的个人综合秘书机器人，支持金融行情查询、自选监控、价格预警、定时早晚报推送等功能。采用 **卡片交互为主、/命令为辅** 的双向对话设计，告别纯推送模式。

## ✨ 功能概览

### 📈 金融查询（即时）
- **实时行情**：A股、港股、全球主要指数（标普、纳斯达克、道琼斯等）
- **名称搜索**：支持股票名称查询，如 `/quote 贵州茅台`
- **自选列表**：增删自选标的，批量查询行情，显示最高/最低价，卡片内一键删除

### 🔔 价格预警（引导式设置）
- 在行情卡片点击「设置预警」→ 弹出独立预警卡片
- 支持四种条件：**涨幅预警 / 跌幅预警 / 价格上限 / 价格下限**
- 对话引导输入数值，无需记忆指令格式
- 2小时冷却防重复推送

### ⏰ 早报 & 晚报（定时推送）

| 报告 | 默认时间 | 内容 |
|------|---------|------|
| 🌅 指数早报 | 09:00 | 可选模块：腾讯组（A股/港股/美股）+ AV 组（汇率/原油/新闻情绪） |
| 🌙 每日晚报 | 15:30 | 固定内容：主要指数收盘 + 自选股收盘价 |

早报内容可自定义（主菜单 → 新建定制 → 自定义早报），晚报不调 AV，省配额给早报。

### 🇺🇸 美国宏观指标（按需查询）
- 点击主菜单「美国宏观」或发送 `/macro`
- 推送 CPI / 失业率 / 联邦基金利率 / 10年期国债收益率
- 消耗 4 次 AV 配额，当日缓存，异步返回（约 15-50 秒）

---

## 🚀 快速开始

### 1. 克隆项目
```bash
git clone https://github.com/brosnan2800/PriceMonitor.git
cd PriceMonitor
```

### 2. 安装依赖
```bash
pip3 install -r requirements.txt
```

### 3. 配置
```bash
cp config.example.py config.py
# 编辑 config.py，填入飞书 App ID、App Secret
```

### 4. 启动 / 停止
```bash
# 后台启动
bash restart.sh

# 停止所有服务
bash stop.sh

# 查看日志
tail -f price_monitor.log
```

---

## 💬 使用方式

### 主入口：`/menu`

发送 `/menu` 或 `菜单` 调出全功能按钮面板：

```
[查行情 🔍]      [我的自选 ⭐]
[定制任务 ⏰]    [新建定制 ➕]
[🇺🇸 美国宏观]  [免打扰 🔕]  [重启服务 🔄]
```

**新建定制** 卡片（入口：主菜单 → 新建定制）：
```
[🔔 价格预警]  [📋 自定义早报]  [⏰ 推送时间]
```

### 文字指令：`/help`

发送 `/help` 查看所有可用的 `/命令` 说明。

---

## 📋 完整指令列表

### 金融模块
| 指令 | 说明 |
|------|------|
| `/quote 600519` | 查询 A股实时行情 |
| `/quote 00700` | 查询港股行情 |
| `/quote SPX` | 查询标普500指数 |
| `/quote 贵州茅台` | 按名称搜索股票 |
| `/watchlist` | 查看我的自选列表（含删除按钮） |
| `/add 600519` | 添加自选 |
| `/remove 600519` | 移除自选 |
| `/macro` | 查询美国宏观指标（需 AV Key） |

### 价格预警
| 指令 | 说明 |
|------|------|
| `/alert` | 查看当前所有预警 |
| `/alert 600519 above 2000` | 价格超过2000时提醒 |
| `/alert 600519 below 1500` | 价格低于1500时提醒 |
| `/alert 600519 change_pct 5` | 涨幅超过5%时提醒 |
| `/alert 600519 change_pct -5` | 跌幅超过5%时提醒 |

> 推荐通过行情卡片的「设置预警 🔔」按钮引导式创建，更方便。

### 任务管理
| 指令 | 说明 |
|------|------|
| `/tasks` | 查看所有定时任务 |
| `/newtask` | 新建定时任务（卡片引导） |
| `/deltask 3` | 删除任务 #3 |
| `/pause 3` | 暂停/恢复任务 #3 |

### 推送控制
| 指令 | 说明 |
|------|------|
| `/quiet` | 开启/关闭免打扰模式 |
| `/mute 600519 2h` | 屏蔽某标的推送 2 小时 |
| `/settings` | 查看 & 修改推送时间（弹卡片） |

---

## ⚙️ 配置说明

关键配置项（`config.py`）：

```python
# 飞书应用（必填）
FEISHU_APP_ID = "cli_xxxx"
FEISHU_APP_SECRET = "xxxx"
FEISHU_OPEN_ID = "ou_xxxx"   # 由 feishu_setup.py 自动获取

# 可选：Alpha Vantage（汇率/原油/宏观，免费版 25次/天）
ALPHA_VANTAGE_API_KEY = "your_key"

# 价格预警检查频率（分钟，默认5分钟）
PRICE_ALERT_INTERVAL_MINUTES = 5

# 晚报推送时间（默认15:30）
DAILY_DIGEST_HOUR = 15
DAILY_DIGEST_MINUTE = 30

# 早报推送时间（默认09:00）
MORNING_REPORT_HOUR = 9
MORNING_REPORT_MINUTE = 0
```

---

## 📁 项目结构

```
├── bot/
│   ├── app.py                  # 主入口（双向对话 + 调度引擎）
│   ├── adapters/
│   │   ├── base.py             # 适配器基类（BaseAdapter / IncomingMessage / OutgoingCard）
│   │   ├── feishu_adapter.py   # 飞书 WebSocket 长连接（主平台）+ 卡片原地刷新 PATCH API
│   │   └── telegram_adapter.py # Telegram（次平台，可选）
│   ├── handlers/
│   │   └── commands.py         # 指令路由 + 按钮回调 + 多步对话状态机
│   ├── scheduler.py            # APScheduler 任务调度引擎
│   └── formatters/
│       └── cards.py            # 飞书卡片消息模板
├── data/
│   ├── sources/
│   │   ├── akshare_source.py   # 行情数据（腾讯财经）
│   │   └── alphavantage_source.py  # AV 数据（汇率/大宗商品/宏观/新闻情绪）
│   └── db.py                   # SQLite 数据层
├── config.example.py           # 配置模板
├── config.py                   # 实际配置（不入 Git）
├── restart.sh                  # 后台重启脚本
├── stop.sh                     # 停止所有服务
├── requirements.txt
└── MANUAL.md                   # 详细技术文档
```

---

## 📊 数据源

| 数据源 | 用途 | 费用 |
|--------|------|------|
| 腾讯财经 API | A股/港股/全球指数实时行情 | 免费，无限制 |
| Alpha Vantage | 汇率/大宗商品/宏观指标/新闻情绪 | 免费 25次/天 |

> AKShare 因网络环境问题暂时停用，后续视情况恢复。

---

## 🛡️ 安全提醒

- 不要将 `config.py` 提交到 Git（已加入 `.gitignore`）
- 飞书 App Secret 请妥善保管

## 📄 许可证

MIT License
