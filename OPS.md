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
| 容器内应用路径 | `/app/` |
| 宿主机项目路径 | `/root/Desktop/priceMonitor/` |
| **注意** | 宿主机路径**不是 git 仓库**，不能 `git pull` |

### 宿主机绑定挂载

| 宿主机路径 | 容器内路径 | 说明 |
|-----------|-----------|------|
| `/root/Desktop/priceMonitor/data/` | `/app/data/` | 数据库（secretary.db）持久化 |
| `/root/Desktop/priceMonitor/.env` | `/app/.env` | 环境变量配置 |
| `/root/Desktop/priceMonitor/logs/` | `/app/logs/` | 日志持久化 |

### 部署代码到生产环境

**不要 git pull！** 正确方式是 scp → docker cp → restart：

```bash
# 1. 拷贝文件到 mydocker
scp "/Users/yanglei/develop/claude world/claudework/bot/scheduler.py" mydocker:/tmp/
scp "/Users/yanglei/develop/claude world/claudework/data/db.py" mydocker:/tmp/

# 2. 复制进容器（注意：data/ 挂载到宿主机，db.py 要单独 docker cp）
ssh mydocker "docker cp /tmp/scheduler.py secretary-bot:/app/bot/scheduler.py"
ssh mydocker "docker cp /tmp/db.py secretary-bot:/app/data/db.py"

# 3. 重启容器
ssh mydocker "docker restart secretary-bot"

# 4. 查看日志确认启动正常
ssh mydocker "docker logs secretary-bot --tail 30"
```

### 常用运维命令

```bash
# 查看容器状态
ssh mydocker "docker ps | grep secretary"

# 实时查看日志
ssh mydocker "docker logs secretary-bot -f --tail 50"

# 进入容器 shell
ssh mydocker "docker exec -it secretary-bot bash"

# 查看数据库用户
ssh mydocker "docker exec secretary-bot sqlite3 /app/data/secretary.db 'SELECT user_id, platform, settings FROM users'"

# 重启容器
ssh mydocker "docker restart secretary-bot"
```

---

## NAS 特殊说明

- **设备**：极空间 NAS（192.168.1.108）
- **定时关机**：每天 03:16 自动关机
- **定时开机**：每天 08:00 自动开机
- **已知 bug**：开机时硬件时钟偏快约 7 小时（RTC/NTP 混淆），NTP 慢慢纠正
- **代码缓解**：`_schedule_startup_morning_report()` 用 `threading.Timer`（不受时钟跳变影响）在启动后 30 秒补发早报，并通过 `builtin_report_log` DB 表防止重复推送
- **`restart: always`**：docker-compose.yml 已设置，确保 NAS 开机后容器自动拉起

---

## .env 配置

`.env` 存放在宿主机 `/root/Desktop/priceMonitor/.env`，挂载进容器，**修改后需 restart 容器生效**。

```bash
# 修改 .env 后重启
ssh mydocker "docker restart secretary-bot"
```

主要 key（详见 config.example.py）：
- `FEISHU_APP_ID` / `FEISHU_APP_SECRET`
- `ALPHA_VANTAGE_API_KEY`
- `MORNING_REPORT_HOUR` / `MORNING_REPORT_MINUTE`
