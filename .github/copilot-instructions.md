# Copilot 工作规范

## 运维任务（必读）

执行任何部署、重启、配置修改等运维操作前，**必须先读取项目根目录的 `OPS.md`**。

OPS.md 包含：
- 开发环境与生产环境的路径和 SSH 别名（mydocker）
- 容器名、bind-mount 说明
- 标准部署流程（rsync → docker build → docker-compose up --force-recreate）
- .env 修改方式（宿主机直接编辑，restart 生效）
- docker-compose 常用命令
- NAS 极空间特殊说明（时钟偏差、threading.Timer 等）

**不要**：
- 尝试在生产环境使用 git pull
- 在不了解 bind-mount 结构的情况下直接重建容器
- 使用 APScheduler date trigger（NAS 时钟偏差问题，用 threading.Timer）

## 项目简介

PriceMonitor：飞书秘书机器人，支持 A 股/美股行情、早报推送、多用户自定义任务。
生产环境运行在极空间 NAS Docker 容器中（`secretary-bot`）。
