# ══════════════════════════════════════════════════════════════════
# 综合秘书机器人配置文件（本地开发用）
# Docker 部署请使用 .env 文件，无需修改此文件
# 复制为 config.py：cp config.example.py config.py
# ══════════════════════════════════════════════════════════════════

# ── 飞书配置（必填） ────────────────────────────────────────────────
# 运行 python3 feishu_setup.py 扫码自动填写以下三项
FEISHU_APP_ID = "your_feishu_app_id"
FEISHU_APP_SECRET = "your_feishu_app_secret"
FEISHU_OPEN_ID = ""   # 私聊推送，由 feishu_setup.py 自动获取
FEISHU_CHAT_ID = ""   # 群聊 ID，可选

# ── 启用平台 ────────────────────────────────────────────────────────
ENABLED_PLATFORMS = ["feishu"]  # 可选：["feishu"] 或 ["feishu", "telegram"]

# ── Telegram（可选次选平台） ────────────────────────────────────────
TELEGRAM_BOT_TOKEN = ""  # 格式: 1234567890:ABCdef...
TELEGRAM_CHAT_ID = ""    # 从 /getUpdates 获取

# ── Alpha Vantage（可选，汇率/原油查询） ───────────────────────────
# 申请地址：https://www.alphavantage.co/support/#api-key
ALPHA_VANTAGE_API_KEY = ""
API_REQUEST_INTERVAL_SECONDS = 2  # 两次调用间隔（秒）

# ── 日志配置 ───────────────────────────────────────────────────────
LOG_LEVEL = "INFO"   # DEBUG / INFO / WARNING / ERROR
LOG_FILE = "secretary.log"

# ── 调度任务配置 ────────────────────────────────────────────────────
PRICE_ALERT_INTERVAL_MINUTES = 5   # 价格预警检查间隔（分钟）
DAILY_DIGEST_HOUR = 15             # 收盘日报小时
DAILY_DIGEST_MINUTE = 30           # 收盘日报分钟
MORNING_REPORT_HOUR = 9            # 早报小时
MORNING_REPORT_MINUTE = 0          # 早报分钟

