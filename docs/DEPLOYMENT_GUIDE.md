# 盘古AI系统 - 部署指南

> 版本: v1.0
> 更新日期: 2026-06-10
> 状态: 草稿

---

## 1. 环境要求

### 1.1 硬件要求

| 环境 | CPU | 内存 | 磁盘 |
|------|-----|------|------|
| 开发环境 | 4核 | 8GB | 10GB |
| 生产环境 | 8核 | 16GB | 50GB |

### 1.2 软件要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 必须 |
| SQLite | 3.x | 已内置于Python |
| pip | 22.0+ | 包管理 |

### 1.3 可选组件

| 组件 | 版本 | 说明 |
|------|------|------|
| Redis | 7.0+ | 缓存和任务队列 |
| PostgreSQL | 14+ | 生产数据库 |
| Docker | 24+ | 容器化部署 |

---

## 2. 开发环境安装

### 2.1 克隆代码

```bash
cd /path/to/projects
git clone https://your-repo/pangu-ai.git
cd pangu-ai
```

### 2.2 创建虚拟环境

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

### 2.3 安装依赖

```bash
# 安装核心依赖
pip install -r requirements.txt

# 安装可选依赖
pip install litellm redis psycopg2-binary
```

### 2.4 配置环境变量

```bash
# 创建 .env 文件
cp .env.example .env

# 编辑 .env
nano .env
```

**`.env.example`**:
```env
# LLM 配置
OPENAI_API_KEY=sk-your-api-key
DEEPSEEK_API_KEY=sk-your-deepseek-key

# 模型配置
LLM_MODEL=deepseek/deepseek-chat
LLM_TIMEOUT=180
LLM_RETRIES=3

# 数据库配置
DATABASE_PATH=knowledge/unified_novel.db

# Redis 配置 (可选)
REDIS_URL=redis://localhost:6379/0

# 日志配置
LOG_LEVEL=INFO
```

### 2.5 初始化数据库

```bash
# 运行初始化脚本
python scripts/unified_import.py --mode all

# 或分步导入
python scripts/unified_import.py --mode incremental
```

### 2.6 验证安装

```bash
# 启动开发服务器
python backend/app_v7.py

# 测试健康检查
curl http://127.0.0.1:5001/api/v7/health
```

**预期输出**:
```json
{
  "status": "ok",
  "version": "7.5",
  "litellm": true
}
```

---

## 3. 生产环境部署

### 3.1 Docker 部署 (推荐)

#### 3.1.1 创建 Dockerfile

```dockerfile
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要目录
RUN mkdir -p logs data

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

# 暴露端口
EXPOSE 5001

# 启动命令
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5001", "backend.app_v7:app"]
```

#### 3.1.2 创建 docker-compose.yml

```yaml
version: '3.8'

services:
  pangu:
    build: .
    ports:
      - "5001:5001"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - LLM_MODEL=${LLM_MODEL:-deepseek/deepseek-chat}
      - DATABASE_PATH=/app/data/unified_novel.db
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5001/api/v7/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  redis_data:
```

#### 3.1.3 启动服务

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f pangu

# 检查健康状态
curl http://localhost:5001/api/v7/health
```

### 3.2 传统部署

#### 3.2.1 安装系统依赖

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y python3.10 python3.10-venv python3-pip nginx

# CentOS/RHEL
sudo yum install -y python310 python310-pip nginx
```

#### 3.2.2 配置 Nginx

```nginx
# /etc/nginx/sites-available/pangu
upstream pangu_backend {
    server 127.0.0.1:5001;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://pangu_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 180s;
    }

    # 静态文件 (未来Web UI)
    location /static {
        alias /app/static;
        expires 30d;
    }
}
```

#### 3.2.3 配置 Gunicorn

```bash
# 安装 Gunicorn
pip install gunicorn

# 创建启动脚本
cat > /app/start.sh << 'EOF'
#!/bin/bash
gunicorn \
    --workers 4 \
    --bind 127.0.0.1:5001 \
    --timeout 300 \
    --access-logfile /app/logs/access.log \
    --error-logfile /app/logs/error.log \
    --log-level info \
    backend.app_v7:app
EOF

chmod +x /app/start.sh
```

#### 3.2.4 配置 Systemd 服务

```ini
# /etc/systemd/system/pangu.service
[Unit]
Description=Pangu AI Writing System
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/app
Environment="PATH=/app/venv/bin"
ExecStart=/app/start.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# 启用服务
sudo systemctl daemon-reload
sudo systemctl enable pangu
sudo systemctl start pangu

# 检查状态
sudo systemctl status pangu
```

---

## 4. 数据库配置

### 4.1 SQLite (开发环境)

默认使用 SQLite，无需额外配置。

```env
DATABASE_PATH=knowledge/unified_novel.db
```

### 4.2 PostgreSQL (生产环境)

```env
# PostgreSQL 配置
DATABASE_URL=postgresql://user:password@localhost:5432/pangu
```

**初始化 PostgreSQL**:
```sql
-- 创建数据库
CREATE DATABASE pangu;

-- 创建用户
CREATE USER pangu_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE pangu TO pangu_user;

-- 切换到数据库
\c pangu

-- 授予模式权限
GRANT ALL ON SCHEMA public TO pangu_user;
```

### 4.3 数据备份

```bash
# SQLite 备份
sqlite3 knowledge/unified_novel.db ".backup backup_$(date +%Y%m%d).db"

# PostgreSQL 备份
pg_dump -U pangu_user -h localhost pangu > backup_$(date +%Y%m%d).sql
```

---

## 5. Redis 配置 (可选)

### 5.1 安装 Redis

```bash
# Ubuntu/Debian
sudo apt-get install -y redis-server

# macOS
brew install redis
```

### 5.2 Redis 配置

```env
REDIS_URL=redis://localhost:6379/0
```

### 5.3 Redis 用途

| 用途 | 说明 |
|------|------|
| LLM响应缓存 | 缓存相似请求的LLM响应 |
| 会话状态 | 存储用户会话数据 |
| 任务队列 | 批量生成任务队列 |
| 限流计数 | API调用频率限制 |

---

## 6. 监控配置

### 6.1 日志配置

```yaml
# config/logging.yaml
version: 1
disable_existing_loggers: false

formatters:
  standard:
    format: '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'
  json:
    class: pythonjsonlogger.jsonlogger.JsonFormatter
    format: '%(asctime)s %(levelname)s %(name)s %(message)s'

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: standard
    stream: ext://sys.stdout

  file:
    class: logging.handlers.RotatingFileHandler
    level: INFO
    formatter: json
    filename: logs/app.log
    maxBytes: 104857600  # 100MB
    backupCount: 10

  error_file:
    class: logging.handlers.RotatingFileHandler
    level: ERROR
    formatter: json
    filename: logs/error.log
    maxBytes: 10485760  # 10MB
    backupCount: 5

loggers:
  backend:
    level: DEBUG
    handlers: [console, file, error_file]
    propagate: false

root:
  level: INFO
  handlers: [console, file]
```

### 6.2 健康检查

```bash
# HTTP 健康检查
curl -f http://localhost:5001/api/v7/health

# 系统状态检查
curl http://localhost:5001/api/v1/system/stats
```

### 6.3 告警配置

```yaml
# config/alerts.yaml
alerts:
  - name: high_error_rate
    condition: "error_rate > 0.05"
    channels: [wechat, email]
    threshold: 5

  - name: high_latency
    condition: "p99_latency > 30"
    channels: [wechat]
    threshold: 10

  - name: disk_full
    condition: "disk_usage > 0.85"
    channels: [wechat, sms]
    threshold: 1
```

---

## 7. 安全配置

### 7.1 API 认证 (预留)

```python
# backend/middleware/auth.py
from functools import wraps
from flask import request, jsonify

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not validate_token(token):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/api/v1/projects', methods=['POST'])
@require_auth
def create_project():
    ...
```

### 7.2 请求限流

```python
# backend/middleware/rate_limit.py
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="redis://localhost:6379/0"
)

@app.route('/api/v1/chapters/generate', methods=['POST'])
@limiter.limit("10 per hour")
def generate_chapter():
    ...
```

### 7.3 CORS 配置

```python
# backend/app_v7.py
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": ["https://your-frontend.com"],
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})
```

---

## 8. 性能优化

### 8.1 Gunicorn 配置

```bash
# /app/gunicorn.conf.py
import multiprocessing

bind = "0.0.0.0:5001"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gevent"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 300
keepalive = 5

# 日志
accesslog = "-"
errorlog = "-"
loglevel = "info"
```

### 8.2 数据库优化

```sql
-- 创建索引
CREATE INDEX IF NOT EXISTS idx_chapters_project_num
ON chapters(project_id, chapter_num);

CREATE INDEX IF NOT EXISTS idx_workshop_tasks_status
ON workshop_tasks(status);

-- 定期清理
DELETE FROM llm_calls WHERE created_at < datetime('now', '-30 days');
VACUUM;
```

### 8.3 缓存策略

```python
# backend/utils/cache.py
from functools import lru_cache
import redis
import json

redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))

def cache_result(key, ttl=3600):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 尝试从缓存获取
            cached = redis_client.get(key)
            if cached:
                return json.loads(cached)

            # 执行函数
            result = func(*args, **kwargs)

            # 存入缓存
            redis_client.setex(key, ttl, json.dumps(result))
            return result
        return wrapper
    return decorator
```

---

## 9. 故障排查

### 9.1 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| API 返回 500 | 数据库文件损坏 | 运行 `sqlite3 db.sqlite "PRAGMA integrity_check;"` |
| LLM 调用超时 | 网络问题或API限流 | 检查 API Key 额度，增大超时时间 |
| 内存占用过高 | RAG索引未释放 | 重启服务，限制并发数 |
| 端口被占用 | 其他进程占用 5001 | `lsof -i:5001` 查找并杀掉进程 |

### 9.2 日志分析

```bash
# 查看错误日志
tail -f logs/error.log | grep ERROR

# 分析 LLM 调用失败
grep "LLM" logs/app.log | grep ERROR

# 查看 API 响应时间
grep "API" logs/access.log
```

### 9.3 性能分析

```python
# 添加性能分析端点
@app.route('/api/v1/debug/profile')
def profile():
    import cProfile
    import pstats
    import io

    pr = cProfile.Profile()
    pr.enable()

    # 执行目标操作
    from backend.app_v7 import generate_chapter
    generate_chapter(...)

    pr.disable()

    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats(20)
    return s.getvalue()
```

---

## 10. 升级指南

### 10.1 版本升级步骤

```bash
# 1. 备份数据
cp -r knowledge knowledge.backup.$(date +%Y%m%d)

# 2. 拉取新代码
git pull origin main

# 3. 安装新依赖
pip install -r requirements.txt

# 4. 运行数据库迁移
python scripts/migrate.py --from v1.0 --to v1.1

# 5. 重启服务
sudo systemctl restart pangu
```

### 10.2 回滚步骤

```bash
# 1. 停止服务
sudo systemctl stop pangu

# 2. 恢复数据
rm -rf knowledge
mv knowledge.backup.20260610 knowledge

# 3. 回滚代码
git reset --hard HEAD~1

# 4. 重启服务
sudo systemctl start pangu
```

---

## 11. 变更历史

| 日期 | 版本 | 变更内容 | 作者 |
|------|------|---------|------|
| 2026-06-10 | v1.0 | 初稿创建 | Claude |
