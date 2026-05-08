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
        grep "^${key}=" "$env_path" | tail -n 1 | cut -d= -f2-
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

echo "✅ 飞书配置已就绪，启动机器人..."
exec python3 bot/app.py
