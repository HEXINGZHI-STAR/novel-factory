# 盘古AI系统 - 架构设计规范

> 版本: v1.0
> 更新日期: 2026-06-10
> 状态: 草稿

---

## 1. 设计原则

### 1.1 核心原则

| 原则 | 描述 | 适用场景 |
|------|------|---------|
| **模块化** | 每个模块有明确边界，通过接口通信 | 所有新功能 |
| **可替换** | 核心逻辑不依赖具体实现，可插拔 | LLM调用、RAG引擎 |
| **可观测** | 所有关键操作都有日志和追踪 | 生产环境 |
| **容错性** | 单点故障不影响整体 | API调用、文件IO |
| **YAGNI** | 不要过度设计，只实现当前需要 | 新功能开发 |

### 1.2 禁止事项

- ❌ 禁止在核心模块中硬编码平台/模式名称
- ❌ 禁止跨层直接调用（UI→Data必须经Service）
- ❌ 禁止在Prompt中硬编码"AI味"禁用词表
- ❌ 禁止生成的文件名包含特殊字符

---

## 2. 分层架构

### 2.1 四层架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      用户交互层 (UI Layer)                        │
│  职责: 命令行交互、Web界面、API响应                              │
│  技术: CLI / Flask-REST / (未来)React                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      服务编排层 (Service Layer)                   │
│  职责: 业务流程编排、多步骤协调、事务管理                         │
│  技术: WorkflowEngine / SchedulerV7                             │
│  依赖: Core Layer                                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       核心引擎层 (Core Layer)                      │
│  职责: 纯业务逻辑，不依赖上层或下层                              │
│  技术: RAG引擎 / 质检引擎 / 风格引擎 / 提示词引擎               │
│  依赖: Data Layer                                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        数据层 (Data Layer)                        │
│  职责: 数据持久化、检索、缓存                                    │
│  技术: SQLite / JSON文件 / 向量索引                             │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 依赖规则

```
UI Layer ──────► Service Layer ──────► Core Layer ──────► Data Layer
     │                │                    │                   │
     ▼                ▼                    ▼                   ▼
  CLI/Web          Workflow             RAG/QC             DB/File
  REST API         Scheduler            Prompt             Vector
```

**逆向依赖禁止**：Core不能依赖Service，Data不能依赖Core。

---

## 3. 模块边界

### 3.1 核心模块清单

| 模块 | 路径 | 职责 | 对外接口 |
|------|------|------|---------|
| `app_v7` | `backend/app_v7.py` | API服务入口、五车间调度 | Flask routes |
| `pangu_optimized` | `pangu_optimized.py` | CLI主程序 | 命令行菜单 |
| `workflow_engine` | `backend/workflow_engine.py` | 工作流编排 | `run_workflow_pipeline()` |
| `rag_engine` | `backend/rag_engine.py` | 向量检索、RAG生成 | `get_rag()`, `PanguRAG.search()` |
| `db_manager` | `knowledge/db_manager.py` | 统一数据库管理 | `UnifiedDBManager` |
| `prompt_builder` | `core/prompt_builder.py` | 智能提示词构建 | `build_smart_prompt()` |
| `quality_checker` | `core/quality_checker.py` | 37项质检 | `check_quality()` |
| `style_manager` | `core/style_manager.py` | 风格配置管理 | `StyleManager` |

### 3.2 模块接口规范

**每个模块必须提供**：
1. `__init__.py` - 模块初始化
2. `get_*()` 或 `load_*()` - 工厂函数获取实例
3. 类型注解 - 所有函数参数和返回值
4. 异常类 - `ModuleNameError` 基类

**示例**：
```python
# rag_engine.py
class RAGEngineError(Exception):
    """RAG引擎基础异常"""
    pass

class IndexNotFoundError(RAGEngineError):
    """索引文件不存在"""
    pass

class PanguRAG:
    def __init__(self, project_name: str = None):
        self.project_name = project_name

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """检索相关文档"""
        ...

def get_rag(project_name: str = None) -> PanguRAG:
    """获取RAG引擎单例"""
    ...
```

---

## 4. 数据流设计

### 4.1 章节生成流程

```
用户输入
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│ 1. 输入验证                                                       │
│    - chapter_task: str (必填)                                     │
│    - mode: str (默认 general)                                    │
│    - platform: str (默认 qimao)                                  │
└──────────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│ 2. 状态加载                                                       │
│    - 从 state.json 读取伏笔、角色、Lorebook                       │
│    - 从数据库读取项目配置                                          │
└──────────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│ 3. Prompt构建 (10层注入)                                          │
│    Layer 1: 通用质量规则                                          │
│    Layer 2: 平台专属约束                                          │
│    Layer 3: 模式深度规则                                          │
│    Layer 4: 风格指纹指引                                          │
│    Layer 5: 情绪锚点                                             │
│    Layer 6: 伏笔追踪提醒                                          │
│    Layer 7: Lorebook强制注入                                      │
│    Layer 8: De-AI化约束                                          │
│    Layer 9: Beat Sheet节拍约束                                    │
│    Layer10: 上下文内容                                            │
└──────────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│ 4. LLM调用 (含重试、熔断、Fallback)                               │
│    - 调用策略: LiteLLM / 手动HTTP                                 │
│    - 熔断条件: 连续失败5次/30秒                                    │
│    - Fallback: deepseek → gpt-4o-mini → qwen                    │
└──────────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│ 5. 质量闭环                                                       │
│    - 快速评分: <65分 → 自动改写                                   │
│    - 改写轮次: 最多2次                                            │
│    - 改写策略: 句长扩展 + 禁用词替换 + 对话嵌入                    │
└──────────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│ 6. 状态更新                                                       │
│    - 伏笔提取 → 写入 state.json                                  │
│    - 角色识别 → 写入 state.json                                  │
│    - 进度更新 → 写入 state.json                                  │
│    - 日志记录 → 写入 unified_novel.db                            │
└──────────────────────────────────────────────────────────────────┘
    │
    ▼
输出文件
```

### 4.2 RAG检索流程

```
Query: "第5章 主角升级"
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│ 1. Query向量化                                                     │
│    - 加载 sentence-transformers 模型                              │
│    - 生成 768维 embedding                                         │
└──────────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│ 2. 向量检索                                                       │
│    - HNSW 近似最近邻检索                                          │
│    - top_k=5 (可配置)                                             │
│    - 召回率: ~95%                                                 │
└──────────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│ 3. 结果过滤                                                       │
│    - 按车间类型过滤 (w1/w2/w3/w4)                                │
│    - 按模式过滤 (healing_life / urban_power / ...)               │
│    - 按平台过滤 (qimao / fanqie / qidian)                        │
└──────────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│ 4. 结果组装                                                       │
│    - 格式化为 prompt 片段                                         │
│    - 添加来源标注                                                  │
│    - 控制总长度 ≤ 2000字                                          │
└──────────────────────────────────────────────────────────────────┘
    │
    ▼
注入Prompt
```

---

## 5. 错误处理

### 5.1 异常层次

```
Exception (Python内置)
    │
    ├── PanguBaseError (系统基础异常)
    │   ├── ConfigError (配置错误)
    │   ├── DataNotFoundError (数据未找到)
    │   └── PermissionError (权限错误)
    │
    ├── LLMError (LLM调用异常)
    │   ├── LLMTimeoutError (超时)
    │   ├── LLMRateLimitError (限流)
    │   ├── LLMAPIError (API错误)
    │   └── LLMModelUnavailableError (模型不可用)
    │
    ├── RAGError (RAG引擎异常)
    │   ├── IndexNotFoundError (索引不存在)
    │   └── EmbeddingModelError (嵌入模型错误)
    │
    └── ValidationError (验证异常)
        ├── InputValidationError (输入验证失败)
        └── OutputValidationError (输出验证失败)
```

### 5.2 错误响应格式

```json
{
  "success": false,
  "error": {
    "code": "LLM_TIMEOUT",
    "message": "LLM调用超时",
    "detail": "deepseek/deepseek-chat 超时 (180s)",
    "recoverable": true,
    "suggestion": "建议稍后重试，或切换到备用模型"
  },
  "request_id": "req_abc123",
  "timestamp": "2026-06-10T12:00:00Z"
}
```

### 5.3 重试策略

| 错误类型 | 重试次数 | 退避策略 | 备注 |
|---------|---------|---------|------|
| Timeout | 3 | 指数退避 (2^n s) | 最长等待 8s |
| RateLimit | 3 | 固定等待 5s | 需人工介入 |
| APIError | 2 | 指数退避 | 4xx不重试 |
| NetworkError | 3 | 指数退避 | 最多等待 16s |

---

## 6. 日志规范

### 6.1 日志级别

| 级别 | 用途 | 示例 |
|------|------|------|
| DEBUG | 开发调试 | 函数入口/出口、变量值 |
| INFO | 正常运行 | API调用成功、文件保存 |
| WARNING | 异常但不阻断 | 缺少可选配置、使用Fallback |
| ERROR | 错误但可恢复 | LLM调用失败、单次写入失败 |
| CRITICAL | 系统不可用 | 数据库连接失败、配置文件丢失 |

### 6.2 日志格式

```python
# 标准格式
[2026-06-10 12:00:00] [INFO] [api.write] 写章节成功: 项目=测试项目, 章=5, 字数=2100

# 错误格式
[2026-06-10 12:00:00] [ERROR] [llm.call] LLM调用失败: model=deepseek, error=Timeout
```

### 6.3 日志存储

```
logs/
├── app.log           # 应用日志 (保留30天)
├── llm_calls.jsonl   # LLM调用记录 (JSONL格式)
├── errors.log        # 错误日志 (保留90天)
└── audit.log         # 操作审计 (保留1年)
```

---

## 7. 配置管理

### 7.1 配置层次

```
环境变量 (.env)
    │
    ▼
命令行参数 (argparse)
    │
    ▼
项目配置 (projects/{name}/config.json)
    │
    ▼
系统默认 (config/default.yaml)
```

### 7.2 关键配置项

```yaml
# config/default.yaml
llm:
  default_model: "deepseek/deepseek-chat"
  timeout: 180
  max_retries: 3
  fallback_models:
    - "openai/gpt-4o-mini"
    - "qwen/qwen-turbo"

rag:
  embedding_model: "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
  top_k: 5
  max_context_length: 2000

quality:
  score_threshold: 65
  max_rewrite_passes: 2

database:
  path: "knowledge/unified_novel.db"
  backup_interval: 86400  # 24小时

logging:
  level: "INFO"
  retention_days: 30
```

---

## 8. 安全性

### 8.1 API Key管理

- ❌ 禁止硬编码在任何代码文件中
- ✅ 必须存储在 `.env` 文件
- ✅ 通过环境变量读取
- ✅ 日志中脱敏显示 (`sk-****abcd`)

### 8.2 输入验证

```python
# 所有用户输入必须验证
class InputValidator:
    @staticmethod
    def validate_chapter_num(n: int) -> int:
        if n < 1:
            raise ValidationError("章节号必须 ≥ 1")
        if n > 10000:
            raise ValidationError("章节号必须 ≤ 10000")
        return n

    @staticmethod
    def validate_word_count(n: int) -> int:
        if n < 100:
            raise ValidationError("字数必须 ≥ 100")
        if n > 50000:
            raise ValidationError("字数必须 ≤ 50000")
        return n
```

### 8.3 文件操作安全

- 所有文件路径必须标准化 (`pathlib.Path`)
- 禁止路径穿越 (`../`)
- 禁止写入系统目录
- 敏感文件 (`state.json`) 禁止提交到Git

---

## 9. 性能优化

### 9.1 缓存策略

| 数据类型 | 缓存方案 | TTL | 失效条件 |
|---------|---------|-----|---------|
| 模式配置 | 内存缓存 | 进程生命周期 | 重启服务 |
| 平台配置 | 内存缓存 | 进程生命周期 | 重启服务 |
| RAG索引 | 内存映射 | 进程生命周期 | 重启服务 |
| Prompt模板 | 内存缓存 | 进程生命周期 | 重启服务 |
| 用户查询结果 | LRU缓存 | 5分钟 | 时间过期 |

### 9.2 异步处理

```python
# 适用于：批量生成、批量分析
import asyncio

async def batch_write(chapters: list[int]):
    tasks = [write_chapter(ch) for ch in chapters]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

### 9.3 数据库优化

```sql
-- 常用查询必须建立索引
CREATE INDEX IF NOT EXISTS idx_chapters_project
ON chapters(project_id, chapter_num);

CREATE INDEX IF NOT EXISTS idx_tasks_status
ON workshop_tasks(project_name, status);

-- 定期清理
DELETE FROM llm_calls
WHERE created_at < datetime('now', '-30 days');
```

---

## 10. 测试策略

### 10.1 测试分层

| 层级 | 测试内容 | 工具 | 覆盖率目标 |
|------|---------|------|-----------|
| 单元测试 | 纯函数、工具类 | pytest | 80% |
| 集成测试 | 模块间接口、数据库 | pytest + fixtures | 60% |
| 端到端测试 | 完整流程、CLI命令 | subprocess + pytest | 40% |

### 10.2 测试示例

```python
# tests/test_prompt_builder.py
def test_build_smart_prompt_injects_mode_rules():
    state = {"project_info": {"genre": "healing_life_v2", "platform": "qimao"}}
    system_msg, user_msg = build_smart_prompt(state, "写一章日常", 5)

    assert "触觉" in system_msg
    assert "半沢式" in system_msg
    assert "qimao" in system_msg

def test_build_smart_prompt_injects_lorebook():
    state = {
        "project_info": {"genre": "general"},
        "lorebook": {
            "李墨寒": {"description": "杀手", "triggers": ["李墨寒"]}
        }
    }
    system_msg, _ = build_smart_prompt(state, "李墨寒出场", 1)
    assert "杀手" in system_msg
```

---

## 11. 部署架构

### 11.1 开发环境

```
本地开发:
├── Python 3.10+
├── SQLite (bundled)
├── .env (本地API Key)
└── VS Code (推荐IDE)
```

### 11.2 生产环境

```
生产部署:
├── Python 3.10+ (Docker容器)
├── PostgreSQL (替代SQLite)
├── Redis (缓存 + 任务队列)
├── Nginx (反向代理)
└── Gunicorn (WSGI服务器)
```

### 11.3 容器化

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5001", "backend.app_v7:app"]
```

---

## 12. 监控告警

### 12.1 关键指标

| 指标 | 告警阈值 | 采集方式 |
|------|---------|---------|
| API响应时间 P99 | > 30s | 日志分析 |
| LLM调用失败率 | > 5% | 日志统计 |
| 数据库连接数 | > 80% | DB监控 |
| 磁盘使用率 | > 85% | 系统监控 |

### 12.2 告警渠道

- ERROR级别 → 企业微信机器人
- CRITICAL级别 → 短信 + 电话

---

## 13. 变更历史

| 日期 | 版本 | 变更内容 | 作者 |
|------|------|---------|------|
| 2026-06-10 | v1.0 | 初稿创建 | Claude |
