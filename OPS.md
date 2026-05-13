# 运维手册（开发 & 生产环境）

> 此文档供开发者和 AI 助手参考，避免重复排查环境配置。

---

## 开发环境

| 项目 | 值 |
|------|-----|
| 本地 macOS 路径（主工作区） | `/Users/yanglei/develop/claude world/claudework` |
| 主分支 | `main` |
| 功能开发工作区 | `/Users/yanglei/develop/claude world/claudework.worktrees/agents-next-version-requirements-finance` |
| 功能分支 | `agents/next-version-requirements-finance` |
| GitHub 仓库 | `https://github.com/brosnan2800/PriceMonitor.git` |

### 开发工作流

```bash
# 在功能工作区开发 → commit
cd "/Users/yanglei/develop/claude world/claudework.worktrees/agents-next-version-requirements-finance"
git add -A && git commit -m "..."

# merge 到 main
GIT_EDITOR=true git -C "/Users/yanglei/develop/claude world/claudework" merge agents/next-version-requirements-finance

# push 到 GitHub
git -C "/Users/yanglei/develop/claude world/claudework" push origin main
```

---

## 生产环境（mydocker）

| 项目 | 值 |
|------|-----|
| SSH 别名 | `mydocker` |
| 容器名 | `secretary-bot` |
| docker-compose.yml 路径 | `/root/Desktop/priceMonitor/docker-compose.yml` |
| 容器内应用路径 | `/app/` |
| **注意** | 宿主机路径**不是 git 仓库**，不能 `git pull` |

### 宿主机绑定挂载

| 宿主机路径 | 容器内路径 | 说明 |
|-----------|-----------|------|
| `/root/Desktop/priceMonitor/data/` | `/app/data/` | 数据库（secretary.db）持久化 |
| `/root/Desktop/priceMonitor/.env` | `/app/.env` | 环境变量配置 |
| `/root/Desktop/priceMonitor/logs/` | `/app/logs/` | 日志持久化 |

---

## 常用运维命令（全部基于 docker-compose）

所有命令通过 `ssh mydocker` 在宿主机执行，工作目录 `/root/Desktop/priceMonitor`。

```bash
# 查看容器状态
ssh mydocker "cd /root/Desktop/priceMonitor && docker-compose ps"

# 查看最近日志（静态）
ssh mydocker "cd /root/Desktop/priceMonitor && docker-compose logs --tail 50"

# 实时追踪日志
ssh mydocker "cd /root/Desktop/priceMonitor && docker-compose logs -f --tail 50"

# 重启容器（配置/代码热更新后用）
ssh mydocker "cd /root/Desktop/priceMonitor && docker-compose restart"

# 停止容器
ssh mydocker "cd /root/Desktop/priceMonitor && docker-compose stop"

# 启动容器
ssh mydocker "cd /root/Desktop/priceMonitor && docker-compose up -d"

# 进入容器 shell
ssh mydocker "cd /root/Desktop/priceMonitor && docker-compose exec secretary-bot bash"

# 查看数据库用户
ssh mydocker "cd /root/Desktop/priceMonitor && docker-compose exec secretary-bot sqlite3 /app/data/secretary.db 'SELECT user_id, platform, settings FROM users'"
```

---

## 部署新版本到生产环境

mydocker **没有源码也没有 git 仓库**，需要在本地同步源码到服务器上远程构建。

### ✅ 标准部署流程

```bash
# 1. 把源码 rsync 到 mydocker 临时构建目录
rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='data/secretary.db' --exclude='*.log' \
  "/Users/yanglei/develop/claude world/claudework/" \
  "mydocker:/tmp/pricemonitor-build/"

# 2. 在 mydocker 上构建新镜像
ssh mydocker "cd /tmp/pricemonitor-build && docker build --no-cache -t pricemonitor-bot . 2>&1 | tail -5"

# 3. 用新镜像重建容器（--force-recreate 确保使用新镜像，data/.env 挂载不受影响）
ssh mydocker "cd /root/Desktop/priceMonitor && docker-compose up -d --force-recreate"

# 4. 确认启动正常
ssh mydocker "cd /root/Desktop/priceMonitor && docker-compose logs --tail 20"
```

### ⚡ 快速热更新（仅 .py 文件修改，调试用）

> **临时生效**，下次 `docker-compose up --force-recreate` 后丢失，不作为正式部署。

```bash
scp "/Users/yanglei/develop/claude world/claudework/bot/scheduler.py" mydocker:/tmp/
ssh mydocker "docker cp /tmp/scheduler.py secretary-bot:/app/bot/scheduler.py"
ssh mydocker "cd /root/Desktop/priceMonitor && docker-compose restart"
ssh mydocker "cd /root/Desktop/priceMonitor && docker-compose logs --tail 20"
```

---

## .env 配置

`.env` 存放在宿主机 `/root/Desktop/priceMonitor/.env`，挂载进容器。

**修改 .env 后需重启生效：**
```bash
ssh mydocker "cd /root/Desktop/priceMonitor && docker-compose restart"
```

主要 key（详见 config.example.py）：
- `FEISHU_APP_ID` / `FEISHU_APP_SECRET`
- `ALPHA_VANTAGE_API_KEY`
- `MORNING_REPORT_HOUR` / `MORNING_REPORT_MINUTE`

---

## NAS 特殊说明

- **设备**：极空间 NAS，docker 运行在极空间内置 Docker 管理器
- **定时关机**：每天 03:16 自动关机
- **定时开机**：每天 08:00 自动开机
- **`restart: always`**：docker-compose.yml 已设置，确保 NAS 开机后容器自动拉起
- **已知 bug**：开机时硬件时钟偏快约 7 小时（RTC/NTP 混淆），NTP 慢慢纠正，导致 APScheduler 把早报任务排到明天
- **代码缓解**：`_schedule_startup_morning_report()` 用 `threading.Timer`（不受时钟跳变影响）在启动 30 秒后补发早报；`builtin_report_log` DB 表确保当天无论重启多少次只发一次

