# 盘古AI系统架构优化 PRD

> 版本：v1.0 | 日期：2026-06-11 | 产品经理：许清楚（Xu）

---

## 1. 产品目标

**消除盘古AI双路径架构的40%逻辑重复，将已实现但未接入的RAG/投影/合约模块接入主写作流程，使系统从"功能碎片化"升级为"能力闭环"。**

---

## 2. 用户故事

| # | 用户故事 | 对应需求 |
|---|---------|---------|
| US1 | 作为网文作者，我希望用快速写作和工坊Pipeline写出风格一致的内容，而不是两条路径产生不同质量的章节 | P0-双路径统一 |
| US2 | 作为网文作者，我希望系统自动检索我已有的知识库内容（85个知识块），让新章节与已有设定保持连贯 | P0-RAG接入 |
| US3 | 作为网文作者，我希望系统记住我写过的角色状态、伏笔和设定，不再需要手动翻查前文 | P0-数据库管道 |
| US4 | 作为网文作者，我希望系统在写完一章后自动分析人物弧光、情节势能等五个维度，帮我发现故事偏差 | P1-投影接入 |
| US5 | 作为开发者，我希望代码模块清晰、入口统一，不再需要维护两套重复的prompt构建和AI调用逻辑 | P1-代码拆分 |

---

## 3. 需求池

### P0 — 必须完成（架构基座）

#### P0-1：双路径统一

**问题**：`pangu_optimized.py`的`write_chapter_quick()`和`workflow_engine.py`的`run_workflow_pipeline()`各自独立实现了prompt构建、mode规则加载、平台规则、风格指引、AI调用、状态更新，约40%逻辑重复。

**方案**：统一为一条写作管线，保留"快速模式"和"工坊模式"作为同一管线的两种运行配置（跳过/启用不同Stage），而非两套独立代码。

**验收标准**：
- [ ] `build_smart_prompt()`和`KnowledgeInjector`共享同一套prompt注入链，无重复定义
- [ ] `write_chapter_quick()`和`run_workflow_pipeline()`调用同一个AI调用入口
- [ ] 快速模式 = 工坊管线中仅执行W0+W2+W4（跳过W1+W3），输出质量不退化
- [ ] 两种模式生成的章节，对同一输入的mode/platform规则注入内容一致
- [ ] 删除重复代码后，总行数减少 >= 800行（约40%重复的估算值）

#### P0-2：数据库管道连接

**问题**：`novel_reference.db`有7张空表（task_parameters/rag_retrievals/chapter_outputs/ref_chapters/foreshadowing_threads/character_states/setting_constraints/knowledge_entries/novels），`creative_engine.db`的writing_strategies表也为空。写作流程从未读写这些表。

**方案**：在统一写作管线的关键节点（Stage执行前后）插入数据库读写操作，使写作用到已有数据并产生持久化记录。

**验收标准**：
- [ ] 写作前：从`character_states`表读取角色当前状态注入prompt
- [ ] 写作前：从`foreshadowing_threads`表读取未闭合伏笔注入prompt
- [ ] 写作后：将生成内容写入`chapter_outputs`表
- [ ] 写作后：将角色状态变更写入`character_states`表
- [ ] 写作后：将伏笔状态更新写入`foreshadowing_threads`表
- [ ] 上述操作均通过`pangu_core/db.py`的`DatabaseManager`执行，不新增数据库连接方式

#### P0-3：RAG混合检索接入

**问题**：`pangu_core/rag_hybrid.py`（690行）已实现FAISS+BM25+RRF+Rerank混合检索，但从未接入主写作流程。85个知识块已初始化但从未被检索使用。

**方案**：在统一管线的prompt构建阶段，调用RAG混合检索获取与当前章节任务相关的知识块，注入prompt。

**验收标准**：
- [ ] 写作前自动调用`rag_hybrid.py`的检索接口，按章节任务查询相关top-K知识块
- [ ] 检索结果注入`build_smart_prompt()`的新增层（如L12:RAG检索结果）
- [ ] 检索过程记录到`rag_retrievals`表（query/top_k结果/scores/timestamp）
- [ ] RAG检索失败时降级为无RAG模式，不阻断写作流程
- [ ] 验证：用已有85个知识块中的已知内容作为章节任务，确认检索命中

---

### P1 — 应该完成（能力增强）

#### P1-1：五路投影接入

**问题**：`pangu_core/projection.py`（401行）已实现五路投影（STATE/VECTOR/MEMORY/INDEX/EVENT），但从未接入主写作流程。

**方案**：在统一管线的写作完成后（W4之后），调用`run_projections()`对章节内容进行五路投影。

**验收标准**：
- [ ] 章节写作完成后自动触发`run_projections()`
- [ ] 投影结果持久化到项目目录的`.projections/`目录
- [ ] 单路投影失败不影响其他路和主流程
- [ ] 投影产出可在下次写作时被检索和使用（与RAG/数据库管道联动）

#### P1-2：pangu_optimized.py拆分

**问题**：`pangu_optimized.py`有2930行，函数堆叠，职责混杂（prompt构建/项目管理/AI调用/状态更新/工具函数全部混在一起）。

**方案**：按职责拆分为多个模块，保留`pangu_optimized.py`作为入口薄壳。

**验收标准**：
- [ ] `pangu_optimized.py`行数 <= 300行（仅保留入口函数和CLI交互）
- [ ] 拆分后的模块放在`pangu_core/`下，每个模块 <= 500行
- [ ] 所有现有CLI命令和参数不变，对外接口向后兼容
- [ ] `build_smart_prompt()`函数签名和返回值不变
- [ ] 拆分后所有现有功能通过回归测试

#### P1-3：Story Contracts接入

**问题**：`pangu_core/story_contracts.py`（533行）已实现四层合同链（MASTER_SETTING/VolumeBrief/ChapterBrief/ReviewContract），但未接入。

**方案**：在统一管线的prompt构建阶段，注入Story Contracts作为写作约束。

**验收标准**：
- [ ] 从`state.json`和`大纲/`目录自动构建合同链
- [ ] 合同链注入`build_smart_prompt()`的L10层
- [ ] 违反合同的内容在QC阶段被检测并标记

---

### P2 — 可以延后（锦上添花）

#### P2-1：creative_engine空表填充

**问题**：`creative_engine.db`的`writing_strategies`表为空。

**方案**：将现有的modes/JSON文件中的策略数据导入该表。

**验收标准**：
- [ ] `writing_strategies`表包含所有现有mode的策略数据
- [ ] 写作时可从该表读取策略推荐

#### P2-2：记忆层系统深度集成

**问题**：`pangu_core/memory_layers.py`（651行）部分接入，但三层记忆（Working/Episodic/Semantic）的完整生命周期未闭环。

**方案**：完善记忆层的写入（写作后存储）和读取（写作前注入）。

**验收标准**：
- [ ] 写作后自动将章节内容提取为三层记忆条目
- [ ] 写作前按预算分配三层记忆条目注入prompt
- [ ] 记忆条目持久化到`memory_bank.json`和数据库

#### P2-3：Write Gates完整接入

**问题**：`pangu_core/write_gates.py`（704行）部分接入，三层关卡（prewrite/precommit/postcommit）未完整运行。

**方案**：在统一管线的三个关键节点分别调用三层关卡。

**验收标准**：
- [ ] prewrite关卡在W0之前执行
- [ ] precommit关卡在W4之后、状态更新之前执行
- [ ] postcommit关卡在状态更新之后执行
- [ ] blocker级别问题阻断流程并给出修复建议

---

## 4. 待确认问题

| # | 问题 | 影响范围 | 建议 |
|---|------|---------|------|
| Q1 | **双路径统一后，工坊Pipeline的Stage体系是否保留？** | P0-1 | 建议保留Stage/Pipeline模式作为统一架构，快速模式作为"跳过部分Stage"的配置。这样既统一了代码路径，又保留了工坊的分阶段质检能力 |
| Q2 | **`write_chapter_quick()`的17层prompt注入链是否全部迁移到`pangu_core/prompts.py`？** | P0-1, P1-2 | 建议是。`pangu_core/prompts.py`已声明为"唯一真值来源"，17层链应集中管理。但需确认迁移后`workflow_engine.py`的`KnowledgeInjector`如何适配 |
| Q3 | **数据库管道的读写粒度：是每次写作都读写，还是按章节号判断？** | P0-2 | 首次写入（空表）建议每次写作后都写；后续增量更新需与`state.json`的更新逻辑对齐，避免数据不一致 |
| Q4 | **RAG检索的top-K值和rerank策略如何确定？** | P0-3 | 建议初始top-K=5，rerank后取top-3注入prompt。后续可根据实际效果调优 |
| Q5 | **拆分pangu_optimized.py时，`_`开头的内部函数如何处理？** | P1-2 | 部分内部函数被`workflow_engine.py`间接依赖，拆分时需确认所有跨模块引用并更新import |
| Q6 | **是否需要为架构优化增加集成测试？** | 全局 | 当前系统未见自动化测试。建议P0阶段至少为双路径统一和数据库管道增加集成测试，防止回归 |
| Q7 | **投影和RAG的交互：投影产出的VECTOR和INDEX是否作为RAG的检索源？** | P1-1, P0-3 | 建议是。投影的VECTOR路更新FAISS索引，INDEX路更新BM25语料，形成"写后索引→下次检索"的闭环。但需确认增量更新的实现方式 |

---

## 附录A：现有功能清单（不可破坏）

| 功能 | 入口 | 所在文件 | 备注 |
|------|------|---------|------|
| 17层Prompt注入链 | `build_smart_prompt()` | pangu_optimized.py:1774 | 已验证6/6通过 |
| 快速写作路径 | `write_chapter_quick()` | pangu_optimized.py:2160 | 用户实际使用 |
| 工坊Pipeline | `run_workflow_pipeline()` | workflow_engine.py:1402 | W0-W5五阶段 |
| 批量生成 | `batch_generate()` | pangu_optimized.py:2362 | 依赖快速写作 |
| 知乎盐选/起点导入 | CLI子命令 | pangu_optimized.py | 素材导入脚本 |
| RAG知识库初始化 | 初始化逻辑 | pangu_core/rag_hybrid.py | 85个知识块 |

## 附录B：代码规模与重复分析

| 文件 | 行数 | 核心问题 |
|------|------|---------|
| pangu_optimized.py | 2930 | 主入口，过于庞大，函数堆叠 |
| workflow_engine.py | 1552 | 独立Pipeline，与路径A约40%重复 |
| pangu_core/rag_hybrid.py | 690 | 已实现未接入 |
| pangu_core/projection.py | 401 | 已实现未接入 |
| pangu_core/memory_layers.py | 651 | 部分接入 |
| pangu_core/write_gates.py | 704 | 部分接入 |
| pangu_core/story_contracts.py | 533 | 未接入 |
| pangu_core/其他 | 1138 | prompts/db/config/ai_client/beat_sheet |
| **总计** | **8599** | |
