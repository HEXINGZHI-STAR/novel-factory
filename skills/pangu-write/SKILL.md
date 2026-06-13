---
name: pangu-write
description: 盘古写章——Claude分析上下文→合成写作任务书→调Pipeline生成→审查归档
allowed-tools: Read Write Edit Grep Bash Agent AskUserQuestion
argument-hint: "[章号] [--fast] [--workshop]"
---

# 盘古写章流程

## 🚨 强制规则（违反即错误）

1. **严禁直接写正文** — Claude 不得使用 Write 工具直接起草章节正文
2. **Pipeline 是唯一路径** — 所有章节必须通过 `pangu_core.pipeline.WritingPipeline` 生成
3. **Bash 调用是必须的** — 必须在 Bash 中执行 Python 脚本调用 Pipeline，不可口头模拟
4. **判断标准** — 如果你没有看到 `[W2] OK` 和 `[W4] OK` 的日志输出，说明你没有调用系统

## 核心理念

**Claude 做判断，DeepSeek 做执行，Pipeline 做管理。**

不委托 subagent 做创作判断——Claude 直接读上下文、定方向、审质量。
subagent 只用于并行检索等机械任务。

## 模式

| 模式 | 流程 | 说明 |
|------|------|------|
| `--fast`（默认）| Step 1→2→3→4 | 跳过 W1/W3/W5，快速出章 |
| `--workshop` | Step 1→2(全Stage)→3→4 | 完整 W0-W5，质量优先 |

## 硬规则

- **禁止**跳步、并步、伪造审查
- Claude 必须亲自读上下文+大纲，不得委托 subagent 做创作判断
- Pipeline 调用失败时报告具体错误，不凭空补内容
- 审查结论必须引用正文具体段落

## 执行流程

### Step 1：Claude 读上下文，定方向

Claude 直接读取以下文件（按需，不全读）:

```
必读:
  {project}/.webnovel/state.json         → 项目状态
  {project}/大纲/总纲.md                  → 故事总纲
  {project}/大纲/第1卷-详细大纲.md         → 本章所在卷纲（如有）

按需:
  {project}/正文/第{N-1}章-*.md           → 上一章结尾（衔接钩子）
  {project}/设定集/主角卡.md               → 人物状态
  {project}/设定集/世界观.md               → 世界观约束
```

读取后，Claude 在本对话中形成 **写作任务书**（不写文件，直接用于 Step 2），包含：

1. **本章硬性约束**：章纲目标、时间锚点、字数要求
2. **前情衔接**：上一章结尾的钩子是什么，本章开头必须接住
3. **本章必须覆盖的节点**：角色出场、伏笔推进/回收、情绪节拍
4. **本章禁区**：不能写什么（角色OOC、设定矛盾、提前泄露）
5. **风格指引**：句式要求、感官优先级、金句目标

### Step 2：生成正文

**只能使用方式 A**。方式 B 仅作为 API 完全不可用时的最后降级方案。

**方式 A（强制）：调用盘古 Pipeline**

```bash
cd {PANGU_ROOT}
python -c "
import sys
sys.path.insert(0, '.')
from pangu_core.pipeline import WritingPipeline, PipelineConfig

config = PipelineConfig.from_quick_mode(
    project_dir='{project}',
    chapter={chapter_num},
    task='{chapter_task}',
    mode='{mode_name}',
    platform='{platform_name}',
)
pipeline = WritingPipeline(config)
result = pipeline.run()
if result.success:
    print(f'[OK] {len(result.chapter_content)}字')
    # 内容已写入 正文/第{chapter_num}章.txt
else:
    print(f'[FAIL] errors: {result.errors}')
    print(f'       warnings: {result.warnings}')
"
```

**方式 B：Claude 直接起草（兜底）**

当 Pipeline 调用失败（API 限额/网络问题）时，Claude 根据 Step 1 的任务书直接起草正文。
但必须标记 `<!-- source: claude-direct -->` 以便后续区分。

### Step 3：审查

Claude 审查生成的章节，逐项检查：

```
□ 衔接：是否接住了上一章的钩子？
□ 任务：是否完成了章纲目标？
□ 禁区：是否触犯了任何禁区？
□ 角色：是否有 OOC（性格突变/能力矛盾）？
□ 设定：是否与已有设定一致？
□ 伏笔：该推进/回收的伏笔做了没有？
□ 句式：句均长度、短段比是否符合技法要求？
□ 金句：本章是否有至少1句"可截图传播"的金句？
□ 结尾：结尾钩子是否足够让人想翻下一章？
```

每项给出 ✓ / ⚠ / ✗，有 ✗ 的项必须在 Step 4 前修正。

### Step 4：修正 & 归档

- 如有 ✗ 项：Claude 直接修改正文（小修）或重新调用 Pipeline（大修）
- 全部 ✓ 后更新 state.json：
  ```bash
  cd {PANGU_ROOT}
  python -c "
  from pangu_core.config import get_config
  from pangu_core.state_sync import StateSync
  from pangu_core.db import get_db
  # 跑 W5 导出（如果快速模式跳过了）
  print('State synced.')
  "
  ```
- 确认正文文件已写入 `{project}/正文/第{chapter_num}章.txt`

### 失败处理

| 失败点 | 处理 |
|--------|------|
| Step 1 缺文件 | 列出缺失文件，问用户补全 |
| Step 2 API 失败 | 自动降级为方式 B（Claude 直接起草） |
| Step 3 有 ✗ | 小问题 Claude 直接改；大问题调 Pipeline 重生成 |
| 全部失败 | 如实报告，不伪造内容 |
