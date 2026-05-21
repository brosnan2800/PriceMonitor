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

### 发布原则

1. **代码每次整套同步**
   - 不要只传单个 `.py` 文件做正式发布
   - 正式换版一律同步完整项目到生产目录，避免 `scheduler.py` / `db.py` / `data/` 版本不一致

2. **数据库结构按代码增量迁移**
   - 生产库以 `init_db()` 中的 `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ADD COLUMN` 为准
   - 正常情况下不要手工改生产 SQLite 表结构

3. **`.env` 只在配置变更时更新**
   - 配置没变，不需要改 `.env`
   - 配置有变更时，先备份 `.env`，再编辑，再 `docker-compose restart`

4. **发布后一定核对“实际运行代码”**
   - 不能只看 build 成功、容器启动正常
   - 还要确认容器实际读取的代码来源是对的：镜像内代码 + bind-mount 宿主机目录都要一致

### 代码来源说明（非常重要）

生产容器运行时的代码并不只来自镜像，还会受到 bind-mount 影响：

| 来源 | 路径 | 说明 |
|------|------|------|
| 镜像内代码 | `/app/` | `docker build` 产物 |
| 宿主机挂载数据目录 | `/root/Desktop/priceMonitor/data/ -> /app/data/` | 会覆盖容器内 `/app/data/` 对应内容 |
| 宿主机挂载配置文件 | `/root/Desktop/priceMonitor/.env -> /app/.env` | 会覆盖镜像内同路径配置 |

**因此正式发布不能只 build 镜像，还必须确保宿主机 `priceMonitor/` 目录也是最新版。**

### ✅ 标准部署流程

```bash
# 0. 生产换版前先做一次上线前备份
ssh mydocker "bash /root/Desktop/priceMonitor/backup_production.sh predeploy"

# 1. 把源码 rsync 到 mydocker 临时构建目录（用于构建镜像）
rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='data/secretary.db' --exclude='*.log' \
  "/Users/yanglei/develop/claude world/claudework/" \
  "mydocker:/tmp/pricemonitor-build/"

# 2. 同步完整源码到生产目录（保证 bind-mount 目录也是最新版）
rsync -av --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='data/secretary.db' --exclude='*.log' \
  "/Users/yanglei/develop/claude world/claudework/" \
  "mydocker:/root/Desktop/priceMonitor/"

# 3. 在 mydocker 上构建新镜像
ssh mydocker "cd /tmp/pricemonitor-build && docker build --no-cache -t pricemonitor-bot . 2>&1 | tail -5"

# 4. 用新镜像重建容器（--force-recreate 确保使用新镜像，data/.env 挂载不受影响）
ssh mydocker "cd /root/Desktop/priceMonitor && docker-compose up -d --force-recreate"

# 5. 确认启动正常
ssh mydocker "cd /root/Desktop/priceMonitor && docker-compose logs --tail 20"

# 6. 清理旧镜像和临时构建目录（确认新版本运行正常后再执行）
ssh mydocker "docker image prune -a -f && rm -rf /tmp/pricemonitor-build"
```

> 说明：
> - `docker build --no-cache` 会持续累积旧镜像层，mydocker 系统盘只有 20G，长期不清理容易满盘。
> - `/tmp/pricemonitor-build` 只是临时构建目录，部署完成后可以删除。
> - **必须先确认新容器已正常启动，再执行清理**，避免误删排障所需现场。
> - 发布后的核验重点不是“容器起来了”，而是“运行时读到的代码确实是本次发布版本”。

---

## 生产备份

### 备份对象

| 路径 | 内容 |
|------|------|
| `/root/Desktop/priceMonitor/data/secretary.db` | 生产 SQLite 数据库 |
| `/root/Desktop/priceMonitor/.env` | 生产环境配置 |

### 备份脚本

```bash
/root/Desktop/priceMonitor/backup_production.sh
```

支持模式：

```bash
ssh mydocker "bash /root/Desktop/priceMonitor/backup_production.sh daily"
ssh mydocker "bash /root/Desktop/priceMonitor/backup_production.sh weekly"
ssh mydocker "bash /root/Desktop/priceMonitor/backup_production.sh predeploy"
ssh mydocker "bash /root/Desktop/priceMonitor/backup_production.sh env-change"
```

### 保留策略

| 类型 | 频率 | 保留数量 |
|------|------|----------|
| daily | 每天 1 次 | 7 份 |
| weekly | 每周 1 次 | 4 份 |
| predeploy | 每次发布前 | 5 份 |
| env-change | 每次改 `.env` 后 | 4 份 |

### cron 安装命令

> 选择 03:00 / 03:05，是为了在 NAS 每天 03:16 自动关机前完成备份。

```bash
ssh mydocker 'crontab -l 2>/dev/null | {
  cat
  echo "0 3 * * * /root/Desktop/priceMonitor/backup_production.sh daily >> /root/Desktop/priceMonitor-backups/backup.log 2>&1"
  echo "5 3 * * 0 /root/Desktop/priceMonitor/backup_production.sh weekly >> /root/Desktop/priceMonitor-backups/backup.log 2>&1"
} | crontab -'
```

### 查看备份

```bash
ssh mydocker "find /root/Desktop/priceMonitor-backups -maxdepth 2 -type d | sort"
```

### 备份文件说明

```text
/root/Desktop/priceMonitor-backups/
├── daily/
├── weekly/
├── predeploy/
├── env-change/
└── manual/
```

每个时间戳备份目录内通常包含：

| 文件 | 说明 |
|------|------|
| `secretary.db` | SQLite 数据库备份 |
| `.env` | 生产配置备份 |
| `backup_meta.txt` | 备份模式、时间戳、主机名等元信息 |

数据库备份使用 Python `sqlite3.backup()`，比直接复制在线 SQLite 文件更稳。

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

`.env` 存放在宿主机 `/root/Desktop/priceMonitor/.env`，以 bind-mount 方式挂载进容器。

**直接在宿主机（mydocker）上编辑，restart 即可生效：**
```bash
# 在 mydocker 上编辑（vi 或其他方式）
ssh mydocker "vi /root/Desktop/priceMonitor/.env"

# 先备份 .env
ssh mydocker "bash /root/Desktop/priceMonitor/backup_production.sh env-change"

# 重启容器让新配置生效
ssh mydocker "cd /root/Desktop/priceMonitor && docker-compose restart"
```

**注意：只有以下路径是 bind-mount（宿主机编辑有效）：**

| 宿主机路径 | 说明 |
|-----------|------|
| `/root/Desktop/priceMonitor/.env` | 环境变量，restart 生效 |
| `/root/Desktop/priceMonitor/data/` | 数据库持久化，不需要重启 |
| `/root/Desktop/priceMonitor/logs/` | 日志输出，不需要重启 |

**代码文件（`.py`）不在挂载列表里，修改代码必须重新构建镜像（见"部署新版本"）。**

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
