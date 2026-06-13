FROM python:3.11-slim

LABEL org.opencontainers.image.title="PanguAI"
LABEL org.opencontainers.image.description="盘古AI — 企业级小说写作系统"
LABEL org.opencontainers.image.version="2.0.0"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PANGU_LOG_FORMAT=json \
    PANGU_LOG_LEVEL=INFO

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir structlog pytest pytest-cov

# 应用代码
COPY . .

# 数据目录
RUN mkdir -p /app/projects /app/logs /app/.webnovel

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "from pangu_core.config import get_config; get_config()" || exit 1

EXPOSE 8000

# 默认: API 服务
CMD ["python", "-m", "uvicorn", "pangu_server.main:app", "--host", "0.0.0.0", "--port", "8000"]
