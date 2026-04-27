# 配置文件 - 请复制为 config.py 并填写您的密钥

# Alpha Vantage API 配置
ALPHA_VANTAGE_API_KEY = "YOUR_ALPHA_VANTAGE_API_KEY"

# Telegram 机器人配置
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # 格式: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"  # 从getUpdates获取的数字ID

# 监控配置
MONITOR_INTERVAL_MINUTES = 5  # 检查间隔（分钟）
API_REQUEST_INTERVAL_SECONDS = 2  # Alpha Vantage 两次接口调用之间的间隔（秒）

# 价格阈值提醒设置
USD_CNH_UPPER_THRESHOLD = 7.15  # USD/CNH 上涨提醒阈值
USD_CNH_LOWER_THRESHOLD = 7.10  # USD/CNH 下跌提醒阈值

BRENT_OIL_CHANGE_THRESHOLD_PERCENT = 1.0  # 原油价格波动提醒阈值（百分比）

# API端点配置
ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"

# 监控资产配置
MONITOR_ASSETS = {
    "USD/CNH": {
        "function": "CURRENCY_EXCHANGE_RATE",
        "from_currency": "USD",
        "to_currency": "CNH"
    },
    "BRENT_OIL": {
        "function": "GLOBAL_QUOTE",
        "symbol": "BRNT"  # Alpha Vantage中的布伦特原油代码
    }
}

# 日志配置
LOG_LEVEL = "INFO"
LOG_FILE = "price_monitor.log"

# 飞书机器人配置（可选）
# 运行 python feishu_setup.py 扫码自动填写以下配置
FEISHU_APP_ID = "your_feishu_app_id"  # 飞书开放平台应用 ID
FEISHU_APP_SECRET = "your_feishu_app_secret"  # 飞书开放平台应用密钥
FEISHU_OPEN_ID = ""  # 你的飞书 open_id（私聊推送，由 feishu_setup.py 自动获取）
FEISHU_CHAT_ID = ""  # 飞书群聊 ID（群聊推送，可选）

# 平台选择配置
ENABLED_PLATFORMS = ["telegram", "feishu"]  # 支持的平台：telegram, feishu
NOTIFICATION_PLATFORM = "all"  # 可选：telegram, feishu, all