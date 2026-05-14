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
# 最多等待 300 秒，超时后直接启动（降级：DB 防重兜底仍然有效）。
# 时间源：读取 HTTP 响应头 Date 字段，无需专用 API，多源高可用。
# ────────────────────────────────────────────────────────
TIME_SOURCES=(
    "http://www.baidu.com"
    "http://www.aliyun.com"
    "http://www.qq.com"
)

# 从时间源列表依次尝试，返回第一个可用的 Unix 时间戳
get_reliable_timestamp() {
    for url in "${TIME_SOURCES[@]}"; do
        HTTP_DATE=$(curl -s -m 3 -I "$url" | grep -i "^date:" | sed 's/^[Dd]ate: //g' | tr -d '\r')
        if [ -n "$HTTP_DATE" ]; then
            TS=$(date -d "$HTTP_DATE" +%s 2>/dev/null)
            if [ -n "$TS" ]; then
                echo "$TS"
                return 0
            fi
        fi
    done
    return 1
}

MAX_WAIT=300
WAIT_TIME=0

while [ "$WAIT_TIME" -lt "$MAX_WAIT" ]; do
    NET_TS=$(get_reliable_timestamp)
    LOCAL_TS=$(date +%s)

    if [ -n "$NET_TS" ]; then
        DIFF=$(( LOCAL_TS - NET_TS ))
        DIFF=${DIFF#-}  # 取绝对值

        if [ "$DIFF" -lt 60 ]; then
            echo "[ OK ] 系统时间已同步（误差 ${DIFF}s），启动机器人..."
            break
        fi

        echo "[WARN] 时间偏差 ${DIFF}s，等待 NTP 校准... (已等待 ${WAIT_TIME}s)"
    else
        echo "[WARN] 无法连接时间源，重试中... (已等待 ${WAIT_TIME}s)"
    fi

    sleep 10
    WAIT_TIME=$(( WAIT_TIME + 10 ))
done

if [ "$WAIT_TIME" -ge "$MAX_WAIT" ]; then
    echo "================================================================"
    echo "[WARNING] 前置时间同步超时（${MAX_WAIT}s）！"
    echo "[WARNING] 放弃等待。这可能会导致早报时间漂移，但系统有 DB 防重兜底。"
    echo "[WARNING] 为保证核心实时价格监控的可用性，强制放行！"
    echo "================================================================"
fi

echo "启动 PriceMonitor 核心进程..."
exec python3 bot/app.py
