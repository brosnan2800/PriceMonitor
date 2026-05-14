# 极空间 NAS 时钟偏差 Bug 复盘

> 记录从 2026-05-11 到 2026-05-13 历时三天、三次修复的时钟偏差问题全过程。

---

## 一、问题现象

每天 09:00 应推送的 A 股指数早报，在 NAS 重启后没有发出。

**生产环境背景：**
- 极空间 NAS，每天 03:16 自动关机，08:00 自动开机
- Docker 容器随 NAS 开机自动拉起
- APScheduler cron 任务负责 09:00 推送早报

---

## 二、根本原因：硬件时钟与 NTP 的混淆

电脑有两个时钟：

| 时钟 | 说明 |
|------|------|
| **RTC（硬件时钟）** | 主板电池供电，断电也走，但精度差，会漂移 |
| **系统时钟** | 操作系统维护，开机从 RTC 读取，之后靠 NTP 校准 |

**极空间的 bug：**
RTC 里存的是 **本地时间（CST，UTC+8）**，但极空间 Linux 系统开机时把它当成 **UTC** 读，再加 8 小时，导致系统时钟偏快约 **7~8 小时**。

```
实际现在：北京时间 09:17（CST）
RTC 存的：09:17（本地时间，但被当 UTC 读）
系统时钟：09:17 + 8h = 17:17  ← 偏快 8 小时
```

NTP 服务会慢慢把时间拉回正确值，这个纠正过程可能需要几分钟到几十分钟。在纠正完成前，系统时间是错的。

---

## 三、为什么 APScheduler 会受影响

APScheduler 的 cron trigger 在每次触发后，会**立刻计算下一次 run_date（绝对时间戳）** 并存起来。

**问题时序：**
```
08:00  NAS 开机
08:01  容器启动，系统时间显示 17:17（偏快 ~8 小时）
08:01  APScheduler 启动，注册 cron: "每天 09:00"
       当前时间是 17:17，今天 09:00 已经"过了"
       → next_run = 明天 09:00  ❌

08:30  NTP 把系统时间纠正到 08:31
       APScheduler 的 next_run 已定为明天，不会自动回来

09:00  今天没有早报 ❌
```

---

## 四、三次修复历史

### 第一次（2026-05-11）：`restart: always`

**现象：** 早报完全没收到，容器没在运行。

**原因：** `docker-compose.yml` 里是 `restart: unless-stopped`，NAS 关机再开机后容器不会自动拉起。

**修复：** 改为 `restart: always`。

**结果：** 解决了容器不启动的问题，但那天 NTP 纠正较快，时钟 bug 没有暴露。

---

### 第二次（2026-05-12）：startup 补发 + APScheduler date trigger

**现象：** 容器启动了，但 09:00 早报没来。查日志发现启动时间显示为 16:17（偏快 7 小时多）。

**分析：** 确认 NAS 时钟偏差问题。APScheduler 看到"现在是下午"，把今天早报排到了明天。

**修复思路：** 加 `_schedule_startup_morning_report()`，在 08:00-12:00 窗口内启动时，30 秒后补发一次。

**实现：**
```python
run_at = now + timedelta(seconds=30)
self._scheduler.add_job(
    self._job_index_report_all,
    "date",
    run_date=run_at,  # ← 绝对时间
)
```

**为什么还是失败：**

`APScheduler date trigger` 同样基于**绝对时间**。

```
当前系统时间 = 16:17（错的）
run_at = 16:17:30（绝对时间戳，也是错的）

NTP 把时间纠正到 08:18
→ APScheduler 发现 run_at=16:17:30 还在"未来"7小时
→ 等到 16:17:30 才执行  ❌
```

**副作用：** 没有去重，当天多次重启触发了多次补发，早报发了 3 次。

---

### 第三次（2026-05-13）：entrypoint NTP 等待 + threading.Timer + DB 去重

**两条并行修复线：**

#### 修复线 A：entrypoint 等 NTP 同步（治根）

在 `docker-entrypoint.sh` 里，应用启动前先轮询网络时间接口，等时钟准了再放行：

```bash
while [ $WAIT_TIME -lt $MAX_WAIT ]; do
    NET_TIME=$(curl -sf "http://quan.suning.com/getSysTime.do" | grep -oE "...")
    DIFF=$(( LOCAL_TS - NET_TS )); DIFF=${DIFF#-}  # 绝对值

    if [ "$DIFF" -lt 60 ]; then
        echo "时间已同步，启动机器人..."
        break
    fi
    sleep 10
done
exec python3 bot/app.py
```

这样 APScheduler 启动时拿到的是准确时间，今天 09:00 就是今天 09:00，不会再被排到明天。

**为什么选苏宁接口：** 纯国内网络，延迟极低，无需 API key。

#### 修复线 B：threading.Timer 替代 APScheduler date trigger（兜底）

即使 NTP 等待超时（300s 上限），仍保留启动补发逻辑，但把触发机制换掉：

```python
# ❌ 之前：APScheduler date trigger，基于绝对时间
self._scheduler.add_job(..., "date", run_date=now + timedelta(seconds=30))

# ✅ 现在：threading.Timer，基于 monotonic clock（单调时钟）
threading.Timer(30.0, self._job_index_report_all).start()
```

`threading.Timer` 内部用 `time.monotonic()`，从调用那一刻起倒计时 30 秒，**完全不看系统时钟，NTP 怎么跳都无所谓**。

#### 修复线 C：DB 去重防止多次补发

新增 `builtin_report_log` 表，早报发送前检查今天是否已发：

```sql
CREATE TABLE builtin_report_log (
    report_type TEXT,
    sent_date   TEXT,
    UNIQUE(report_type, sent_date)  -- 幂等，INSERT OR IGNORE
);
```

三道防线：
1. `_schedule_startup_morning_report()` 入口查 DB，已发则跳过调度
2. `_job_index_report_all()` 入口查 DB，已发则跳过执行
3. 成功发送后写入 DB

---

## 五、为什么极空间底层没法直接修

极空间 NAS 底层 OS 是定制的，`timedatectl`、`hwclock --systohc` 等命令要么没有权限，要么行为被锁死，无法直接修改 RTC 时区配置。只能在应用层规避。

---

## 六、最终架构

```
NAS 开机
  └─ Docker 容器启动
       └─ docker-entrypoint.sh
            ├─ [NTP 等待] 轮询苏宁时间接口，误差<60s 或超时300s
            └─ python3 bot/app.py
                 └─ TaskScheduler.start()
                      ├─ APScheduler 注册 cron（此时时钟已准，next_run 正确）
                      └─ _schedule_startup_morning_report()
                           ├─ 08:00-12:00 且今天早报未发（查DB）
                           └─ threading.Timer(30s) → 补发
                                └─ _job_index_report_all()
                                     ├─ 再次查DB去重
                                     ├─ 发送早报
                                     └─ 写入DB记录
```

---

## 七、涉及文件

| 文件 | 改动 |
|------|------|
| `docker-entrypoint.sh` | 新增 NTP 等待循环（最核心改动） |
| `Dockerfile` | apt-get 安装 `curl`（entrypoint 需要） |
| `bot/scheduler.py` | `threading.Timer` 替代 date trigger；DB 去重检查；`import threading` |
| `data/db.py` | 新增 `builtin_report_log` 表及 `builtin_report_sent_today`/`mark_builtin_report_sent` |
| `docker-compose.yml` | `restart: unless-stopped` → `restart: always`（第一次修复） |
