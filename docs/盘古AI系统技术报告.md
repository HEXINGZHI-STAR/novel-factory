
# 盘古AI写作系统 - 技术架构报告

&gt; 版本：V7.5  
&gt; 生成日期：2026-06-08  
&gt; 作者：盘古AI开发团队

---

## 目录

1. [系统概述](#1-系统概述)
2. [总体架构](#2-总体架构)
3. [核心模块详解](#3-核心模块详解)
4. [运行流程](#4-运行流程)
5. [技术栈与开源集成](#5-技术栈与开源集成)
6. [文件结构](#6-文件结构)
7. [配置指南](#7-配置指南)

---

## 1. 系统概述

### 1.1 系统定位

盘古AI是一套**基于叙事动力学理论驱动的智能写作辅助系统**，专为网络文学创作设计。它不是简单的文本生成工具，而是一套完整的创作流水线，融合了：

- 叙事理论（时距系统、聚焦模式、矛盾螺旋）
- RAG知识检索（FAISS向量检索）
- 多模型路由（LiteLLM统一接口）
- 流水线调度（四车间+Fusion引擎）
- 可观测性分析（情绪曲线、风格指纹）

### 1.2 核心特性

| 特性 | 描述 |
|------|------|
| **12种创作模式** | 通用、治愈系、都市异能、规则怪谈、历史考据流、无CP大女主等 |
| **四大平台适配** | 番茄、起点、七猫、晋江差异化写作配置 |
| **五车间流水线** | 锚点设定→设定预处理→正文初稿→逻辑质检→文笔精修 |
| **三库系统** | 人物图谱、事件图谱、专属素材库 |
| **RAG知识库** | 775本网文参考库，支持语义检索 |
| **多模型支持** | OpenAI、DeepSeek、Claude、通义千问、Ollama等100+模型 |

### 1.3 版本演进

- **V6.0**：基础框架搭建，Flask API，JSON知识库
- **V7.0**：四车间调度系统，Fusion引擎
- **V7.5**：HNSW索引优化，LiteLLM集成，情绪工程模块

---

## 2. 总体架构

### 2.1 分层架构图

```
┌───────────────────────────────────────────────────────────────────────┐
│                          用户交互层（CLI/API）                          │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐              │
│  │  pangu.py     │  │ pangu_plus.py │  │ generate_*.py │              │
│  │ (精简CLI)     │  │ (增强CLI)     │  │ (专用脚本)    │              │
│  └───────────────┘  └───────────────┘  └───────────────┘              │
└───────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│                         服务调度层（Backend）                           │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                  Flask API Server (app_v7.py)                    │  │
│  │  ┌───────────────────────────────────────────────────────────┐  │  │
│  │  │               五车间流水线调度器                            │  │  │
│  │  │  W0(锚点) → W1(设定) → W2(初稿) → W3(质检) → W4(精修)      │  │  │
│  │  └───────────────────────────────────────────────────────────┘  │  │
│  │  ┌───────────────────────────────────────────────────────────┐  │  │
│  │  │               Fusion 融合引擎                               │  │  │
│  │  │  多版本择优、上下文保持、风格一致性校验                      │  │  │
│  │  └───────────────────────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│                          引擎层（Core Engines）                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐    │
│  │  RAG引擎     │  │  LiteLLM     │  │  可观测性分析引擎         │    │
│  │ (rag_engine) │  │ (多模型路由) │  │ (observability.py)       │    │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐    │
│  │  章节分析器  │  │  提示词生成器 │  │  数据库管理器             │    │
│  │ (chapter_   │  │ (reference_  │  │ (db_manager.py)          │    │
│  │  analyzer)   │  │  prompt.py)  │  │                          │    │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘    │
└───────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│                           数据层（Data Layer）                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐    │
│  │ SQLite数据库     │  │ System Prompts   │  │ 创作模式配置      │    │
│  │ novel_reference  │  │ (workshops/)     │  │ (modes/)          │    │
│  │ .db              │  │                  │  │                  │    │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘    │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐    │
│  │ 平台写作配置     │  │ 项目状态文件     │  │ FAISS索引缓存     │    │
│  │ (platform_      │  │ (state.json)     │  │ (.rag_cache/)    │    │
│  │ writing_profiles│  │                  │  │                  │    │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘    │
└───────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────┐
│                        外部模型层（LLM Providers）                      │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    │
│  │ OpenAI  │  │DeepSeek │  │ Claude  │  │  通义千问│  │ Ollama  │    │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘    │
└───────────────────────────────────────────────────────────────────────┘
```

### 2.2 核心数据流

```
用户输入（书名/大纲/任务）
    │
    ├─→ 选择创作模式（modes/*.json）
    │
    ├─→ 选择目标平台（platform_writing_profiles.json）
    │
    ├─→ [可选] RAG检索参考小说（novel_reference.db）
    │
    ▼
五车间流水线开始
    │
    ├─ W0: 锚点设定 → 生成核心情绪锚点
    │
    ├─ W1: 设定预处理 → 三库（人物/事件/素材）生成
    │
    ├─ W2: 正文初稿 → 生成章节内容
    │
    ├─ W3: 逻辑质检 → 矛盾检测、一致性校验
    │
    └─ W4: 文笔精修 → 风格打磨、情绪曲线调整
    │
    ▼
Fusion引擎择优输出
    │
    ▼
保存到项目目录（projects/）
```

---

## 3. 核心模块详解

### 3.1 五车间流水线系统

#### 3.1.1 W0 - 情绪锚点车间（Workshop 0: Anchor）

**文件位置**：`workshops/workshop_0_anchor/`

**功能**：
- 定义章节的核心情绪目标
- 设置情绪曲线的关键节点
- 确定爽点/泪点位置

**System Prompt设计思路**：
```
角色：治愈系情绪设计师
任务：为即将创作的章节设计3-5个情绪锚点
输出格式：
- 锚点1：[情绪类型] - [位置] - [触发事件]
- 锚点2：...
```

#### 3.1.2 W1 - 设定预处理车间（Workshop 1: Setup）

**文件位置**：`workshops/workshop_1_setup/`

**功能**：
- 生成/补充人物图谱
- 生成/补充事件图谱
- 生成/补充专属素材库
- 确保设定一致性

**核心输出**：
- 三库JSON文件（characters.json, events.json, materials.json）
- 设定冲突检测报告

#### 3.1.3 W2 - 正文初稿车间（Workshop 2: Draft）

**文件位置**：`workshops/workshop_2_draft/`

**功能**：
- 根据细纲生成初稿
- 应用平台写作配置
- 保持设定一致性
- 控制字数和段落结构

**技术要点**：
- 动态注入RAG检索结果
- 参考库风格匹配
- 时距/聚焦模式应用

#### 3.1.4 W4 - 逻辑质检车间（Workshop 3: QC）

**文件位置**：`workshops/workshop_3_qc/`

**功能**：
- 设定一致性检查
- 逻辑矛盾检测
- 红线规则校验（如女频红线）
- 质量评分

**质检维度**：
| 维度 | 检查内容 |
|------|---------|
| 设定一致性 | 人物名字、能力、设定是否前后矛盾 |
| 时间线 | 事件发生顺序是否合理 |
| 逻辑链 | 因果关系是否成立 |
| 红线规则 | 平台违禁内容检查 |
| 情绪曲线 | 是否符合预设的情绪锚点 |

#### 3.1.5 W5 - 文笔精修车间（Workshop 4: Polish）

**文件位置**：`workshops/workshop_4_polish/`

**功能**：
- 文笔打磨
- 节奏调整
- 风格统一
- 情绪曲线校准

**精修策略**：
- 句子长度优化（平均15-20字）
- 段落长度控制（3-5行/段）
- 对话比例调整
- 钩子强化

### 3.2 Fusion 融合引擎

**核心功能**：
1. **多版本择优**：W2生成3个版本，Fusion选择最优
2. **上下文保持**：确保与前文设定一致
3. **风格一致性**：校验与前文风格匹配度
4. **自动重写**：对低质版本进行二次优化

**择优算法**：
```python
def select_best_version(versions, context, style_profile):
    scores = []
    for v in versions:
        score = (
            coherence_score(v, context) * 0.3 +
            style_match_score(v, style_profile) * 0.3 +
            quality_score(v) * 0.2 +
            hook_score(v) * 0.2
        )
        scores.append(score)
    return versions[argmax(scores)]
```

### 3.3 RAG 知识检索引擎

**文件位置**：`backend/rag_engine.py`

#### 3.3.1 三级检索机制

```
用户查询
    │
    ├─→ [1级] FAISS-HNSW 语义检索（推荐，O(log N)）
    │       速度快，适合大规模数据
    │
    ├─→ [回退1] FAISS-Flat 暴力检索（O(N)）
    │       精度高，速度中等
    │
    └─→ [回退2] TF-IDF 关键词检索
            零依赖，速度快，精度中等
```

#### 3.3.2 HNSW索引优化（V7.5新特性）

**优势**：
- 检索速度提升5-20倍（O(log N) vs O(N)）
- 索引持久化到磁盘，重启秒加载
- 增量更新，仅重编码变化文档
- 相似度阈值过滤，杜绝低质量结果

**配置参数**：
```python
HNSW_PARAMS = {
    'M': 16,           # 每个节点的连接数
    'efConstruction': 40,  # 构建时探索的候选数
    'efSearch': 16     # 检索时探索的候选数
}
```

#### 3.3.3 国内模型适配

自动配置HuggingFace镜像：
```python
# 自动设置国内镜像
if not os.getenv("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
```

支持的模型加载方式：
1. HuggingFace官方
2. 国内镜像（hf-mirror.com）
3. ModelScope
4. 本地路径

### 3.4 LiteLLM 多模型路由

**文件位置**：`backend/app_v7.py` (L19-127)

#### 3.4.1 统一模型接口

LiteLLM支持100+模型供应商，统一调用方式：
```python
from litellm import completion

response = completion(
    model="deepseek/deepseek-chat",
    messages=[{"role": "user", "content": "你好"}],
    api_key="sk-xxx"
)
```

支持的模型格式：
- `openai/gpt-4o`
- `deepseek/deepseek-chat`
- `anthropic/claude-sonnet-4-6`
- `ollama/qwen2.5:14b`
- `dashscope/qwen-turbo`
- `zhipuai/glm-4`

#### 3.4.2 车间级模型配置

每个车间可独立配置模型：
```bash
# 全局默认模型
set LLM_MODEL=deepseek/deepseek-chat

# 特定车间模型
set WORKSHOP_W2_MODEL=anthropic/claude-sonnet  # W2用Claude
set WORKSHOP_W4_MODEL=openai/gpt-4o            # W4用GPT-4o
```

#### 3.4.3 高可用配置

| 特性 | 配置 | 说明 |
|------|------|------|
| **超时** | `LLM_TIMEOUT=180` | 请求超时时间（秒） |
| **重试** | `LLM_RETRIES=3` | 自动重试次数 |
| **指数退避** | `retry_after=2` | 等待2^attempt秒后重试 |
| **熔断** | `LLM_ALLOWED_FAILS=5` | 连续失败5次后熔断 |
| **冷却时间** | `LLM_COOLDOWN_SEC=30` | 熔断后冷却30秒 |
| **速率限制** | `LLM_RPM=0` | 每分钟最大请求数 |

#### 3.4.4 Fallback 机制

```bash
# W2车间 fallback 链
set WORKSHOP_W2_FALLBACK=deepseek/deepseek-chat,openai/gpt-4o-mini
```

当主模型失败时，自动尝试fallback链中的下一个模型。

### 3.5 可观测性分析引擎

**文件位置**：`backend/observability.py`

#### 3.5.1 核心分析器

| 分析器 | 功能 |
|--------|------|
| `detect_emotional_curve()` | 情绪曲线检测 |
| `extract_style_fingerprint()` | 风格指纹提取 |
| `check_style_consistency()` | 风格一致性检查 |
| `score_text()` | 文本质量评分 |
| `HeroArcDetector` | 主角弧光检测 |
| `ShonenStyleDetector` | 少年漫风格检测 |
| `TensionCurveGenerator` | 张力曲线生成 |

#### 3.5.2 情绪工程

**情绪锚点系统**：
- 开篇钩子（Hook）
- 发展铺垫（Build-up）
- 高潮爆发（Climax）
- 收尾爽点（Payoff）

**情绪曲线示例**：
```
情绪强度
    ↑
    │    ╭─────╮
    │   ╱       ╲
    │  ╱         ╲
    │ ╱           ╲
    │╱             ╲
    └────────────────→ 章节进度
     开篇   发展   高潮   收尾
```

### 3.6 数据库管理器

**文件位置**：`knowledge/db_manager.py`

#### 3.6.1 数据库结构

```sql
-- 书籍表
CREATE TABLE books (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT,
    platform TEXT,
    genre TEXT,
    mode TEXT,
    word_count INTEGER,
    chapter_count INTEGER,
    is_reference BOOLEAN,
    notes TEXT,
    created_at DATETIME
);

-- 章节表
CREATE TABLE chapters (
    id INTEGER PRIMARY KEY,
    book_id INTEGER,
    chapter_num INTEGER,
    title TEXT,
    content TEXT,
    word_count INTEGER,
    created_at DATETIME,
    FOREIGN KEY (book_id) REFERENCES books(id)
);

-- 风格标签表
CREATE TABLE style_tags (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT,  -- emotion, rhythm, narrative, platform
    description TEXT,
    color TEXT
);
```

#### 3.6.2 当前数据规模

| 指标 | 数值 |
|------|------|
| 总书籍数 | 775本 |
| 参考书籍 | 146本 |
| 总章节数 | 数千章 |
| 总字数 | 数百万字 |

### 3.7 章节分析器

**文件位置**：`knowledge/chapter_analyzer.py`

#### 3.7.1 分析维度

| 维度 | 分析内容 |
|------|---------|
| **钩子检测** | 识别钩子类型（悬念、疑问、冲突、预告等） |
| **阅读难度** | 平均句子长度、词汇复杂度 |
| **段落结构** | 段落长度分布、对话占比 |
| **节奏分析** | 分段密度分析（感叹号、问号、对话） |
| **开篇钩子** | 开篇300字的钩子强度 |

#### 3.7.2 输出示例

```python
{
    'hooks': [
        {'type': '悬念', 'count': 5},
        {'type': '冲突', 'count': 3}
    ],
    'reading_difficulty': {
        'avg_words_per_sentence': 18,
        'difficulty_level': '适中'
    },
    'paragraphs': [
        {'word_count': 120, 'has_dialogue': True},
        ...
    ],
    'pacing': {
        'segments': [
            {'position': '开篇', 'density': 5, 'pace': '紧张'},
            ...
        ]
    }
}
```

### 3.8 提示词生成器

**文件位置**：`knowledge/reference_prompt.py`

**功能**：
- 从参考小说提取风格指引
- 生成节奏参考
- 提供开篇技巧建议
- 给出具体写作建议

**生成的提示词结构**：
```
## 参考作品风格
- 作品：XXX
- 作者：XXX
- 题材：XXX
- 主要钩子：悬念(5次)、冲突(3次)
- 句子长度：平均18字/句
- 对话占比：45%

## 节奏参考
- 开篇：紧张高潮（密度5）
- 发展：正常发展（密度2）
- 高潮：紧张高潮（密度6）
- 收尾：舒缓铺垫（密度1）

## 写作建议
1. 重点钩子：多使用悬念类型的钩子
2. 节奏把控：按照参考作品的密度变化安排内容
...
```

---

## 4. 运行流程

### 4.1 完整创作流程（CLI模式）

#### 步骤1：启动系统

```bash
cd d:\study\近思录\小说\盘古ai
python pangu_plus.py
```

#### 步骤2：创建新项目

```
[1] 创建新项目
[2] 继续现有项目
[3] 查看参考库
[4] 分析参考小说
[5] 退出

请选择：1

书名：末世：我有一座外星空间站
选择平台：[1]番茄 [2]起点 [3]七猫 [4]晋江 → 3
选择模式：[1]通用 [2]治愈系 [3]都市异能... → 1
目标字数：1000000
目标章节：100
```

**系统自动执行**：
1. 创建项目目录 `projects/末世：我有一座外星空间站/`
2. 创建大纲、正文、设定集子目录
3. 生成 `state.json` 状态文件
4. 生成大纲模板 `大纲/总大纲.txt`

#### 步骤3：编写/完善大纲

编辑 `大纲/总大纲.txt`，填写：
- 一句话核心概念
- 核心卖点
- 人物设定
- 章节规划

#### 步骤4：生成章节

```
选择项目：末世：我有一座外星空间站

[1] 写新章节
[2] 查看进度
[3] 质量检查
[4] 返回

请选择：1

这章要写什么？简要描述：主角苏醒，发现地球毁灭，通过三项考验获得空间站控制权
目标字数：2000
```

**系统自动执行**：

```
[1/5] W0 情绪锚点设定... ✓
[2/5] W1 设定预处理... ✓
[3/5] W2 正文初稿... (生成3个版本) ✓
[4/5] W3 逻辑质检... ✓
[5/5] W4 文笔精修... ✓

Fusion引擎择优... ✓

第1章已生成！
保存到：projects/末世：我有一座外星空间站/正文/第1章_太空的苏醒.txt
```

#### 步骤5：质量检查（可选）

```
选择章节：第1章

[质检报告]
- 设定一致性：✓ 通过
- 逻辑链：✓ 通过
- 情绪曲线：✓ 符合预期
- 风格匹配：✓ 七猫爽文风格
- 总体评分：88/100

[优化建议]
- 开篇钩子可再强化
- 第3段对话比例可提升
```

### 4.2 API调用流程

#### 启动后端服务

```bash
cd backend
python app_v7.py
```

#### 生成章节API

```bash
curl -X POST http://localhost:5000/api/generate/chapter \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "末世：我有一座外星空间站",
    "chapter_num": 1,
    "outline": "主角苏醒，发现地球毁灭...",
    "word_count": 2000,
    "platform": "qimao",
    "mode": "general"
  }'
```

#### 响应示例

```json
{
    "success": true,
    "chapter": {
        "title": "太空的苏醒",
        "content": "林夜是被冻醒的...",
        "word_count": 1987,
        "quality_score": 88
    },
    "workflow": {
        "w0": "完成",
        "w1": "完成",
        "w2": "完成（3版本）",
        "w3": "完成",
        "w4": "完成",
        "fusion": "完成"
    }
}
```

### 4.3 数据流详细追踪

```
用户输入：章节任务描述
    │
    ├─→ [步骤1] 加载项目状态 (state.json)
    │       └─→ 获取当前进度、已写章节
    │
    ├─→ [步骤2] 加载创作模式 (modes/general.json)
    │       └─→ 获取该模式的写作规则、禁忌、提示词
    │
    ├─→ [步骤3] 加载平台配置 (platform_writing_profiles.json)
    │       └─→ 获取七猫的字数、节奏、风格要求
    │
    ├─→ [步骤4] RAG检索（可选）
    │       ├─→ 解析查询 → 向量化
    │       ├─→ FAISS-HNSW检索Top-5参考小说
    │       ├─→ 提取参考章节内容
    │       └─→ 生成风格参考提示词
    │
    ├─→ [步骤5] W0 情绪锚点设定
    │       ├─→ 调用 LLM (WORKSHOP_W0_MODEL)
    │       ├─→ 生成3-5个情绪锚点
    │       └─→ 确定情绪曲线
    │
    ├─→ [步骤6] W1 设定预处理
    │       ├─→ 读取已有三库
    │       ├─→ 补充缺失设定
    │       ├─→ 设定冲突检测
    │       └─→ 保存更新后的三库
    │
    ├─→ [步骤7] W2 正文初稿
    │       ├─→ 构建完整Prompt（设定+大纲+参考+风格）
    │       ├─→ 并行调用 LLM 3次（生成3个版本）
    │       ├─→ 版本A: deepseek/deepseek-chat
    │       ├─→ 版本B: openai/gpt-4o-mini
    │       └─→ 版本C: anthropic/claude-sonnet (fallback)
    │
    ├─→ [步骤8] W3 逻辑质检
    │       ├─→ 对每个版本进行质检
    │       ├─→ 设定一致性检查
    │       ├─→ 逻辑矛盾检测
    │       ├─→ 红线规则校验
    │       └─→ 生成质检报告
    │
    ├─→ [步骤9] W4 文笔精修
    │       ├─→ 对通过质检的版本进行精修
    │       ├─→ 句子长度优化
    │       ├─→ 节奏调整
    │       ├─→ 情绪曲线校准
    │       └─→ 钩子强化
    │
    ├─→ [步骤10] Fusion 择优
    │       ├─→ 计算各版本得分
    │       │   ├─ 连贯性 30%
    │       │   ├─ 风格匹配 30%
    │       │   ├─ 质量评分 20%
    │       │   └─ 钩子强度 20%
    │       ├─→ 选择最高分版本
    │       └─→ 可选：多版本融合
    │
    └─→ [步骤11] 保存结果
            ├─→ 保存章节文件
            ├─→ 更新 state.json
            ├─→ 保存工作流日志
            └─→ 返回结果给用户
```

---

## 5. 技术栈与开源集成

### 5.1 核心技术栈

| 类别 | 技术 | 用途 | 许可证 |
|------|------|------|--------|
| **编程语言** | Python 3.8+ | 主要开发语言 | PSF |
| **Web框架** | Flask | API服务 | BSD-3-Clause |
| **数据库** | SQLite | 参考库存储 | Public Domain |
| **向量检索** | FAISS | RAG语义检索 | MIT |
| **嵌入模型** | sentence-transformers | 文本向量化 | Apache-2.0 |
| **多模型路由** | LiteLLM | 统一LLM接口 | MIT |
| **CORS** | flask-cors | 跨域支持 | MIT |

### 5.2 开源组件详解

#### 5.2.1 FAISS (Facebook AI Similarity Search)

**用途**：高效的相似度搜索和向量聚类

**为什么选择FAISS**：
- 由Facebook/Meta开发，工业级强度
- 支持HNSW、IVF等多种索引结构
- Python绑定友好
- 内存效率高

**在盘古中的应用**：
```python
# 构建HNSW索引
index = faiss.IndexHNSWFlat(dimension, M)
index.hnsw.efConstruction = efConstruction
index.add(vectors)

# 检索
distances, indices = index.search(query_vector, k)
```

#### 5.2.2 sentence-transformers

**用途**：生成文本的语义嵌入向量

**默认模型**：`paraphrase-multilingual-MiniLM-L12-v2`

**选择理由**：
- 多语言支持（中、英等100+语言）
- 体积小（~100MB），速度快
- 语义相似度效果好
- 开源免费

#### 5.2.3 LiteLLM

**用途**：统一100+LLM供应商的调用接口

**核心价值**：
- 一套代码支持所有模型
- 自动处理重试、熔断、fallback
- 标准化的输入输出格式
- 内置成本追踪

**代码对比**：

**使用前（多套代码）**：
```python
# OpenAI
import openai
openai.api_key = "sk-xxx"
response = openai.ChatCompletion.create(...)

# DeepSeek（需要自己写HTTP）
import requests
response = requests.post("https://api.deepseek.com/v1/chat/completions", ...)

# Claude
import anthropic
client = anthropic.Anthropic(api_key="sk-xxx")
response = client.messages.create(...)
```

**使用后（一套代码）**：
```python
from litellm import completion

# OpenAI
response = completion(model="openai/gpt-4o", ...)

# DeepSeek
response = completion(model="deepseek/deepseek-chat", ...)

# Claude
response = completion(model="anthropic/claude-sonnet-4-6", ...)
```

### 5.3 自研核心算法

#### 5.3.1 情绪曲线检测算法

```python
def detect_emotional_curve(text, segment_size=200):
    """
    检测文本的情绪曲线
    分段 → 情绪打分 → 平滑 → 返回曲线
    """
    segments = split_into_segments(text, segment_size)
    scores = [score_emotion(seg) for seg in segments]
    smoothed = smooth_curve(scores)
    return smoothed
```

#### 5.3.2 风格指纹提取算法

```python
def extract_style_fingerprint(text):
    """
    提取文本的风格指纹
    维度：
    - 句子长度分布
    - 段落长度分布
    - 对话占比
    - 标点密度
    - 词汇复杂度
    """
    features = {
        'avg_sentence_len': calc_avg_sentence_len(text),
        'avg_paragraph_len': calc_avg_paragraph_len(text),
        'dialogue_ratio': calc_dialogue_ratio(text),
        'punctuation_density': calc_punctuation_density(text),
        'vocab_complexity': calc_vocab_complexity(text)
    }
    return features
```

#### 5.3.3 TF-IDF向量化器（纯NumPy实现）

**用途**：FAISS不可用时的回退方案

```python
class SimpleTfidfVectorizer:
    def __init__(self, ngram_range=(2, 4), max_df=0.95, min_df=1):
        self.ngram_range = ngram_range
        self.max_df = max_df
        self.min_df = min_df
        
    def fit_transform(self, texts):
        # 提取n-gram
        # 计算TF-IDF
        # L2归一化
        return matrix
```

---

## 6. 文件结构

### 6.1 完整目录树

```
盘古ai/
├── README.md                           # 系统说明文档
├── 盘古AI系统技术报告.md               # 本文件
├── requirements.txt                    # Python依赖
│
├── pangu.py                            # V2.0精简版CLI
├── pangu_plus.py                       # V7.5增强版CLI（推荐）
├── pangu_check.py                      # 质量检查工具
│
├── generate_new_project.py             # 新项目生成脚本
├── generate_qimao.py                   # 七猫风格专用生成器
├── generate_scifi.py                   # 科幻题材专用生成器
├── generate_rest.py                    # 批量续更脚本
├── create_sample_novel.py              # 示例小说生成器
├── list_all_books.py                   # 参考库列表工具
├── find_scifi.py                       # 科幻题材查找工具
├── find_test_book.py                   # 测试书籍查找工具
│
├── backend/                            # 后端服务目录
│   ├── app.py                          # V6.0基础API
│   ├── app_v7.py                       # V7.5主API（推荐）
│   ├── rag_engine.py                   # RAG检索引擎
│   ├── observability.py                # 可观测性分析引擎
│   ├── generate_novel_libraries.py     # 三库生成器
│   └── __pycache__/                    # Python缓存
│
├── knowledge/                          # 知识库目录
│   ├── novel_reference.db              # SQLite参考库数据库
│   ├── db_manager.py                   # 数据库管理器
│   ├── db_schema.sql                   # 数据库结构
│   ├── chapter_analyzer.py             # 章节分析器
│   ├── reference_prompt.py             # 提示词生成器
│   ├── reference_library.py            # 参考库管理
│   ├── platform_writing_profiles.json  # 平台写作配置
│   ├── unified_knowledge_base.json     # 统一知识库
│   ├── import_novels.py                # 小说导入工具
│   ├── import_chapters.py              # 章节导入工具
│   ├── import_efficient.py             # 高效导入工具
│   ├── import_from_source.py           # 从源导入
│   ├── import_more.py                  # 批量导入
│   ├── run_import.py                   # 导入运行器
│   ├── test_database.py                # 数据库测试
│   ├── .rag_cache/                     # FAISS索引缓存
│   └── __pycache__/                    # Python缓存
│
├── modes/                              # 创作模式配置
│   ├── general.json                    # 通用网文
│   ├── healing_life.json               # 治愈系生活流
│   ├── healing_life_v2.json            # 治愈系V2
│   ├── urban_power.json                # 都市职业异能
│   ├── female_solo.json                # 无CP大女主
│   ├── history_scholar.json            # 历史考据流
│   ├── folk_horror.json                # 中式民俗悬疑
│   ├── rule_mystery.json               # 规则怪谈
│   ├── romance.json                    # 言情
│   ├── crazy_lit.json                  # 疯狂文学
│   └── modules/                        # 模块配置
│       ├── conflict_rules.json         # 冲突规则
│       ├── index.json                  # 模块索引
│       ├── w0_healing_anchor.json      # W0治愈系锚点
│       ├── w1_general_setup.json       # W1通用设定
│       ├── w1_healing_setup.json       # W1治愈系设定
│       ├── w2_general_draft.json       # W2通用初稿
│       ├── w2_healing_draft.json       # W2治愈系初稿
│       ├── w3_general_qc.json          # W3通用质检
│       ├── w3_healing_qc.json          # W3治愈系质检
│       ├── w4_general_polish.json      # W4通用精修
│       └── w4_healing_polish.json      # W4治愈系精修
│
├── workshops/                          # 五车间System Prompts
│   ├── workshop_0_anchor/              # W0情绪锚点
│   │   └── system_prompt.txt
│   ├── workshop_1_setup/               # W1设定预处理
│   │   └── system_prompt.txt
│   ├── workshop_2_draft/               # W2正文初稿
│   │   └── system_prompt.txt
│   ├── workshop_3_qc/                  # W3逻辑质检
│   │   └── system_prompt.txt
│   └── workshop_4_polish/              # W4文笔精修
│       └── system_prompt.txt
│
├── system_prompts/                     # 专家System Prompts
│   ├── novel_writer.txt                # 小说作家
│   ├── title_expert.txt                # 书名专家
│   ├── hook_expert.txt                 # 钩子专家
│   ├── quality_inspector.txt           # 质检专家
│   ├── market_analyst.txt              # 市场分析专家
│   └── short_story_template.txt        # 短篇小说模板
│
└── projects/                           # 项目存储目录
    ├── 使用说明/                       # 使用说明项目
    │   ├── 正文/
    │   │   └── 使用说明.txt
    │   └── state.json
    ├── 凌晨三点/                       # 凌晨三点项目
    │   ├── 正文/
    │   │   └── 凌晨三点.txt
    │   └── state.json
    ├── 古镇的咖啡店/                   # 古镇的咖啡店项目
    │   ├── 大纲/
    │   │   └── 总大纲.md
    │   ├── 正文/
    │   │   └── 第1章_梧桐叶落.txt
    │   └── state.json
    ├── 星尘漫游指南/                   # 星尘漫游指南项目
    │   ├── 大纲/
    │   │   └── 总大纲.md
    │   ├── 正文/
    │   │   ├── 第1章_太空的苏醒.txt
    │   │   ├── 第2章_太空站探秘.txt
    │   │   ├── 第2章_白色房间的秘密.txt
    │   │   ├── 第3章_星尘区.txt
    │   │   ├── 第4章_神秘信号.txt
    │   │   └── 第5章_星门.txt
    │   └── state.json
    └── 末世：我有一座外星空间站/       # 末世空间站项目（示例）
        ├── 大纲/
        │   └── 总大纲.txt
        ├── 正文/
        │   ├── 第1章_太空的苏醒.txt
        │   ├── 第2章_白色房间的秘密.txt
        │   ├── 第3章_星尘区.txt
        │   ├── 第4章_神秘信号.txt
        │   └── 第5章_星门.txt
        ├── 投稿文档.md
        ├── 末世：我有一座外星空间站 投稿文件.docx
        ├── 项目报告.md
        └── state.json
```

### 6.2 关键文件说明

#### 6.2.1 入口文件

| 文件 | 用途 | 推荐场景 |
|------|------|---------|
| `pangu_plus.py` | 增强版CLI，集成参考库 | 日常创作，需要参考功能 |
| `pangu.py` | 精简版CLI | 快速创作，不需要复杂功能 |
| `generate_qimao.py` | 七猫风格专用 | 七猫平台投稿 |
| `generate_new_project.py` | 新项目一键生成 | 开新书 |
| `backend/app_v7.py` | V7.5后端API | 前端集成、服务化部署 |

#### 6.2.2 核心引擎

| 文件 | 功能 |
|------|------|
| `backend/rag_engine.py` | RAG检索引擎，FAISS+HNSW |
| `backend/observability.py` | 可观测性分析，情绪曲线、风格指纹 |
| `knowledge/db_manager.py` | 参考库数据库管理 |
| `knowledge/chapter_analyzer.py` | 章节内容分析器 |
| `knowledge/reference_prompt.py` | 参考提示词生成器 |

#### 6.2.3 配置文件

| 文件 | 内容 |
|------|------|
| `modes/*.json` | 12种创作模式配置 |
| `knowledge/platform_writing_profiles.json` | 四大平台写作配置 |
| `workshops/*/system_prompt.txt` | 五车间System Prompts |
| `system_prompts/*.txt` | 专家角色System Prompts |

---

## 7. 配置指南

### 7.1 环境配置

#### 7.1.1 Python依赖安装

```bash
cd d:\study\近思录\小说\盘古ai

# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows PowerShell:
venv\Scripts\Activate.ps1
# Windows CMD:
venv\Scripts\activate.bat
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

#### 7.1.2 requirements.txt 内容

```txt
flask&gt;=2.0
flask-cors&gt;=3.0
requests&gt;=2.25
litellm&gt;=1.0
faiss-cpu&gt;=1.7
sentence-transformers&gt;=2.0
numpy&gt;=1.20
```

### 7.2 API Key配置

#### 7.2.1 环境变量设置

**Windows PowerShell**：
```powershell
# DeepSeek（推荐，性价比高）
$env:DEEPSEEK_API_KEY = "sk-d0a65c094b53413d8712e93c364ebeea"

# 或 OpenAI
$env:OPENAI_API_KEY = "sk-xxx"

# 或 Anthropic Claude
$env:ANTHROPIC_API_KEY = "sk-ant-xxx"

# 默认模型
$env:LLM_MODEL = "deepseek/deepseek-chat"
```

**Windows CMD**：
```cmd
set DEEPSEEK_API_KEY=sk-d0a65c094b53413d8712e93c364ebeea
set LLM_MODEL=deepseek/deepseek-chat
```

**Linux/Mac**：
```bash
export DEEPSEEK_API_KEY=sk-d0a65c094b53413d8712e93c364ebeea
export LLM_MODEL=deepseek/deepseek-chat
```

#### 7.2.2 车间级模型配置

```bash
# W2初稿车间用Claude（更强的创作能力）
set WORKSHOP_W2_MODEL=anthropic/claude-sonnet-4-6

# W4精修车间用GPT-4o（更好的文笔）
set WORKSHOP_W4_MODEL=openai/gpt-4o

# 其他车间用DeepSeek（性价比高）
set WORKSHOP_W0_MODEL=deepseek/deepseek-chat
set WORKSHOP_W1_MODEL=deepseek/deepseek-chat
set WORKSHOP_W3_MODEL=deepseek/deepseek-chat
```

#### 7.2.3 Fallback配置

```bash
# 主模型失败时自动尝试fallback链
set LLM_FALLBACK=deepseek/deepseek-chat,openai/gpt-4o-mini,ollama/qwen2.5:14b
```

### 7.3 高可用配置

```bash
# 超时时间（秒）
set LLM_TIMEOUT=180

# 重试次数
set LLM_RETRIES=3

# 熔断阈值（连续失败N次后熔断）
set LLM_ALLOWED_FAILS=5

# 熔断冷却时间（秒）
set LLM_COOLDOWN_SEC=30

# 速率限制（每分钟请求数，0=不限制）
set LLM_RPM=0
set LLM_TPM=0
```

### 7.4 RAG配置

```bash
# 语义嵌入模型（默认 paraphrase-multilingual-MiniLM-L12-v2）
set SEMANTIC_MODEL_NAME=paraphrase-multilingual-MiniLM-L12-v2

# 或使用本地模型路径
set SEMANTIC_MODEL_PATH=d:\models\paraphrase-multilingual-MiniLM-L12-v2

# HuggingFace镜像（国内用户推荐）
set HF_ENDPOINT=https://hf-mirror.com
```

### 7.5 创作模式配置

编辑 `modes/general.json`（以通用模式为例）：

```json
{
    "name": "通用网文",
    "description": "适合大多数网络文学创作的通用模式",
    "platform": "fanqie",
    "target_word_count": 3000,
    "writing_rules": [
        "开篇300字必须出钩子",
        "每章至少3个爽点",
        "段落不超过5行",
        "对话占比40-50%"
    ],
    "taboos": [
        "不要大段景物描写",
        "不要过多心理活动",
        "不要解释设定"
    ],
    "workshop_config": {
        "w0": "emotion_anchor",
        "w1": "setup_general",
        "w2": "draft_general",
        "w3": "qc_general",
        "w4": "polish_general"
    }
}
```

### 7.6 平台写作配置

编辑 `knowledge/platform_writing_profiles.json`：

```json
{
    "qimao": {
        "name": "七猫",
        "target_word_count": 2000,
        "style": "爽文",
        "pace": "快节奏",
        "hook_density": "高",
        "rules": [
            "开篇即高潮",
            "每章结尾留钩子",
            "主角强势不圣母",
            "打脸要及时"
        ]
    },
    "fanqie": {
        "name": "番茄",
        "target_word_count": 3000,
        "style": "轻松",
        "pace": "中等",
        "hook_density": "中"
    }
}
```

---

## 附录

### A. 快速开始

```bash
# 1. 进入目录
cd d:\study\近思录\小说\盘古ai

# 2. 设置API Key
$env:DEEPSEEK_API_KEY = "sk-xxx"

# 3. 启动增强版CLI
python pangu_plus.py

# 4. 选择"创建新项目"，按提示操作
```

### B. 常见问题

**Q: API调用失败怎么办？**
A: 检查环境变量是否正确设置，尝试设置fallback模型。

**Q: RAG检索很慢？**
A: 确保使用FAISS-HNSW索引（V7.5默认），第一次运行会构建索引，后续很快。

**Q: 如何添加自己的参考小说？**
A: 使用 `knowledge/import_novels.py` 工具导入到SQLite数据库。

**Q: 可以用本地模型吗？**
A: 可以！使用Ollama运行本地模型，设置 `LLM_MODEL=ollama/qwen2.5:14b`。

---

## 总结

盘古AI V7.5是一套**生产级的智能写作辅助系统**，它的核心优势在于：

1. **理论驱动**：基于叙事动力学，不是随机生成
2. **工程化设计**：流水线架构，可观测、可优化
3. **开源集成**：站在FAISS、LiteLLM等巨人肩膀上
4. **灵活可扩展**：12种模式、四大平台、多模型支持
5. **数据私有**：本地运行，数据安全

**适用场景**：
- 网络文学创作（番茄、起点、七猫、晋江）
- 批量内容生产
- 写作风格学习与模仿
- 新人作者辅助

**不适用场景**：
- 纯文学创作（需要极高的原创性）
- 学术写作（需要严谨的引用）
- 需要深度思考的创作

---

*报告结束*

如有问题，请参考 `README.md` 或查看项目目录中的示例。
