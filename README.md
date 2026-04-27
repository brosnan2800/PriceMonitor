# USD/CNH 和 布伦特原油价格监控系统

一个 Python 脚本系统，用于监控 USD/CNH 汇率和布伦特原油价格，并通过 **飞书** 或 **Telegram** 推送通知。

## ✨ 功能特点

- **价格监控**: 定时获取 USD/CNH 汇率和布伦特原油（日线）价格
- **智能提醒**: 价格超过阈值时自动推送警报
- **多推送平台**: 同时支持飞书（国内推荐）和 Telegram
- **飞书扫码部署**: 运行 `feishu_setup.py` 扫码自动完成飞书配置
- **可配置间隔**: API 请求间隔、监控频率均可在配置文件中调整
- **多平台运行**: 支持 Windows / Linux / Mac

## 📋 系统要求

- Python 3.8+
- Alpha Vantage API 密钥（免费注册，25次/天）
- 推送平台二选一或均配置：
  - 飞书开放平台应用（国内网络，推荐）
  - Telegram Bot Token（需翻墙）

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

### 3. 获取 API 密钥
- **Alpha Vantage**（必需）: https://www.alphavantage.co/support/#api-key
- **飞书**（推荐，国内可用）: 在飞书开放平台创建应用，获取 App ID 和 App Secret
- **Telegram**（可选，需翻墙）: 通过 @BotFather 创建 Bot

### 4. 配置系统
```bash
# 复制配置文件模板
cp config.example.py config.py

# 编辑配置文件，填入你的密钥
nano config.py
```

**飞书用户推荐使用扫码方式自动完成配置：**
```bash
python3 feishu_setup.py
```

### 5. 测试运行
```bash
# 单次运行，验证配置是否正确
python3 price_monitor.py --once

# 启动持续监控
python3 price_monitor.py
```

## 📁 项目结构

```
.
├── price_monitor.py          # 主监控程序
├── data_collector.py         # 数据收集模块（Alpha Vantage）
├── feishu_bot.py             # 飞书推送模块
├── feishu_setup.py           # 飞书扫码配置工具
├── telegram_bot.py           # Telegram 推送模块
├── config.example.py         # 配置文件模板（复制为 config.py 后填写密钥）
├── requirements.txt          # Python 依赖列表
├── setup_guide.md            # 详细部署指南
├── price-monitor.service     # systemd 服务文件（Linux 部署用）
└── README.md                 # 本文档
```

## ⚙️ 配置说明

```python
# config.py

# Alpha Vantage API 密钥（必需）
ALPHA_VANTAGE_API_KEY = "your_api_key"

# 监控间隔（分钟）
MONITOR_INTERVAL_MINUTES = 5

# API 请求间隔（秒）—— 免费版建议 >= 2，避免触发频率限制
API_REQUEST_INTERVAL_SECONDS = 2

# 价格提醒阈值
USD_CNH_UPPER_THRESHOLD = 7.15       # USD/CNH 上涨提醒阈值
USD_CNH_LOWER_THRESHOLD = 7.10       # USD/CNH 下跌提醒阈值
BRENT_OIL_CHANGE_THRESHOLD_PERCENT = 1.0  # 原油波动提醒阈值（%）

# 启用的推送平台（可单独启用一个或两个都启用）
ENABLED_PLATFORMS = ["feishu"]       # 可选: "telegram", "feishu"

# 飞书配置
FEISHU_APP_ID = "your_feishu_app_id"
FEISHU_APP_SECRET = "your_feishu_app_secret"
FEISHU_OPEN_ID = ""                  # 由 feishu_setup.py 自动获取

# Telegram 配置（国内需翻墙）
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"
```

## 🚀 运行方式

```bash
# 单次运行（测试用）
python3 price_monitor.py --once

# 持续监控（前台）
python3 price_monitor.py

# 后台运行（Linux/Mac）
nohup python3 price_monitor.py > monitor.log 2>&1 &
```

### Linux 系统服务
```bash
sudo cp price-monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable price-monitor
sudo systemctl start price-monitor
```

## 🔔 推送消息示例

```
📈 价格监控报告 📈

💰 USD/CNH
    └─ 价格: 7.1234
    └─ 涨跌: 📈 +0.15% (+0.0111)
    └─ 时间: 2024-01-01 14:30:05

🛢️ 布伦特原油
    └─ 价格: 85.67美元/桶
    └─ 涨跌: 📉 -0.42% (-0.36)
    └─ 时间: 2024-01-01 14:30:05

🔧 系统信息
• 本次检查: 2024-01-01 14:30:05
• 下次检查: 14:35:05
```

## 📊 数据记录

系统自动记录：
- `price_history.json` - 历史价格数据
- `price_monitor.log` - 系统运行日志
- `price_monitor.db` - 数据库备份（如果启用）

## 🔧 故障排除

1. **`python: command not found`** → macOS/Linux 请用 `python3`
2. **原油价格是几天前的** → Alpha Vantage 免费版 BRENT 接口只提供每日收盘价，属正常现象
3. **API 返回 rate limit 错误** → 增大 `API_REQUEST_INTERVAL_SECONDS`，或等明天（25次/天限制）
4. **飞书收不到消息** → 运行 `python3 feishu_setup.py` 重新获取 open_id
5. **Telegram 连接失败** → 国内网络需要翻墙才能访问 Telegram API

## 🚢 部署选项

### 本地电脑
- 24小时开机的电脑
- 使用任务计划程序(cron/Windows任务计划)

### 云服务器
- 阿里云/腾讯云轻量服务器（月费5-15元）
- 配置systemd服务自动运行

### 免费云函数
- Cloudflare Workers（有速率限制）
- Railway/Heroku免费额度

### Docker容器
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "price_monitor.py"]
```

## 📊 API 说明

### Alpha Vantage（免费版）
- 限制：**25次/天，5次/分钟**
- USD/CNH 汇率：接近实时
- 布伦特原油：**每日收盘价**（非实时，数据为上一交易日）
- 免费注册：https://www.alphavantage.co/support/#api-key

### 飞书推送
- 完全免费，国内网络直连
- 支持私聊和群聊
- 通过 `feishu_setup.py` 扫码自动配置

### Telegram 推送
- 完全免费，无消息数量限制
- **国内网络需要翻墙**

## 🛡️ 安全建议

1. **保护API密钥**: 不要公开`config.py`或`.env`文件
2. **使用环境变量**: 生产环境建议使用环境变量
3. **定期更新**: 保持依赖包最新版本
4. **访问限制**: 服务器部署时配置防火墙

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

1. Fork项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启Pull Request

## 📄 许可证

本项目基于MIT许可证开源。

## 📞 支持

- 查看详细文档: [setup_guide.md](setup_guide.md)
- 报告问题: GitHub Issues
- 邮件支持: 请联系项目维护者

---

**开始监控你的资产价格吧！** 🚀