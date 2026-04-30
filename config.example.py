# ══════════════════════════════════════════════════════════════════
# 综合秘书机器人配置文件
# 复制为 config.py 并填写你的密钥：cp config.example.py config.py
# ══════════════════════════════════════════════════════════════════

# ── 渠道配置（飞书为主，Telegram 为次） ────────────────────────────

# 启用的平台列表（可选：feishu / telegram / 两者都填）
ENABLED_PLATFORMS = ["feishu"]  # 推荐：["feishu"] 或 ["feishu", "telegram"]

# ── 飞书配置（主平台） ─────────────────────────────────────────────
# 运行 python feishu_setup.py 扫码自动填写以下三项
FEISHU_APP_ID = "your_feishu_app_id"        # 飞书开放平台应用 ID
FEISHU_APP_SECRET = "your_feishu_app_secret"  # 飞书开放平台应用密钥
FEISHU_OPEN_ID = ""   # 你的飞书 open_id（私聊推送，由 feishu_setup.py 自动获取）
FEISHU_CHAT_ID = ""   # 飞书群聊 ID（群聊推送，可选）
# 接收模式：WebSocket 长连接（无需公网 IP / ngrok，极空间 Docker 友好）

# ── Telegram 配置（次选平台） ──────────────────────────────────────
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # 格式: 1234567890:ABCdef...
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"               # 从 /getUpdates 获取

# ── 数据源配置 ─────────────────────────────────────────────────────
# Alpha Vantage（汇率/原油，免费 500次/天）
# 申请地址：https://www.alphavantage.co/support/#api-key
ALPHA_VANTAGE_API_KEY = "YOUR_ALPHA_VANTAGE_API_KEY"
ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"
API_REQUEST_INTERVAL_SECONDS = 2  # 两次 Alpha Vantage 调用间隔（秒）

# 主数据源：腾讯财经（A股/港股/全球指数）+ Binance（加密货币），无需密钥
# AKShare 当前因网络环境问题暂停使用（公告数据备用）

# ── 日志配置 ───────────────────────────────────────────────────────
LOG_LEVEL = "INFO"   # DEBUG / INFO / WARNING / ERROR
LOG_FILE = "secretary.log"

# ── 调度任务配置 ────────────────────────────────────────────────────
# 价格预警检查间隔（分钟），建议 5~30，越小越灵敏但消耗更多请求
PRICE_ALERT_INTERVAL_MINUTES = 5

# 每日收盘日报推送时间（工作日，24小时制）
DAILY_DIGEST_HOUR = 15
DAILY_DIGEST_MINUTE = 30

# 每日早报推送时间（工作日，24小时制）
MORNING_REPORT_HOUR = 9
MORNING_REPORT_MINUTE = 0

# ── 遗留配置（保持向后兼容，v1 price_monitor.py 使用） ────────────
MONITOR_INTERVAL_MINUTES = 5
USD_CNH_UPPER_THRESHOLD = 7.15
USD_CNH_LOWER_THRESHOLD = 7.10
BRENT_OIL_CHANGE_THRESHOLD_PERCENT = 1.0
MONITOR_ASSETS = {
    "USD/CNH": {
        "function": "CURRENCY_EXCHANGE_RATE",
        "from_currency": "USD",
        "to_currency": "CNH"
    },
    "BRENT_OIL": {
        "function": "BRENT",
        "interval": "daily"
    }
}
NOTIFICATION_PLATFORM = "feishu"  # 遗留字段