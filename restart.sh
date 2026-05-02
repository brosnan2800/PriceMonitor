#!/usr/bin/env bash
# 综合秘书机器人 —— 重启脚本
# 用法：bash restart.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/secretary.pid"
LOG_FILE="$SCRIPT_DIR/price_monitor.log"

echo "=============================="
echo " 综合秘书机器人 重启脚本"
echo "=============================="

# ── 1. 停止旧进程 ──────────────────────────────────────
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo "⏹  停止旧进程 PID=$OLD_PID ..."
        kill "$OLD_PID"
        sleep 2
        # 强杀
        kill -0 "$OLD_PID" 2>/dev/null && kill -9 "$OLD_PID"
    fi
    rm -f "$PID_FILE"
fi

# 额外兜底：杀掉所有同路径的 bot/app.py 进程
pkill -f "python.*bot/app.py" 2>/dev/null
sleep 1

# ── 2. 切换到项目目录 ──────────────────────────────────
cd "$SCRIPT_DIR" || { echo "❌ 找不到项目目录"; exit 1; }

# ── 3. 后台启动 ────────────────────────────────────────
echo "▶  启动机器人（后台运行，日志 → $LOG_FILE）..."
nohup python3 bot/app.py > /dev/null 2>&1 &
NEW_PID=$!
echo "$NEW_PID" > "$PID_FILE"

sleep 2

# ── 4. 检查是否启动成功 ────────────────────────────────
if kill -0 "$NEW_PID" 2>/dev/null; then
    echo "✅ 启动成功！PID=$NEW_PID"
    echo ""
    echo "📋 查看日志："
    echo "   tail -f $LOG_FILE"
    echo ""
    echo "⏹  停止机器人："
    echo "   kill \$(cat $PID_FILE)"
else
    echo "❌ 启动失败，查看日志："
    echo "   tail -20 $LOG_FILE"
    exit 1
fi
