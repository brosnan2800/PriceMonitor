# ────────────────────────────────────────────
# 综合秘书机器人 Dockerfile
# 基于 Python 3.11 slim，生产镜像
# ────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（qrcode 需要 Pillow，Pillow 需要这些库）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 先复制 requirements，利用 Docker 层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码（.env 和 data/ 通过 volume 挂载，不打入镜像）
COPY . .

# 创建数据和日志目录（volume 挂载点）
RUN mkdir -p data logs

# 入口脚本
COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 数据目录暴露为 volume（SQLite 持久化）
VOLUME ["/app/data", "/app/logs"]

ENTRYPOINT ["/entrypoint.sh"]
