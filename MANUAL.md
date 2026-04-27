# 价格监控系统 操作手册 & 技术文档

**版本**: v0.1  
**更新日期**: 2026-04-25

---

## 目录

1. [系统概述](#1-系统概述)
2. [快速开始](#2-快速开始)
3. [配置说明](#3-配置说明)
4. [运行方式](#4-运行方式)
5. [功能模块说明](#5-功能模块说明)
6. [文件结构](#6-文件结构)
7. [常见问题](#7-常见问题)

---

## 1. 系统概述

本系统用于实时监控以下金融资产，并通过飞书/Telegram 推送价格报告和预警通知：

| 资产 | 数据源 | 说明 |
|------|--------|------|
| USD/CNH 汇率 | Alpha Vantage | 美元/离岸人民币实时汇率 |
| 布伦特原油 | Alpha Vantage | 国际原油价格（每日数据） |

**推送平台**：飞书（私聊推送）、Telegram（可选）

---

## 2. 快速开始

### 2.1 安装依赖

```bash
pip install -r requirements.txt
```

### 2.2 配置飞书机器人（首次使用）

```bash
python feishu_setup.py
```

- 程序会在终端打印二维码
- 用**飞书 App** 扫码，按提示授权
- 扫码成功后自动将 `FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_OPEN_ID` 写入 `config.py`

> ⚠️ 必须在系统终端（VS Code Terminal 等）中运行，不是在聊天窗口里。

### 2.3 填写 Alpha Vantage API Key

编辑 `config.py`，填写：

```python
ALPHA_VANTAGE_API_KEY = "你的KEY"
```

API Key 免费申请地址：https://www.alphavantage.co/support/#api-key

### 2.4 运行测试

```bash
python price_monitor.py --once
```

收到飞书消息即表示配置成功。

### 2.5 启动持续监控

```bash
python price_monitor.py
```

默认每 5 分钟检查一次，触发阈值时发送预警。

---

## 3. 配置说明

所有配置在项目根目录的 `config.py` 文件中。

### 3.1 Alpha Vantage（行情数据）

```python
ALPHA_VANTAGE_API_KEY = "你的API Key"
```

- 免费版限制：**25次/天**，每秒 1 次
- 申请地址：https://www.alphavantage.co/support/#api-key
- 付费版可提升至 75~1200 次/分钟

### 3.2 飞书机器人

```python
FEISHU_APP_ID     = "cli_xxxxxxxxxxxxxxxx"   # 运行 feishu_setup.py 自动填写
FEISHU_APP_SECRET = "xxxxxxxxxxxxxxxxxxxxxxx"  # 运行 feishu_setup.py 自动填写
FEISHU_OPEN_ID    = "ou_xxxxxxxxxxxxxxxx"     # 你的飞书用户ID，扫码后自动获取
FEISHU_CHAT_ID    = ""                         # 群聊推送时填写，私聊留空即可
```

> 不要手动修改这几项，通过 `feishu_setup.py` 扫码自动配置最稳。

### 3.3 Telegram 机器人（可选）

```python
TELEGRAM_BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
TELEGRAM_CHAT_ID   = "你的Chat ID"
```

- Token 通过 [@BotFather](https://t.me/BotFather) 创建机器人获取
- Chat ID 向机器人发一条消息后，访问 `https://api.telegram.org/bot<TOKEN>/getUpdates` 获取

### 3.4 监控间隔

```python
MONITOR_INTERVAL_MINUTES = 5   # 检查价格的频率，单位：分钟
```

> 注意：Alpha Vantage 免费版每天只有 25 次请求，监控间隔不建议低于 60 分钟，否则当天配额会快速耗尽。

### 3.5 预警阈值

```python
# USD/CNH 汇率预警
USD_CNH_UPPER_THRESHOLD = 7.15   # 高于此值触发上涨预警
USD_CNH_LOWER_THRESHOLD = 7.10   # 低于此值触发下跌预警

# 布伦特原油波动预警
BRENT_OIL_CHANGE_THRESHOLD_PERCENT = 1.0   # 相对上次价格波动超过 1% 触发预警
```

### 3.6 推送平台选择

```python
ENABLED_PLATFORMS    = ["telegram", "feishu"]  # 启用的平台
NOTIFICATION_PLATFORM = "all"                   # 可选：telegram / feishu / all
```

### 3.7 日志配置

```python
LOG_LEVEL = "INFO"              # 日志级别：DEBUG / INFO / WARNING / ERROR
LOG_FILE  = "price_monitor.log" # 日志文件名，留空则只输出到终端
```

---

## 4. 运行方式

### 4.1 命令行参数

```bash
# 单次执行（拉取一次价格并推送，然后退出）
python price_monitor.py --once

# 持续监控（按 MONITOR_INTERVAL_MINUTES 循环运行）
python price_monitor.py

# 飞书机器人扫码配置
python feishu_setup.py

# 单独测试飞书推送
python feishu_bot.py

# 单独测试数据采集
python data_collector.py
```

### 4.2 后台运行（Linux/macOS）

```bash
# 使用 nohup 后台运行，日志写入 price_monitor.log
nohup python price_monitor.py > price_monitor.log 2>&1 &

# 查看进程
ps aux | grep price_monitor

# 停止
kill <PID>
```

### 4.3 systemd 服务（Linux）

项目内附带 `price-monitor.service` 配置文件：

```bash
sudo cp price-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable price-monitor
sudo systemctl start price-monitor
sudo systemctl status price-monitor
```

---

## 5. 功能模块说明

### 5.1 price_monitor.py — 主程序

- 初始化并协调所有模块
- 按配置间隔定时触发价格检查
- 对比阈值，决定是否发送预警
- 处理 SIGINT/SIGTERM 信号优雅退出

### 5.2 data_collector.py — 数据采集

| 方法 | 说明 |
|------|------|
| `get_usd_cnh_rate()` | 调用 Alpha Vantage CURRENCY_EXCHANGE_RATE 接口获取 USD/CNH |
| `get_brent_oil_price()` | 调用 Alpha Vantage BRENT 接口获取布伦特原油日线价格 |
| `collect_all_prices()` | 同时获取以上两项，返回汇总字典 |

### 5.3 feishu_bot.py — 飞书推送

| 方法 | 说明 |
|------|------|
| `test_connection()` | 获取 tenant_access_token，验证凭证有效性 |
| `send_message(text)` | 发送纯文本消息（支持私聊 open_id 或群聊 chat_id） |
| `send_price_report(data)` | 格式化发送价格报告（含涨跌箭头） |
| `send_alert(asset, msg)` | 发送 🚨 价格预警消息 |
| `get_chat_list()` | 获取机器人所在的群聊列表 |

**消息接收方优先级**：`open_id`（私聊）> `chat_id`（群聊）

### 5.4 feishu_setup.py — 飞书扫码配置

实现飞书官方 Device Code Flow（设备码流程）：

```
1. POST accounts.feishu.cn/oauth/v1/app/registration  action=init
2. POST ...  action=begin  →  获取 device_code + qr_url
3. 终端渲染 QR 码（ASCII 字符画）
4. 轮询 action=poll，直到用户扫码确认
5. 返回 client_id（app_id）+ client_secret（app_secret）+ open_id
6. 自动写入 config.py
```

> 这是飞书官方提供的标准接口，不依赖任何第三方服务。

### 5.5 telegram_bot.py — Telegram 推送

- 使用 python-telegram-bot 库
- 支持发送价格报告和预警
- 需要配置 BOT_TOKEN 和 CHAT_ID

---

## 6. 文件结构

```
.
├── config.py              # 主配置文件（含所有 API Key 和阈值）
├── config.example.py      # 配置模板，不含敏感信息
├── price_monitor.py       # 主程序入口
├── data_collector.py      # 行情数据采集
├── feishu_bot.py          # 飞书推送模块
├── feishu_setup.py        # 飞书扫码一键配置工具
├── telegram_bot.py        # Telegram 推送模块
├── requirements.txt       # Python 依赖列表
├── price-monitor.service  # systemd 服务配置（Linux）
├── price_monitor.log      # 运行日志（自动生成）
├── price_history.json     # 历史价格记录（自动生成）
└── MANUAL.md              # 本文档
```

---

## 7. 常见问题

**Q: 飞书扫码后提示"连接失败"？**  
A: 确保在系统终端（不是聊天窗口）运行 `python feishu_setup.py`，需要访问 `accounts.feishu.cn`，检查网络是否正常。

**Q: 布伦特原油数据获取失败？**  
A: Alpha Vantage 免费版每天限 25 次请求。当天测试次数过多会触发限速，次日自动恢复。如需高频监控，建议升级付费套餐或调大 `MONITOR_INTERVAL_MINUTES`。

**Q: 修改了阈值，没有收到预警？**  
A: 修改 `config.py` 后需要重启程序才能生效。另外预警只在价格**穿越**阈值时触发，不会重复发送。

**Q: 想只用飞书，不用 Telegram？**  
A: 修改 `config.py`：
```python
NOTIFICATION_PLATFORM = "feishu"
```

**Q: 如何查看历史价格？**  
A: 运行日志保存在 `price_monitor.log`，历史价格数据保存在 `price_history.json`。

---

*价格监控系统 v0.1 — 本文档随代码同步维护*
