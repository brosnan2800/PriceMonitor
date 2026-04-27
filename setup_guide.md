# USD/CNH 和 布伦特原油价格监控系统 - 设置指南

## 快速开始

### 步骤 1: 获取API密钥

#### 1.1 Alpha Vantage API (金融数据)
1. 访问: https://www.alphavantage.co/support/#api-key
2. 填写邮箱和密码注册
3. 登录后生成API密钥
4. 免费限制: 5次/分钟, 500次/天

#### 1.2 Telegram机器人 (消息推送)

**创建机器人**:
1. 在Telegram中搜索 `@BotFather`
2. 发送 `/start` 开始
3. 发送 `/newbot` 创建新机器人
4. 按提示设置:
   - 机器人名称: `Price Monitor Bot`
   - 用户名: `your_price_monitor_bot` (必须以bot结尾)
5. 保存API Token，格式类似: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`

**获取Chat ID**:
1. 在Telegram中搜索你的机器人用户名 (@your_price_monitor_bot)
2. 发送 `/start` 或任意消息
3. 打开浏览器访问(替换YOUR_TOKEN):
   ```
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
   ```
4. 在JSON响应中找到 `"chat":{"id":12345678}` 中的数字

### 步骤 2: 设置配置文件

1. 复制配置文件模板:
   ```bash
   cp config.example.py config.py
   ```

2. 编辑 `config.py`:
   ```python
   # Alpha Vantage API 配置
   ALPHA_VANTAGE_API_KEY = "你的AlphaVantage密钥"

   # Telegram 机器人配置
   TELEGRAM_BOT_TOKEN = "你的Telegram机器人Token"
   TELEGRAM_CHAT_ID = "你的Chat ID"

   # 监控配置 (可根据需要调整)
   MONITOR_INTERVAL_MINUTES = 5  # 检查间隔，建议5-15分钟

   # 价格阈值提醒设置
   USD_CNH_UPPER_THRESHOLD = 7.15  # USD/CNH超过此值提醒
   USD_CNH_LOWER_THRESHOLD = 7.10  # USD/CNH低于此值提醒
   BRENT_OIL_CHANGE_THRESHOLD_PERCENT = 1.0  # 原油价格波动超过此百分比提醒
   ```

### 步骤 3: 安装依赖

```bash
# 创建虚拟环境 (推荐)
python3 -m venv venv

# 激活虚拟环境
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 步骤 4: 测试系统

```bash
# 测试所有服务
python price_monitor.py --test

# 单次运行测试
python price_monitor.py --once

# 测试Telegram单独
python telegram_bot.py

# 测试数据收集单独
python data_collector.py
```

### 步骤 5: 运行系统

#### 方式 A: 交互式运行 (推荐初学者)
```bash
python price_monitor.py --interactive
```

#### 方式 B: 定时监控 (后台运行)
```bash
python price_monitor.py
# 按 Ctrl+C 停止
```

#### 方式 C: Windows系统启动脚本
创建 `start_monitor.bat`:
```batch
@echo off
cd /d "%~dp0"
python price_monitor.py
pause
```

#### 方式 D: Linux/Mac后台运行
```bash
# 使用nohup在后台运行
nohup python price_monitor.py > monitor.log 2>&1 &

# 查看日志
tail -f monitor.log

# 停止进程
pkill -f "python price_monitor.py"
```

#### 方式 E: 使用systemd服务 (Linux)
创建 `/etc/systemd/system/price-monitor.service`:
```ini
[Unit]
Description=Price Monitor Service
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/price_monitor
ExecStart=/path/to/venv/bin/python /path/to/price_monitor.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用并启动:
```bash
sudo systemctl daemon-reload
sudo systemctl enable price-monitor
sudo systemctl start price-monitor
sudo systemctl status price-monitor
```

## 配置选项详解

### 监控频率设置
| 选项 | 推荐值 | 说明 |
|------|--------|------|
| MONITOR_INTERVAL_MINUTES | 5-15 | 检查间隔。越小数据越实时，但API调用次数越多 |

### 价格阈值设置
| 选项 | 示例值 | 说明 |
|------|--------|------|
| USD_CNH_UPPER_THRESHOLD | 7.15 | USD/CNH汇率超过此值触发提醒 |
| USD_CNH_LOWER_THRESHOLD | 7.10 | USD/CNH汇率低于此值触发提醒 |
| BRENT_OIL_CHANGE_THRESHOLD_PERCENT | 1.0 | 原油价格波动超过1%提醒 |

### 环境变量配置
不想使用config.py可以使用环境变量:
```bash
# Linux/Mac
export ALPHA_VANTAGE_API_KEY="你的密钥"
export TELEGRAM_BOT_TOKEN="你的Token"
export TELEGRAM_CHAT_ID="你的ChatID"
export MONITOR_INTERVAL_MINUTES="5"

# Windows (cmd)
set ALPHA_VANTAGE_API_KEY=你的密钥
set TELEGRAM_BOT_TOKEN=你的Token
set TELEGRAM_CHAT_ID=你的ChatID
set MONITOR_INTERVAL_MINUTES=5

# Windows (PowerShell)
$env:ALPHA_VANTAGE_API_KEY="你的密钥"
$env:TELEGRAM_BOT_TOKEN="你的Token"
$env:TELEGRAM_CHAT_ID="你的ChatID"
$env:MONITOR_INTERVAL_MINUTES="5"
```

## 系统功能

### 1. 价格监控
- **USD/CNH汇率**: 从Alpha Vantage获取实时数据
- **布伦特原油**: 获取国际原油价格
- **自动计算涨跌幅**: 与上次数据对比计算百分比变化

### 2. 智能提醒
- **阈值提醒**: 价格超过设定阈值时推送
- **涨跌提醒**: 价格波动超过设定百分比时推送
- **每日汇总**: 每天凌晨发送当天价格汇总

### 3. 数据记录
- **price_history.json**: 保存历史价格数据
- **price_monitor.log**: 系统运行日志
- **数据持久化**: 重启后继续上次的价格对比

### 4. 错误处理
- **网络重试**: API调用失败自动重试
- **服务检测**: 启动时检查所有服务连接
- **优雅关闭**: Ctrl+C安全关闭并发送通知

## 故障排除

### 常见问题

#### 1. Telegram消息收不到
- ✅ 检查聊天ID是否正确
- ✅ 确认给机器人发送过消息
- ✅ 尝试访问 `https://api.telegram.org/botYOUR_TOKEN/getMe`

#### 2. Alpha Vantage API失败
- ✅ 检查API密钥是否正确
- ✅ 确认没有超过调用限制(5次/分钟)
- ✅ 可能需要VPN访问

#### 3. 程序启动失败
- ✅ 检查Python版本 >= 3.8
- ✅ 运行 `pip install -r requirements.txt`
- ✅ 检查配置文件是否存在

#### 4. 在Windows上运行问题
- ✅ 使用PowerShell而非CMD
- ✅ 设置PYTHONIOENCODING=utf-8
- ✅ 路径不要包含中文或空格

### 日志检查
```bash
# 查看日志
tail -f price_monitor.log

# 查看详细日志
cat price_monitor.log | grep ERROR
```

### 测试命令
```bash
# 测试网络连接
curl -I https://www.alphavantage.co

# 测试Telegram
curl "https://api.telegram.org/botYOUR_TOKEN/getMe"

# 测试Alpha Vantage
curl "https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency=USD&to_currency=CNH&apikey=YOUR_KEY"
```

## 高级配置

### 自定义提醒消息
编辑 `telegram_bot.py` 中的 `format_price_message` 函数可以自定义消息格式。

### 添加更多监控资产
编辑 `config.py` 添加更多资产后，修改 `data_collector.py` 增加对应的获取函数。

### 增加其他推送方式
可以在 `telegram_bot.py` 旁创建其他推送类，如 `email_sender.py`、`dingtalk_bot.py`。

### 部署到云服务器
1. 购买阿里云/腾讯云/华为云轻量服务器(月费约5-15元)
2. 通过SSH上传代码
3. 使用systemd或cron运行
4. 配置防火墙和安全组

## 安全建议

1. **不要公开API密钥**: 不要将config.py上传到GitHub
2. **使用环境变量**: 生产环境建议使用环境变量而非配置文件
3. **限制访问**: 如果部署在服务器，配置防火墙限制访问
4. **定期更新**: 定期更新依赖包保证安全

## 支持与反馈

遇到问题可以:
1. 查看日志文件 `price_monitor.log`
2. 测试单个模块 `python data_collector.py`
3. 检查API密钥是否有效

如需修改功能或添加新特性，可以联系开发者或自行修改源代码。