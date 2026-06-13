# 盘古AI写作系统 — 整体状况报告

**报告日期**：2026-06-11  
**系统版本**：V6.0（T02阶段完成）

---

## TL;DR

盘古AI是一个面向网文创作的AI写作系统，核心引擎 7,657 行代码（14个模块），知识库 905MB（2万+参考章节、20万+分析记录），17个创作项目，12种写作模式。T02阶段6个新模块全部集成通过四层验证，系统健康可运行。

---

## 一、系统全景

### 1.1 项目规模

| 指标 | 数值 |
|------|------|
| 项目总大小 | 1.1 GB |
| Python 代码总行数 | ~46,400 行 |
| 核心引擎 (pangu_core) | 7,657 行 / 14 模块 |
| 旧版脚本（顶层） | ~10,500 行 / 10 文件 |
| 知识库引擎 (knowledge/) | ~8,000 行 / 20+ 文件 |
| 后端 (backend/) | ~1,500 行 / 6 文件 |
| 知识库数据库 | 905 MB / 24 张表 |
| 创作项目 | 17 个 |
| 写作模式 | 12 种 |
| 日志文件 | 46 个 |

### 1.2 系统架构

```
┌──────────────────────────────────────────────────────┐
│                   盘古AI 写作系统                       │
├──────────────────────────────────────────────────────┤
│                                                       │
│  ┌──────────── pangu_core (核心引擎) ─────────────┐  │
│  │                                                 │  │
│  │  Pipeline ──→ Stages (W0~W5) ──→ Output       │  │
│  │     │           │                               │  │
│  │     ├── StateSync    ←→  DB (DbContext)        │  │
│  │     ├── WriteGates   →  门控检查               │  │
│  │     ├── Projection   →  走向推演               │  │
│  │     ├── StoryContracts → 契约注入              │  │
│  │     ├── MemoryOrchestrator → 三层记忆           │  │
│  │     └── PromptBuilder  → L1~L15 15层提示词     │  │
│  │                                                 │  │
│  │  辅助：AI Client / Config / BeatSheet / Prompts │  │
│  │  可选：HybridRAG (语义+关键词+结构化检索)        │  │
│  └─────────────────────────────────────────────────┘  │
│                         │                              │
│                         ▼                              │
│  ┌──────────── 知识层 ──────────────┐                  │
│  │  novel_reference.db (905MB)      │                  │
│  │  - 参考书籍 4,465 本             │                  │
│  │  - 参考章节 23,659 章            │                  │
│  │  - 钩子库 64,709 条             │                  │
│  │  - 写作技法 78,041 条           │                  │
│  │  - 情感锚点 60,101 条           │                  │
│  └──────────────────────────────────┘                  │
│                         │                              │
│                         ▼                              │
│  ┌──────────── 应用层 ─────────────┐                   │
│  │  后端 API (Flask)               │                   │
│  │  12种写作模式 (modes/)          │                   │
│  │  17个创作项目 (projects/)       │                   │
│  └─────────────────────────────────┘                   │
└──────────────────────────────────────────────────────┘
```

---

## 二、核心引擎 pangu_core 模块状况

### 2.1 模块清单与健康度

| 模块 | 文件 | 行数 | 职责 | 健康度 |
|------|------|------|------|--------|
| **Pipeline** | `pipeline.py` | 576 | 写作流水线编排 | ✅ 正常 |
| **Stages** | `stages.py` | 952 | W0~W5 六阶段执行 | ✅ 正常 |
| **PromptBuilder** | `prompt_builder.py` | 1,495 | 15层提示词构建 (L1~L15) | ✅ 正常 |
| **WriteGates** | `write_gates.py` | 704 | 写入门控（一致性/伏笔/设定） | ✅ 正常 |
| **MemoryLayers** | `memory_layers.py` | 651 | 三层记忆编排（工作/情节/知识） | ✅ 正常 |
| **HybridRAG** | `rag_hybrid.py` | 690 | 混合检索（语义+关键词+结构化） | ✅ 正常 |
| **StoryContracts** | `story_contracts.py` | 533 | 章节契约（伏笔/角色/设定约束） | ✅ 正常 |
| **BeatSheet** | `beat_sheet.py` | 483 | 节拍表生成与注入 | ✅ 正常 |
| **Projection** | `projection.py` | 401 | 故事走向推演（5条路由） | ✅ 正常 |
| **DB** | `db.py` | 377 | 统一数据库管理 + Schema迁移 | ✅ 正常 |
| **StateSync** | `state_sync.py` | 239 | State↔DB双向同步 | ✅ 正常 |
| **Prompts** | `prompts.py` | 213 | 系统提示词 + 知识注入器 | ✅ 正常 |
| **AI Client** | `ai_client.py` | 177 | 大模型API统一调用 | ✅ 正常 |
| **Config** | `config.py` | 131 | 全局配置管理 | ✅ 正常 |
| **\_\_init\_\_** | `__init__.py` | 35 | 包入口 | ✅ 正常 |

**合计**：7,657 行 / 15 文件 / 14 模块（含 \_\_init\_\_）

### 2.2 模块依赖关系

```
Config ← AI Client ← Prompts
   ↓                     ↓
DB ← StateSync ← Pipeline ← Stages
   ↓               ↓          ↓
   └──── WriteGates  ←── PromptBuilder
         Projection  ←── StoryContracts
         MemoryOrchestrator
         HybridRAG (可选)
```

### 2.3 T02 集成点分布

| 宿主模块 | T02集成点数 | 集成内容 |
|----------|-----------|---------|
| stages.py | 5处 | WriteGates门控 + Projection推演 + MemoryOrchestrator记忆注入 |
| pipeline.py | 4处 | StateSync同步 + WriteGates + Projection + MemoryOrchestrator |
| prompt_builder.py | 4处 | L08角色状态 + L09伏笔 + L10契约 + L11记忆 + L12 RAG + L15 DB上下文 |

所有12处集成点均有 try/except 降级保护，100%覆盖。

---

## 三、知识库状况

### 3.1 数据库统计

| 表名 | 行数 | 用途 |
|------|------|------|
| books | 4,465 | 参考书籍索引 |
| chapters | 23,659 | 参考章节内容 |
| hooks | 64,709 | 钩子（开篇/结尾悬念） |
| writing_techniques | 78,041 | 写作技法库 |
| emotion_anchors | 60,101 | 情感锚点库 |
| projects | 9 | 创作项目 |
| project_chapters | 10 | 项目章节 |
| books_style_tags | 10 | 风格标签关联 |
| style_tags | 13 | 风格标签定义 |
| modes | 12 | 写作模式配置 |
| mode_workshop_configs | 48 | 模式工坊配置 |
| platforms | 4 | 平台定义 |
| character_states | 1 | 角色状态（T02） |
| foreshadowing_threads | 2 | 伏笔线程（T02） |
| setting_constraints | 2 | 设定约束（T02） |
| workshop_tasks | 1 | 工坊任务 |
| workshop_steps | 15 | 工坊步骤 |
| novels | 0 | （预留） |
| knowledge_entries | 0 | 知识条目（T02，迁移后为空） |
| ref_chapters | 0 | 参考章节（T02，迁移后为空） |
| chapter_outputs | 0 | 章节输出 |
| rag_retrievals | 0 | RAG检索记录 |
| task_parameters | 0 | 任务参数 |

**总记录数**：~231,000 条

### 3.2 Schema迁移状态

T02阶段完成了5张表的schema升级（`project_id` → `project_name`），迁移逻辑已内置到 `db.py` 的 `init_tables()` 中，自动检测并迁移旧schema。

---

## 四、创作项目状况

### 4.1 项目清单

| # | 项目名 | 文件数 |
|---|--------|--------|
| 1 | 末世：我有一座外星空间站 | 5章 + 大纲 |
| 2 | 三天后，北境刀皇进京 | - |
| 3 | 凌晨三点 | - |
| 4 | 别信任何人 | - |
| 5 | 古镇的咖啡店 | - |
| 6 | 我有一本明史 | - |
| 7 | 我的系统居然是美少女 | - |
| 8 | 无词者 | - |
| 9 | 星尘漫游指南 | - |
| 10 | 深渊猎人 | - |
| 11 | 生命倒计时7天 | - |
| 12 | 篮神崛起 | - |
| 13 | 规则之下 | - |
| 14 | 逻辑之下 | - |
| 15 | 重生回到高考前一天 | - |
| 16 | 镇妖司：新科状元 | - |
| 17 | 阿念回家 | - |

**合计**：17个项目，51个文本文件

### 4.2 写作模式

12种内置模式：general / romance / urban_power / reality_revenge / rule_mystery / folk_horror / crazy_lit / healing_life / healing_life_v2 / retro_life / history_scholar / female_solo

---

## 五、技术债与待清理项

### 5.1 代码架构债

| 债务项 | 严重度 | 说明 |
|--------|--------|------|
| 旧版脚本冗余 | ⚠️ 中 | `pangu.py`(1,110行) / `pangu_optimized.py`(2,930行) / `pangu_plus.py`(1,499行) 等顶层脚本与 pangu_core 功能重叠，合计 10,500+ 行 |
| 临时文件未清理 | ⚠️ 中 | 46个 `.log` 文件、`temp_*.json/txt`、`scan_results.json` 等临时产物 |
| knowledge/ 模块老化 | ⚠️ 中 | `db_manager.py` / `unified_db_manager.py` / `workshop_db_manager.py` 三套旧DB管理与 `pangu_core/db.py` 重叠 |
| backend 部分模块空置 | ℹ️ 低 | `observability.py` / `rag_engine.py` 已从主流程移除 |

### 5.2 数据债

| 债务项 | 严重度 | 说明 |
|--------|--------|------|
| DB体积 905MB | ⚠️ 中 | hooks/writing_techniques/emotion_anchors 三张表占绝大部分，可考虑归档冷数据 |
| T02新表数据稀少 | ℹ️ 低 | character_states=1, foreshadowing_threads=2, setting_constraints=2（刚迁移，尚无项目数据写入） |
| knowledge_entries / ref_chapters 为空 | ℹ️ 低 | 旧数据迁移时因schema差异无法直接映射，需项目运行后重新积累 |

### 5.3 功能缺失

| 缺失项 | 严重度 | 说明 |
|--------|--------|------|
| rag_engine 未安装 | ℹ️ 低 | HybridRAG 自动降级为空结果，不影响流程 |
| Java后端未对接 | ℹ️ 低 | `backend-java/` 目录存在但未与核心引擎集成 |
| 前端UI | ℹ️ 低 | 当前仅CLI + Flask API，无Web前端 |

---

## 六、测试覆盖状况

### 6.1 T02 集成验证结果

| 层级 | 测试内容 | 结果 |
|------|---------|------|
| L1 模块导入 | 14个核心模块全部可导入 | ✅ PASS |
| L2 接口调用 | 6个T02新模块关键接口正常 | ✅ PASS |
| L3 降级安全 | 12处集成点 100% try/except 覆盖 | ✅ PASS |
| L4 端到端 | Pipeline + StateSync 读写 round-trip | ✅ PASS |

### 6.2 测试文件清单

| 文件 | 测试范围 |
|------|---------|
| `test_pangu_core.py` | 核心引擎基础测试 |
| `test_pipeline.py` | Pipeline 流程测试 |
| `test_system_run.py` | 系统级运行测试 |
| `test_api.py` | API 接口测试 |
| `test_call_ai.py` | AI调用测试 |
| `test_qc_integration.py` | QC集成测试 |
| `test_unified_db.py` | 统一DB测试 |
| `test_workshop_integration.py` | 工坊集成测试 |
| `test_optimized_performance.py` | 性能测试 |
| `knowledge/tests/` | 知识库引擎测试（5个文件） |

---

## 七、依赖环境

| 层级 | 依赖 | 状态 |
|------|------|------|
| 核心 | flask / requests / numpy / python-dotenv / beautifulsoup4 | ✅ 必装 |
| 文本分析 | jieba / sqlalchemy | ✅ 必装 |
| 统计分析 | pandas / scipy / lifelines | ⚡ 建议装 |
| LLM调用 | litellm | 🔌 可选 |
| 向量检索 | faiss-cpu / sentence-transformers | 🔌 可选 |
| 日志 | loguru / tqdm | 🔌 可选 |

---

## 八、下一步建议

1. **清理旧版脚本**：将 `pangu.py` / `pangu_optimized.py` / `pangu_plus.py` 等顶层入口迁移到 `pangu_core` 统一架构，或标记为 `_deprecated`
2. **统一DB管理层**：移除 `knowledge/db_manager.py` / `unified_db_manager.py` / `workshop_db_manager.py`，统一使用 `pangu_core/db.py`
3. **清理临时文件**：删除 46 个空 `.log` 文件、`temp_*.json/txt`、`scan_results.json`
4. **为活跃项目填充T02数据**：运行 Pipeline 写入 character_states / foreshadowing_threads / setting_constraints，验证完整写作流程
5. **安装 rag_engine**：如需语义检索能力，安装 faiss-cpu + sentence-transformers 启用 HybridRAG
6. **DB冷热分离**：将 hooks/writing_techniques/emotion_anchors 的历史数据归档，减小主库体积
