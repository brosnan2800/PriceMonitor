#!/usr/bin/env bash
# 综合秘书机器人 —— 停止脚本
# 用法：bash stop.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/secretary.pid"

echo "=============================="
echo " 综合秘书机器人 停止脚本"
echo "=============================="

KILLED=0

# 1. 通过 PID 文件停止
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "⏹  停止主进程 PID=$OLD_PID ..."
        kill "$OLD_PID"
        sleep 2
        kill -0 "$OLD_PID" 2>/dev/null && kill -9 "$OLD_PID" && echo "   强制终止 PID=$OLD_PID"
        KILLED=$((KILLED+1))
    else
        echo "ℹ️  PID=$OLD_PID 已不存在"
    fi
    rm -f "$PID_FILE"
fi

# 2. 兜底：杀掉所有相关进程
for PATTERN in "python.*bot/app.py" "python.*bot\.app" "python.*price_monitor.py"; do
    PIDS=$(pgrep -f "$PATTERN" 2>/dev/null)
    for PID in $PIDS; do
        echo "⏹  终止残留进程 PID=$PID ($PATTERN)"
        kill "$PID" 2>/dev/null
        KILLED=$((KILLED+1))
    done
done

sleep 1

# 3. 验证
REMAINING=$(pgrep -f "python.*(bot/app|bot\.app|price_monitor)" 2>/dev/null | wc -l | tr -d ' ')
if [ "$REMAINING" -eq 0 ]; then
    if [ "$KILLED" -gt 0 ]; then
        echo "✅ 所有机器人服务已停止"
    else
        echo "ℹ️  没有发现运行中的机器人服务"
    fi
else
    echo "⚠️  仍有 $REMAINING 个进程未终止，尝试强制杀..."
    pgrep -f "python.*(bot/app|bot\.app|price_monitor)" | xargs kill -9 2>/dev/null
    echo "✅ 强制终止完成"
fi
