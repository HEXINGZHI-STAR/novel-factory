# 盘古AI系统 - API接口规范

> 版本: v1.0
> 更新日期: 2026-06-10
> 状态: 草稿

---

## 1. 概述

### 1.1 API设计原则

| 原则 | 描述 |
|------|------|
| RESTful | 使用标准HTTP方法 |
| JSON格式 | 请求和响应均为JSON |
| 幂等性 | GET/PUT/DELETE幂等 |
| 版本化 | URL包含版本号 `/api/v1/` |
| 错误规范化 | 统一错误响应格式 |

### 1.2 基础信息

- **Base URL**: `http://127.0.0.1:5001/api/v7`
- **Content-Type**: `application/json`
- **字符编码**: UTF-8
- **认证方式**: Bearer Token (预留)

---

## 2. 通用规范

### 2.1 请求格式

```http
POST /api/v1/projects HTTP/1.1
Host: 127.0.0.1:5001
Content-Type: application/json
Authorization: Bearer <token>

{
  "title": "我的小说",
  "genre": "healing_life_v2",
  "platform": "qimao"
}
```

### 2.2 响应格式

**成功响应**:
```json
{
  "success": true,
  "data": {
    "id": "proj_abc123",
    "title": "我的小说",
    "genre": "healing_life_v2",
    "platform": "qimao",
    "created_at": "2026-06-10T12:00:00Z"
  },
  "request_id": "req_xyz789"
}
```

**错误响应**:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "章节号必须大于0",
    "field": "chapter_num",
    "detail": "chapter_num=0 不在有效范围内 (1-10000)"
  },
  "request_id": "req_xyz789"
}
```

### 2.3 错误码

| 错误码 | HTTP状态码 | 说明 |
|--------|-----------|------|
| `SUCCESS` | 200 | 成功 |
| `CREATED` | 201 | 资源创建成功 |
| `VALIDATION_ERROR` | 400 | 输入验证失败 |
| `UNAUTHORIZED` | 401 | 未认证 |
| `FORBIDDEN` | 403 | 无权限 |
| `NOT_FOUND` | 404 | 资源不存在 |
| `CONFLICT` | 409 | 资源冲突 |
| `LLM_ERROR` | 422 | LLM调用失败 |
| `RATE_LIMIT` | 429 | 请求过于频繁 |
| `INTERNAL_ERROR` | 500 | 服务器内部错误 |

---

## 3. 项目管理 API

### 3.1 创建项目

**端点**: `POST /api/v1/projects`

**请求体**:
```json
{
  "title": "我的小说",
  "genre": "healing_life_v2",
  "platform": "qimao",
  "target_chapters": 200,
  "target_words": 400000
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 是 | 书名 |
| genre | string | 是 | 创作模式 |
| platform | string | 是 | 目标平台 |
| target_chapters | integer | 否 | 目标章节数 (默认200) |
| target_words | integer | 否 | 目标字数 (默认400000) |

**响应** (201):
```json
{
  "success": true,
  "data": {
    "id": "proj_abc123",
    "title": "我的小说",
    "genre": "healing_life_v2",
    "platform": "qimao",
    "target_chapters": 200,
    "target_words": 400000,
    "current_chapter": 0,
    "total_words": 0,
    "created_at": "2026-06-10T12:00:00Z"
  }
}
```

---

### 3.2 获取项目列表

**端点**: `GET /api/v1/projects`

**查询参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| page | integer | 页码 (默认1) |
| page_size | integer | 每页数量 (默认20) |
| sort | string | 排序字段 (默认created_at) |
| order | string | 排序方向 (asc/desc, 默认desc) |

**响应** (200):
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "proj_abc123",
        "title": "我的小说",
        "genre": "healing_life_v2",
        "platform": "qimao",
        "progress": {"current": 5, "total": 200, "percentage": 2.5}
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 1,
      "total_pages": 1
    }
  }
}
```

---

### 3.3 获取项目详情

**端点**: `GET /api/v1/projects/{project_id}`

**路径参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| project_id | string | 项目ID |

**响应** (200):
```json
{
  "success": true,
  "data": {
    "id": "proj_abc123",
    "title": "我的小说",
    "genre": "healing_life_v2",
    "platform": "qimao",
    "target_chapters": 200,
    "target_words": 400000,
    "current_chapter": 10,
    "total_words": 21000,
    "state": {
      "foreshadowing": {"active": 3, "resolved": 1},
      "characters": {"protagonist": "林柚", "count": 5},
      "lorebook": {"total": 8, "filled": 3}
    },
    "created_at": "2026-06-10T12:00:00Z",
    "updated_at": "2026-06-10T15:30:00Z"
  }
}
```

---

### 3.4 更新项目

**端点**: `PUT /api/v1/projects/{project_id}`

**请求体**:
```json
{
  "title": "新书名",
  "genre": "urban_power"
}
```

**响应** (200):
```json
{
  "success": true,
  "data": {
    "id": "proj_abc123",
    "title": "新书名",
    "genre": "urban_power",
    "updated_at": "2026-06-10T16:00:00Z"
  }
}
```

---

### 3.5 删除项目

**端点**: `DELETE /api/v1/projects/{project_id}`

**响应** (200):
```json
{
  "success": true,
  "message": "项目已删除"
}
```

---

## 4. 章节管理 API

### 4.1 生成章节 (五车间流水线)

**端点**: `POST /api/v1/projects/{project_id}/chapters`

**请求体**:
```json
{
  "chapter_num": 5,
  "chapter_task": "主角在便利店遇到神秘老人，获得金手指",
  "collaborative_mode": "api_review",
  "temperature": 0.6
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| chapter_num | integer | 是 | 章节号 |
| chapter_task | string | 是 | 章节任务描述 |
| collaborative_mode | string | 否 | 协作模式 (默认api_review) |
| temperature | float | 否 | 温度参数 (0.1-1.0) |

**collaborative_mode 选项**:
| 模式 | 说明 |
|------|------|
| api_auto | API自动生成 |
| api_review | API生成 + 人工审校 |
| human_review | 人工生成 + API审校 |
| human | 纯人工写作 |

**响应** (200):
```json
{
  "success": true,
  "data": {
    "chapter_num": 5,
    "word_count": 2150,
    "content": "正文内容...",
    "quality_score": 78.5,
    "workshop_outputs": {
      "w0_anchor": "...",
      "w1_hot_storage": "...",
      "w2_draft": "...",
      "w3_qc_report": "...",
      "w4_final": "..."
    },
    "state_updated": {
      "foreshadowing": {"added": 2, "resolved": 0},
      "characters": {"added": 1}
    },
    "generated_at": "2026-06-10T12:30:00Z"
  }
}
```

---

### 4.2 获取章节内容

**端点**: `GET /api/v1/projects/{project_id}/chapters/{chapter_num}`

**响应** (200):
```json
{
  "success": true,
  "data": {
    "chapter_num": 5,
    "title": "神秘的便利店",
    "content": "正文内容...",
    "word_count": 2150,
    "task": "主角在便利店遇到神秘老人，获得金手指",
    "quality_score": 78.5,
    "created_at": "2026-06-10T12:30:00Z"
  }
}
```

---

### 4.3 获取章节列表

**端点**: `GET /api/v1/projects/{project_id}/chapters`

**查询参数**:
| 参数 | 类型 | 说明 |
|------|------|------|
| page | integer | 页码 |
| page_size | integer | 每页数量 |
| min_score | float | 最低质量分数 |

**响应** (200):
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "chapter_num": 5,
        "title": "神秘的便利店",
        "word_count": 2150,
        "quality_score": 78.5,
        "created_at": "2026-06-10T12:30:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 10
    }
  }
}
```

---

### 4.4 批量生成章节

**端点**: `POST /api/v1/projects/{project_id}/chapters/batch`

**请求体**:
```json
{
  "start_chapter": 6,
  "count": 5,
  "chapter_tasks": {
    "6": "主角测试金手指能力",
    "7": "主角遇到第一个对手",
    "8": "主角与对手交锋",
    "9": "主角险胜",
    "10": "主角获得奖励"
  }
}
```

**响应** (200):
```json
{
  "success": true,
  "data": {
    "total": 5,
    "succeeded": 4,
    "failed": 1,
    "chapters": [
      {"chapter_num": 6, "word_count": 2100, "success": true},
      {"chapter_num": 7, "word_count": 2150, "success": true},
      {"chapter_num": 8, "word_count": 2200, "success": true},
      {"chapter_num": 9, "word_count": 0, "success": false, "error": "LLM_TIMEOUT"},
      {"chapter_num": 10, "word_count": 2050, "success": true}
    ],
    "failed_indexes": [3]
  }
}
```

---

## 5. 质量检测 API

### 5.1 文本评分

**端点**: `POST /api/v7/observability/score`

**请求体**:
```json
{
  "text": "要检测的文本内容...",
  "mode": "healing_life_v2"
}
```

**响应** (200):
```json
{
  "success": true,
  "data": {
    "total_score": 78.5,
    "metrics": {
      "dialogue_ratio": {"score": 85.0, "weight": 15},
      "sentence_length": {"score": 72.0, "weight": 15},
      "ai_indicator": {"score": 80.0, "weight": 15},
      "hook_strength": {"score": 75.0, "weight": 15},
      "emotion_release": {"score": 90.0, "weight": 15},
      "sensory_detail": {"score": 70.0, "weight": 10},
      "character_consistency": {"score": 88.0, "weight": 10},
      "plot_coherence": {"score": 82.0, "weight": 5}
    },
    "suggestions": [
      "建议增加触觉描写细节",
      "部分对话可以更口语化"
    ]
  }
}
```

---

### 5.2 情绪曲线检测

**端点**: `POST /api/v7/observability/curve`

**请求体**:
```json
{
  "text": "要检测的文本内容...",
  "target": "healing",
  "quick": false
}
```

**响应** (200):
```json
{
  "success": true,
  "data": {
    "curve_valid": true,
    "curve_type": "前3后1",
    "score": 85,
    "release_points": [
      {"position": 0.25, "type": "微澜"},
      {"position": 0.75, "type": "释放"}
    ],
    "recommendation": "情绪曲线符合治愈系标准"
  }
}
```

---

### 5.3 风格一致性检测

**端点**: `POST /api/v7/observability/style`

**请求体**:
```json
{
  "text": "要检测的文本内容...",
  "target": "healing_life_v2",
  "mode": "full"
}
```

**响应** (200):
```json
{
  "success": true,
  "data": {
    "style_match_score": 82.5,
    "fingerprint": {
      "avg_sentence_length": 28.5,
      "long_sentence_ratio": 0.42,
      "dialogue_ratio": 0.45,
      "sensory_distribution": {"visual": 40, "auditory": 30, "tactile": 30}
    },
    "deviations": [
      "句长偏长，建议缩短部分句子"
    ]
  }
}
```

---

## 6. RAG 检索 API

### 6.1 知识检索

**端点**: `POST /api/v7/rag/search`

**请求体**:
```json
{
  "query": "第5章如何写主角升级",
  "top_k": 5,
  "mode": "urban_power",
  "platform": "qimao",
  "project_name": "我的小说"
}
```

**响应** (200):
```json
{
  "success": true,
  "data": {
    "query": "第5章如何写主角升级",
    "count": 5,
    "results": [
      {
        "title": "都市异能升级体系设计",
        "category": "writing_technique",
        "source": "知识库/技法/升级体系.md",
        "score": 0.95,
        "text": "主角升级的关键在于..."
      }
    ]
  }
}
```

---

### 6.2 RAG 统计

**端点**: `GET /api/v7/rag/stats`

**响应** (200):
```json
{
  "success": true,
  "data": {
    "total_documents": 1234,
    "total_vectors": 5678,
    "index_size_mb": 45.6,
    "by_category": {
      "books": 775,
      "techniques": 739,
      "templates": 37
    }
  }
}
```

---

## 7. 伏笔追踪 API

### 7.1 获取伏笔列表

**端点**: `GET /api/v1/projects/{project_id}/foreshadowing`

**响应** (200):
```json
{
  "success": true,
  "data": {
    "active": [
      {
        "id": "f001",
        "planted_chapter": 3,
        "description": "老人留给主角的神秘玉佩",
        "status": "open",
        "age": 2
      }
    ],
    "resolved": [
      {
        "id": "f002",
        "planted_chapter": 1,
        "resolved_chapter": 5,
        "description": "主角能力的来源"
      }
    ]
  }
}
```

---

### 7.2 添加伏笔

**端点**: `POST /api/v1/projects/{project_id}/foreshadowing`

**请求体**:
```json
{
  "chapter_num": 5,
  "description": "主角体内封印的妖兽",
  "status": "open"
}
```

---

### 7.3 更新伏笔状态

**端点**: `PUT /api/v1/projects/{project_id}/foreshadowing/{foreshadow_id}`

**请求体**:
```json
{
  "status": "resolved",
  "resolved_chapter": 10
}
```

---

## 8. 协作 API

### 8.1 生成协作链接

**端点**: `POST /api/v1/projects/{project_id}/collaborate`

**请求体**:
```json
{
  "role": "reviewer",
  "expires_in": 86400
}
```

**响应** (200):
```json
{
  "success": true,
  "data": {
    "invite_code": "ABC123",
    "expires_at": "2026-06-11T12:00:00Z"
  }
}
```

---

## 9. 系统 API

### 9.1 健康检查

**端点**: `GET /api/v7/health`

**响应** (200):
```json
{
  "success": true,
  "data": {
    "status": "ok",
    "version": "7.5",
    "uptime_seconds": 3600,
    "services": {
      "database": "connected",
      "llm": "available",
      "rag": "available"
    }
  }
}
```

---

### 9.2 获取系统统计

**端点**: `GET /api/v1/system/stats`

**响应** (200):
```json
{
  "success": true,
  "data": {
    "projects_count": 5,
    "chapters_count": 127,
    "total_words": 267000,
    "avg_quality_score": 75.2,
    "llm_calls_today": 45,
    "api_errors_today": 2
  }
}
```

---

## 10. Webhook

### 10.1 Webhook 配置

**端点**: `POST /api/v1/webhooks`

**请求体**:
```json
{
  "url": "https://your-server.com/webhook",
  "events": ["chapter.generated", "chapter.failed", "quality.low"],
  "secret": "your-secret-key"
}
```

### 10.2 Webhook 事件

| 事件 | 触发时机 |
|------|---------|
| chapter.generated | 章节生成成功 |
| chapter.failed | 章节生成失败 |
| quality.low | 质量分数低于阈值 |
| project.created | 项目创建 |
| project.deleted | 项目删除 |

---

## 11. 变更历史

| 日期 | 版本 | 变更内容 | 作者 |
|------|------|---------|------|
| 2026-06-10 | v1.0 | 初稿创建 | Claude |
