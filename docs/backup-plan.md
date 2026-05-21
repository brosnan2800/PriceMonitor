# 生产备份计划（mydocker）

## 目标

为生产环境的以下关键文件建立轻量、可恢复、低维护成本的备份：

- 数据库：`/root/Desktop/priceMonitor/data/secretary.db`
- 配置：`/root/Desktop/priceMonitor/.env`

## 方案

### 1. 备份频率

| 类型 | 频率 | 保留 |
|------|------|------|
| 日备份 | 每天 1 次 | 7 份 |
| 周备份 | 每周 1 次 | 4 份 |
| 上线前备份 | 每次生产换版前手动执行 | 5 份 |
| `.env` 变更备份 | 每次修改 `.env` 后手动执行 | 4 份 |

### 2. 备份目录

```text
/root/Desktop/priceMonitor-backups/
├── daily/
├── weekly/
├── predeploy/
└── env-change/
```

每次备份都会创建一个时间戳目录，例如：

```text
/root/Desktop/priceMonitor-backups/daily/20260521-030000/
├── secretary.db
├── .env
└── backup_meta.txt
```

### 3. 备份脚本

脚本位置：

```bash
/root/Desktop/priceMonitor/backup_production.sh
```

支持模式：

```bash
bash /root/Desktop/priceMonitor/backup_production.sh daily
bash /root/Desktop/priceMonitor/backup_production.sh weekly
bash /root/Desktop/priceMonitor/backup_production.sh predeploy
bash /root/Desktop/priceMonitor/backup_production.sh env-change
bash /root/Desktop/priceMonitor/backup_production.sh manual
```

## 实施步骤

### A. 部署脚本到生产机

```bash
rsync -av "/Users/yanglei/develop/claude world/claudework/backup_production.sh" \
  "mydocker:/root/Desktop/priceMonitor/"

ssh mydocker "chmod +x /root/Desktop/priceMonitor/backup_production.sh"
```

### B. 先执行一次手工备份

```bash
ssh mydocker "bash /root/Desktop/priceMonitor/backup_production.sh manual"
```

### C. 安装 cron

建议在 **03:00 前后** 执行，确保在 NAS 每天 03:16 自动关机前完成。

```bash
ssh mydocker 'crontab -l 2>/dev/null | {
  cat
  echo "0 3 * * * /root/Desktop/priceMonitor/backup_production.sh daily >> /root/Desktop/priceMonitor-backups/backup.log 2>&1"
  echo "5 3 * * 0 /root/Desktop/priceMonitor/backup_production.sh weekly >> /root/Desktop/priceMonitor-backups/backup.log 2>&1"
} | crontab -'
```

### D. `.env` 修改后的操作

```bash
ssh mydocker "vi /root/Desktop/priceMonitor/.env"
ssh mydocker "bash /root/Desktop/priceMonitor/backup_production.sh env-change"
ssh mydocker "cd /root/Desktop/priceMonitor && docker-compose restart"
```

### E. 每次生产换版前先备份

```bash
ssh mydocker "bash /root/Desktop/priceMonitor/backup_production.sh predeploy"
```

然后再执行正常发布流程。

## 恢复步骤

### 恢复数据库

1. 停止容器
2. 用某个备份目录中的 `secretary.db` 覆盖生产库
3. 再启动容器

```bash
ssh mydocker "cd /root/Desktop/priceMonitor && docker-compose stop"
ssh mydocker "cp /root/Desktop/priceMonitor-backups/daily/20260521-030000/secretary.db /root/Desktop/priceMonitor/data/secretary.db"
ssh mydocker "cd /root/Desktop/priceMonitor && docker-compose up -d"
```

### 恢复 `.env`

```bash
ssh mydocker "cp /root/Desktop/priceMonitor-backups/env-change/20260521-101500/.env /root/Desktop/priceMonitor/.env"
ssh mydocker "cd /root/Desktop/priceMonitor && docker-compose restart"
```

## 注意事项

- 数据库备份使用 Python `sqlite3.backup()`，比直接 `cp` 正在使用中的 SQLite 文件更稳。
- `.env` 可能包含敏感信息，备份目录只保留在生产机本地，注意权限控制。
- 保留策略由脚本自动执行，不需要每月人工清理。
- 如果后续要更稳，可以再加一份异机备份（例如定期 rsync 到另一台机器或 NAS 共享目录）。
