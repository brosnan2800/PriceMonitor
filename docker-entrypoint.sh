#!/bin/bash
set -e

# ────────────────────────────────────────────────────────
# 综合秘书机器人 Docker 启动入口
# 检查飞书配置是否完成，未完成则提示用户运行 feishu_setup.py
# ────────────────────────────────────────────────────────

read_env_file_var() {
    key="$1"
    env_path="/app/.env"
    if [ -f "$env_path" ]; then
        val=$(grep "^${key}=" "$env_path" | tail -n 1 | cut -d= -f2-)
        val="${val%\"}"
        val="${val#\"}"
        printf '%s' "$val"
    fi
}

EFFECTIVE_FEISHU_APP_ID="${FEISHU_APP_ID:-$(read_env_file_var FEISHU_APP_ID)}"
EFFECTIVE_FEISHU_APP_SECRET="${FEISHU_APP_SECRET:-$(read_env_file_var FEISHU_APP_SECRET)}"

FEISHU_READY=true

if [ -z "$EFFECTIVE_FEISHU_APP_ID" ] || [ "$EFFECTIVE_FEISHU_APP_ID" = "your_feishu_app_id" ]; then
    FEISHU_READY=false
fi
if [ -z "$EFFECTIVE_FEISHU_APP_SECRET" ] || [ "$EFFECTIVE_FEISHU_APP_SECRET" = "your_feishu_app_secret" ]; then
    FEISHU_READY=false
fi

if [ "$FEISHU_READY" = "false" ]; then
    echo ""
    echo "════════════════════════════════════════════════"
    echo "  ⚠️  飞书尚未配置，机器人无法启动"
    echo "════════════════════════════════════════════════"
    echo ""
    echo "  请在另一个终端中运行飞书扫码配置："
    echo ""
    echo "    docker exec -it secretary-bot python3 feishu_setup.py"
    echo ""
    echo "  扫码完成后，重启容器："
    echo ""
    echo "    docker-compose restart"
    echo ""
    echo "  或者直接手动编辑 .env 文件填入："
    echo "    FEISHU_APP_ID=cli_xxxx"
    echo "    FEISHU_APP_SECRET=xxxx"
    echo "    FEISHU_OPEN_ID=ou_xxxx"
    echo ""
    echo "  容器将保持运行，等待配置完成..."
    echo ""
    # 保持容器运行，不退出，让用户可以 docker exec 进来跑 setup
    exec tail -f /dev/null
fi

echo "✅ 飞书配置已就绪，等待系统时间同步..."

# ────────────────────────────────────────────────────────
# NTP 时钟同步等待
# 极空间 NAS 开机时硬件时钟偏快约 7 小时，NTP 纠正前 APScheduler 会把
# 今天的定时任务排到明天。此处等待本地时钟与网络时间误差 < 60 秒后再放行。
# 最多等待 600 秒，超时后直接启动（降级：与之前行为一致）。
# ────────────────────────────────────────────────────────
MAX_WAIT=600
WAIT_TIME=0

while [ "$WAIT_TIME" -lt "$MAX_WAIT" ]; do
    NET_TIME=$(curl -sf --max-time 5 "http://quan.suning.com/getSysTime.do" \
        | grep -oE "[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}")

    if [ -n "$NET_TIME" ]; then
        NET_TS=$(date -d "$NET_TIME" +%s 2>/dev/null)
        LOCAL_TS=$(date +%s)

        if [ -n "$NET_TS" ]; then
            DIFF=$(( LOCAL_TS - NET_TS ))
            DIFF=${DIFF#-}  # 取绝对值

            if [ "$DIFF" -lt 60 ]; then
                echo "✅ 系统时间已同步（误差 ${DIFF}s），启动机器人..."
                break
            fi

            echo "⏳ 时间偏差 ${DIFF}s，等待 NTP 校准... (已等待 ${WAIT_TIME}s)"
        fi
    else
        echo "⏳ 无法获取网络时间，继续等待... (已等待 ${WAIT_TIME}s)"
    fi

    sleep 10
    WAIT_TIME=$(( WAIT_TIME + 10 ))
done

if [ "$WAIT_TIME" -ge "$MAX_WAIT" ]; then
    echo "⚠️  等待超时（${MAX_WAIT}s），直接启动（时间可能仍有偏差）"
fi

exec python3 bot/app.py
