# 盘古AI系统 - 重构路线图

> 版本: v1.0
> 更新日期: 2026-06-10
> 状态: 草稿

---

## 1. 问题诊断

### 1.1 当前状态评估

| 维度 | 现状 | 问题 | 影响评分 |
|------|------|------|---------|
| 五车间流水线 | app_v7.py 完整实现，但未被调用 | 用户用 pangu_optimized.py 绕过 | ⭐⭐ 差 |
| 数据库填充 | 三表（hooks/emotion_anchors/writing_techniques）全空 | batch_analyze.py 未运行 | ⭐ 很差 |
| Prompt质量 | build_smart_prompt 有10层注入，但实际注入不完整 | 缺少深度注入配置 | ⭐⭐ 差 |
| 批量模式 | 无上下文传递机制 | 长篇一致性差 | ⭐ 很差 |
| 导入脚本 | 8个独立脚本，碎片化 | 数据管理混乱 | ⭐⭐ 中 |
| 状态追踪 | state.json 有字段定义，但未更新 | 伏笔/角色追踪失效 | ⭐ 很差 |
| 代码质量 | app_v7.py 有 import 崩溃 | 后端无法启动 | ⭐⭐⭐ 及格 |
| 可观测性 | 有框架但缺依赖库 | 诊断能力弱 | ⭐⭐ 中 |

**综合评分**: ⭐⭐ (2/5) - 架构优秀，执行脱节

### 1.2 根因分析

```
┌──────────────────────────────────────────────────────────────────┐
│                        问题根因分析                               │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   用户需求: "写2000字，留钩子"                                    │
│          │                                                      │
│          ▼                                                      │
│   ┌─────────────────┐                                           │
│   │ pangu_optimized  │ ◄── 用户实际使用的入口                    │
│   │ _py (主入口)     │                                           │
│   └────────┬────────┘                                           │
│            │                                                    │
│            ▼                                                    │
│   ┌─────────────────────────────────────────────┐              │
│   │ build_smart_prompt()                        │              │
│   │ - 通用规则 ✓                                │              │
│   │ - 平台规则 ✓                                │              │
│   │ - 模式规则 ✗ (部分)                         │              │
│   │ - 情绪锚点 ✗ (未注入)                       │              │
│   │ - 伏笔追踪 ✗ (未调用)                       │              │
│   │ - Lorebook ✗ (未调用)                       │              │
│   │ - De-AI约束 ✗ (未注入)                       │              │
│   │ - Beat Sheet ✗ (未调用)                     │              │
│   └─────────────────────────────────────────────┘              │
│          │                                                      │
│          ▼                                                      │
│   ┌─────────────────────────────────────────────┐              │
│   │ call_llm() ──► 输出 "AI味" 文本            │              │
│   └─────────────────────────────────────────────┘              │
│          │                                                      │
│          ▼                                                      │
│   ┌─────────────────────────────────────────────┐              │
│   │ _update_state_after_writing() 几乎不工作     │              │
│   │ - 伏笔追踪为空                               │              │
│   │ - 角色识别为空                               │              │
│   │ - 设定日志为空                               │              │
│   └─────────────────────────────────────────────┘              │
│                                                                  │
│   核心问题: 五车间流水线 (app_v7.py) 存在但从未被调用             │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. 重构阶段

### Phase 1: 止血 (Week 1-2)

**目标**: 让现有功能可运行，消除阻塞性问题

#### 1.1 修复 app_v7.py import 崩溃

**问题**: `app_v7.py` 导入了不存在的模块

**修复方案**:

```python
# 当前代码 (app_v7.py:31-38)
try:
    from rag_engine import get_rag, PanguRAG
    from rag_engine import build_graph_from_project
except ImportError:
    # 有stub，但 observability 模块缺失
    get_rag = None
    PanguRAG = None
    build_graph_from_project = None

# 修复: 确保所有导入失败都有安全回退
```

**任务清单**:
- [ ] 创建 `backend/rag_engine.py` stub (至少300行兼容代码)
- [ ] 创建 `backend/observability.py` stub (至少200行兼容代码)
- [ ] 创建 `backend/textgrad_opt.py` stub
- [ ] 创建 `backend/style_library.py` stub
- [ ] 创建 `backend/dspy_compile.py` stub
- [ ] 验证 Flask 服务可正常启动

**验收标准**: `python backend/app_v7.py` 无报错，访问 `localhost:5001/api/v7/health` 返回正常

#### 1.2 接通五车间流水线到CLI

**问题**: 用户通过 `pangu_optimized.py` 使用系统，但五车间在 `app_v7.py` 中

**修复方案**: 在 `pangu_optimized.py` 中添加选项，调用 `app_v7.py` 的五车间

```python
# pangu_optimized.py 新增功能
def write_chapter_with_workshop(project_dir, chapter_task, workshop_id=None):
    """调用五车间流水线写章节"""
    from backend.app_v7 import SchedulerV7

    # 加载项目配置
    state = load_state(project_dir)

    # 构建输入
    user_input = {
        "title": state["project_info"]["title"],
        "chapter_num": state["progress"]["current_chapter"] + 1,
        "chapter_task": chapter_task,
        "mode": state["project_info"]["genre"],
        "platform": state["project_info"]["platform"],
        "cold_storage": load_cold_storage(project_dir),
        "project_name": project_dir.name,
    }

    # 调用五车间
    scheduler = SchedulerV7(user_input)
    result = scheduler.run()

    if result["success"]:
        save_chapter(project_dir, result["results"]["w4_final_chapter"])
        update_state(project_dir, result)

    return result
```

**任务清单**:
- [ ] 在 `pangu_optimized.py` 添加"使用五车间"选项
- [ ] 测试 W0→W1→W2→W3→W4 完整流程
- [ ] 测试 W0 阻断机制（万能主旨不通过）

**验收标准**: 用户可以选择"使用五车间"模式，生成质量明显提升

#### 1.3 跑批量分析填充数据库

**问题**: 数据库三表为空，RAG检索无数据

**修复方案**: 运行 `knowledge/scripts/batch_analyze.py`

```bash
# 批量分析命令
python knowledge/scripts/batch_analyze.py \
    --input-dir "knowledge/references/books" \
    --output-db "knowledge/unified_novel.db" \
    --batch-size 50
```

**任务清单**:
- [ ] 检查 `batch_analyze.py` 是否可运行
- [ ] 准备参考书籍目录
- [ ] 运行批量分析（预计2-4小时）
- [ ] 验证数据库填充率

**验收标准**: 
- `hooks` 表: ≥100条记录
- `emotion_anchors` 表: ≥50条记录
- `writing_techniques` 表: ≥200条记录

#### 1.4 清理导入脚本

**问题**: 8个独立脚本，碎片化

**修复方案**: 合并为统一脚本

```
scripts/
├── import_books.py      # 导入书籍
├── import_techniques.py  # 导入技法
├── import_modes.py       # 导入模式
├── import_platforms.py   # 导入平台
├── import_hooks.py       # 导入钩子
├── import_emotions.py    # 导入情绪
├── import_patterns.py    # 导入模式规则
├── batch_analyze.py      # 批量分析
│
└── unified_import.py     # 统一导入 (新)

# 合并后的统一脚本
python scripts/unified_import.py --mode all  # 导入所有
python scripts/unified_import.py --mode incremental  # 增量导入
python scripts/unified_import.py --mode verify  # 验证数据完整性
```

**任务清单**:
- [ ] 创建 `scripts/unified_import.py`
- [ ] 保留原有脚本作为兼容
- [ ] 添加去重逻辑
- [ ] 添加进度显示

---

### Phase 2: 筑基 (Week 3-4)

**目标**: 提升Prompt质量，完善状态追踪

#### 2.1 重构 Prompt 注入逻辑

**问题**: `build_smart_prompt()` 有10层定义，但实际注入不完整

**当前注入率分析**:

| 层级 | 内容 | 注入率 |
|------|------|--------|
| L1 | 通用质量规则 | 100% |
| L2 | 平台专属约束 | 100% |
| L3 | 模式深度规则 | 60% |
| L4 | 风格指纹指引 | 30% |
| L5 | 情绪锚点 | 0% |
| L6 | 伏笔追踪提醒 | 0% |
| L7 | Lorebook强制注入 | 0% |
| L8 | De-AI化约束 | 80% |
| L9 | Beat Sheet节拍 | 50% |
| L10 | 上下文内容 | 100% |

**修复方案**: 完善各层注入逻辑

```python
def build_smart_prompt(state, chapter_task, chapter_num, context=""):
    parts = {"system": [], "user": []}

    # L1: 通用质量规则
    parts["system"].append(_load_universal_prompt())

    # L2: 平台专属约束
    parts["system"].append(_extract_platform_section(state["project_info"]["platform"]))

    # L3: 模式深度规则 (修复: 直接读JSON完整配置)
    parts["system"].append(_load_mode_deep_injection(state["project_info"]["genre"]))

    # L4: 风格指纹指引 (新增: 启用风格库)
    style_vault = _load_style_vault(state["project_info"]["genre"], chapter_task)
    if style_vault:
        parts["system"].append(style_vault)

    # L5: 情绪锚点 (新增: 从state提取情绪状态)
    emotion_hints = _extract_emotion_anchors(state, chapter_num)
    if emotion_hints:
        parts["system"].append(f"【情绪锚点】\n{emotion_hints}")

    # L6: 伏笔追踪提醒 (新增: 调用追踪函数)
    foreshadow = _build_foreshadow_reminder(state, chapter_num)
    if foreshadow:
        parts["user"].append(f"【伏笔提醒】\n{foreshadow}")

    # L7: Lorebook强制注入 (新增: 完善匹配逻辑)
    lorebook = _inject_lorebook(state, chapter_task, context)
    if lorebook:
        parts["system"].append(f"【世界观设定(Lorebook)】\n{lorebook}")

    # L8: De-AI化约束 (修复: 完整加载)
    parts["system"].append(_load_de_ai_rules())

    # L9: Beat Sheet节拍 (新增: AI生成beat)
    beats = _generate_beat_sheet(state, chapter_task, chapter_num)
    if beats:
        parts["system"].append(_inject_beat_sheet(beats))

    # L10: 上下文内容
    parts["user"].append(context)

    return "\n\n".join(parts["system"]), "\n\n".join(parts["user"])
```

**任务清单**:
- [ ] 完善 L3: 模式JSON深度注入
- [ ] 完善 L4: 风格库匹配
- [ ] 实现 L5: 情绪锚点提取
- [ ] 实现 L6: 伏笔追踪提醒
- [ ] 实现 L7: Lorebook完整匹配
- [ ] 完善 L8: De-AI规则
- [ ] 实现 L9: Beat Sheet生成
- [ ] 编写Prompt注入测试

**验收标准**: Prompt注入完整度从 5% 提升到 80%

#### 2.2 实现上下文传递机制

**问题**: 批量模式无上下文传递，长篇一致性差

**修复方案**: 在批量生成中传递上下文

```python
def batch_generate(project_dir, count=5):
    state = load_state(project_dir)
    last_content = None

    for i in range(count):
        chapter_num = state["progress"]["current_chapter"] + 1

        # 构建上下文
        context_parts = []

        # 1. 前序章节内容
        prev_context = get_context_chapters(project_dir, chapter_num)
        if prev_context:
            context_parts.append(prev_context)

        # 2. 上一轮生成的内容
        if last_content:
            context_parts.append(
                f"## 上一章（第{chapter_num-1}章）结尾\n\n"
                f"{last_content[-800:]}\n"
            )

        # 3. 伏笔追踪提醒
        foreshadow = _build_foreshadow_reminder(state, chapter_num)
        if foreshadow:
            context_parts.append(f"【伏笔提醒】\n{foreshadow}")

        context = "\n\n".join(context_parts) if context_parts else ""

        # 生成章节
        result = write_chapter(project_dir, chapter_task, context)

        # 更新上下文
        if result["success"]:
            last_content = result["content"]
            state = _update_state_after_writing(state, last_content, chapter_num)
            save_state(state)

    return state
```

**任务清单**:
- [ ] 实现批量模式上下文传递
- [ ] 实现伏笔追踪上下文注入
- [ ] 测试5章连写一致性

**验收标准**: 批量生成5章后，伏笔追踪记录 ≥ 3条

#### 2.3 完善伏笔追踪系统

**问题**: `_update_state_after_writing()` 未正确更新伏笔/角色/设定

**修复方案**: 重写更新逻辑，增加自动追踪

```python
def _update_state_after_writing(state, content, chapter_num, chapter_task):
    """从生成文本中提取并更新状态"""

    # 1. 伏笔追踪
    foreshadow = state.get("foreshadowing", {})
    active = foreshadow.get("active_threads", [])

    # 检测新伏笔
    new_threads = _extract_foreshadow(content)
    for t in new_threads:
        if not _is_duplicate(t, active):
            t["id"] = f"f{len(active)+1:03d}"
            t["planted_ch"] = chapter_num
            t["status"] = "open"
            active.append(t)

    # 检查伏笔兑现
    for t in active:
        if t["status"] == "open":
            if _is_foreshadow_resolved(t, content):
                t["status"] = "resolved"
                t["resolved_ch"] = chapter_num

    foreshadow["active_threads"] = active
    foreshadow["last_updated"] = datetime.now().isoformat()
    state["foreshadowing"] = foreshadow

    # 2. 角色追踪
    chars = state.get("characters", {})
    detected_chars = _extract_characters(content)
    _update_characters(chars, detected_chars, chapter_num)
    state["characters"] = chars

    # 3. 设定日志
    setting = state.get("setting_log", {})
    new_rules = _extract_setting_rules(content)
    setting["locked_rules"].extend(new_rules)
    setting["last_checked_chapter"] = chapter_num
    state["setting_log"] = setting

    return state
```

**任务清单**:
- [ ] 重写伏笔提取函数
- [ ] 重写角色识别函数
- [ ] 重写设定提取函数
- [ ] 添加伏笔兑现检测
- [ ] 添加伏笔过期告警

**验收标准**: 写完10章后，state.json 中有完整的伏笔/角色/设定记录

---

### Phase 3: 扩展 (Week 5-8)

**目标**: 添加Web界面、API服务、Qclaw集成

#### 3.1 开发 Web 前端

**技术选型**:
- 前端框架: React 18 + TypeScript
- UI组件: Ant Design
- 状态管理: Zustand
- 图表: ECharts

**核心页面**:
1. **首页/仪表盘** - 项目列表、进度概览、最近活动
2. **项目详情** - 章节列表、伏笔追踪、角色图谱
3. **写作工作台** - 章节编辑、Prompt预览、生成控制
4. **质检报告** - 质量评分、问题列表、改写建议
5. **设置页面** - API Key配置、模式管理、参数调优

**任务清单**:
- [ ] 初始化 React 项目
- [ ] 实现项目列表页面
- [ ] 实现章节编辑页面
- [ ] 实现伏笔追踪可视化
- [ ] 实现质量报告页面
- [ ] 前后端API对接

#### 3.2 实现 REST API 服务

**基于现有 `app_v7.py` 扩展**:

```python
# 新增API路由
@app.route("/api/v1/projects", methods=["GET", "POST"])
def list_projects():
    """项目列表 / 创建项目"""
    pass

@app.route("/api/v1/projects/<project_id>", methods=["GET", "PUT", "DELETE"])
def project_detail(project_id):
    """项目详情 / 更新 / 删除"""
    pass

@app.route("/api/v1/projects/<project_id>/chapters", methods=["POST"])
def generate_chapter(project_id):
    """生成章节"""
    pass

@app.route("/api/v1/projects/<project_id>/chapters/<int:num>", methods=["GET"])
def get_chapter(project_id, num):
    """获取章节"""
    pass

@app.route("/api/v1/projects/<project_id>/analytics", methods=["GET"])
def project_analytics(project_id):
    """项目分析数据"""
    pass
```

**任务清单**:
- [ ] 整理现有API路由
- [ ] 添加项目管理API
- [ ] 添加认证/鉴权
- [ ] 添加API文档 (Swagger)
- [ ] 添加请求限流

#### 3.3 Qclaw 集成

**集成方案**: Skill插件形式

```json
{
  "name": "pangu_novel_writer",
  "version": "1.0.0",
  "description": "盘古AI小说创作助手",
  "triggers": [
    {
      "pattern": "写第{n}章",
      "action": "call_api",
      "params": {
        "method": "POST",
        "endpoint": "/api/v1/projects/{project_id}/chapters",
        "body": {
          "chapter_num": "{n}",
          "chapter_task": "{task}"
        }
      }
    },
    {
      "pattern": "检查质量",
      "action": "call_api",
      "params": {
        "method": "POST",
        "endpoint": "/api/v7/observability/score",
        "body": {
          "text": "{selected_text}"
        }
      }
    }
  ]
}
```

**任务清单**:
- [ ] 创建 Qclaw Skill 配置文件
- [ ] 定义命令模式
- [ ] 实现 API 调用封装
- [ ] 添加响应格式化
- [ ] 编写使用文档

---

### Phase 4: 商业化 (Month 3-6)

**目标**: 准备商业化，支持多租户

#### 4.1 多租户架构

```python
# 数据库增加租户字段
ALTER TABLE projects ADD COLUMN tenant_id VARCHAR(36);
ALTER TABLE users ADD COLUMN tenant_id VARCHAR(36);

# API增加租户隔离
@app.before_request
def check_tenant():
    tenant_id = request.headers.get("X-Tenant-ID")
    g.tenant_id = tenant_id
```

#### 4.2 计费和订阅

```python
# 订阅计划
SUBSCRIPTION_PLANS = {
    "free": {"projects": 1, "chapters_per_month": 10},
    "pro": {"projects": 5, "chapters_per_month": 100},
    "enterprise": {"projects": -1, "chapters_per_month": -1}
}
```

---

## 3. 优先级矩阵

| 优先级 | 任务 | 工作量 | 风险 | 收益 |
|--------|------|--------|------|------|
| P0 | 修复 app_v7.py import | 低 | 低 | 高 |
| P0 | 接通五车间到CLI | 中 | 低 | 高 |
| P0 | 跑批量分析填充DB | 低 | 低 | 中 |
| P1 | 重构 Prompt 注入 | 中 | 中 | 高 |
| P1 | 实现上下文传递 | 中 | 中 | 高 |
| P2 | 完善伏笔追踪 | 中 | 低 | 中 |
| P2 | Web 前端 | 高 | 中 | 高 |
| P3 | REST API 扩展 | 中 | 低 | 中 |
| P3 | Qclaw 集成 | 中 | 中 | 中 |
| P4 | 多租户架构 | 高 | 高 | 中 |

---

## 4. 资源估算

| 阶段 | 预计工期 | 主要工作 |
|------|---------|---------|
| Phase 1: 止血 | 2周 | 修复崩溃、接通五车间 |
| Phase 2: 筑基 | 2周 | Prompt质量、状态追踪 |
| Phase 3: 扩展 | 4周 | Web界面、API服务 |
| Phase 4: 商业化 | 3月+ | 多租户、计费系统 |

---

## 5. 验收标准

| 阶段 | 验收标准 |
|------|---------|
| Phase 1 | 五车间流水线可正常调用，数据库填充率 ≥ 50% |
| Phase 2 | Prompt注入完整度 ≥ 80%，伏笔追踪可用 |
| Phase 3 | Web界面可完成基本写作流程 |
| Phase 4 | 支持多租户，计费系统可用 |

---

## 6. 变更历史

| 日期 | 版本 | 变更内容 | 作者 |
|------|------|---------|------|
| 2026-06-10 | v1.0 | 初稿创建 | Claude |
