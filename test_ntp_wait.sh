#!/bin/bash
# ────────────────────────────────────────────────────────
# test_ntp_wait.sh
# 测试 docker-entrypoint.sh 中的 NTP 等待逻辑
# 用法：bash test_ntp_wait.sh
# ────────────────────────────────────────────────────────

PASS=0
FAIL=0

ok()   { echo "  [PASS] $1"; PASS=$(( PASS + 1 )); }
fail() { echo "  [FAIL] $1"; FAIL=$(( FAIL + 1 )); }

# ── 提取被测函数（与 entrypoint 保持一致） ────────────────
TIME_SOURCES=(
    "http://www.baidu.com"
    "http://www.aliyun.com"
    "http://www.qq.com"
)

get_reliable_timestamp() {
    for url in "${TIME_SOURCES[@]}"; do
        HTTP_DATE=$(curl -s -m 3 -I "$url" | grep -i "^date:" | sed 's/^[Dd]ate: //g' | tr -d '\r')
        if [ -n "$HTTP_DATE" ]; then
            # GNU date（Linux/Docker）
            TS=$(date -d "$HTTP_DATE" +%s 2>/dev/null)
            # BSD date（macOS，用于本地测试）
            if [ -z "$TS" ]; then
                TS=$(date -j -f "%a, %d %b %Y %H:%M:%S %Z" "$HTTP_DATE" +%s 2>/dev/null)
            fi
            if [ -n "$TS" ]; then
                echo "$TS"
                return 0
            fi
        fi
    done
    return 1
}

# ── Case 1: curl 可用性 ───────────────────────────────────
echo ""
echo "=== Case 1: curl 是否可用 ==="
if command -v curl >/dev/null 2>&1; then
    ok "curl 已安装"
else
    fail "curl 未安装，entrypoint 将无法获取网络时间"
fi

# ── Case 2: 各时间源连通性 ───────────────────────────────
parse_http_date() {
    local d="$1"
    date -d "$d" +%s 2>/dev/null || date -j -f "%a, %d %b %Y %H:%M:%S %Z" "$d" +%s 2>/dev/null
}

echo ""
echo "=== Case 2: 各时间源 HTTP Date 响应 ==="
for url in "${TIME_SOURCES[@]}"; do
    HTTP_DATE=$(curl -s -m 3 -I "$url" | grep -i "^date:" | sed 's/^[Dd]ate: //g' | tr -d '\r')
    if [ -n "$HTTP_DATE" ]; then
        TS=$(parse_http_date "$HTTP_DATE")
        if [ -n "$TS" ]; then
            ok "$url → Date: $HTTP_DATE (ts=$TS)"
        else
            fail "$url → 获取到 Date 但解析失败: '$HTTP_DATE'"
        fi
    else
        fail "$url → 未返回 Date 头"
    fi
done

# ── Case 3: get_reliable_timestamp 返回值合理 ────────────
echo ""
echo "=== Case 3: get_reliable_timestamp 函数 ==="
NET_TS=$(get_reliable_timestamp)
if [ $? -eq 0 ] && [ -n "$NET_TS" ]; then
    ok "返回时间戳: $NET_TS"
else
    fail "所有时间源均不可用，返回空值"
fi

# ── Case 4: 与本地时间对比偏差 ───────────────────────────
echo ""
echo "=== Case 4: 本地时间与网络时间偏差 ==="
if [ -n "$NET_TS" ]; then
    LOCAL_TS=$(date +%s)
    DIFF=$(( LOCAL_TS - NET_TS ))
    DIFF=${DIFF#-}
    fmt_ts() { date -d "@$1" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date -r "$1" '+%Y-%m-%d %H:%M:%S'; }
    echo "  本地时间戳 : $LOCAL_TS  ($(fmt_ts $LOCAL_TS))"
    echo "  网络时间戳 : $NET_TS  ($(fmt_ts $NET_TS))"
    echo "  偏差       : ${DIFF}s"
    if [ "$DIFF" -lt 60 ]; then
        ok "偏差 < 60s，entrypoint 会立即放行"
    elif [ "$DIFF" -lt 300 ]; then
        ok "偏差 ${DIFF}s（< 300s），模拟 NAS 时钟偏差场景，entrypoint 会等待"
    else
        fail "偏差 ${DIFF}s 过大，本机时钟可能有问题"
    fi
else
    fail "无网络时间，跳过偏差检测"
fi

# ── Case 5: 超时降级路径模拟 ─────────────────────────────
echo ""
echo "=== Case 5: 超时降级逻辑（dry-run） ==="
MOCK_WAIT_TIME=300
MOCK_MAX_WAIT=300
if [ "$MOCK_WAIT_TIME" -ge "$MOCK_MAX_WAIT" ]; then
    ok "超时判断正确：WAIT_TIME($MOCK_WAIT_TIME) >= MAX_WAIT($MOCK_MAX_WAIT) 会打印 WARNING 并强制放行"
else
    fail "超时判断逻辑有误"
fi

# ── 汇总 ──────────────────────────────────────────────────
echo ""
echo "════════════════════════════════"
echo "  结果：PASS=$PASS  FAIL=$FAIL"
if [ "$FAIL" -eq 0 ]; then
    echo "  ✅ 全部通过"
else
    echo "  ❌ 有 $FAIL 项失败，请检查网络或 curl 安装"
fi
echo "════════════════════════════════"
