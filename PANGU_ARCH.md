# 盘古系统（PANGU SYSTEM）架构与调用规范

> 任何代码编写、修改、重构，都必须严格遵守以下规范，否则视为无效实现。

## 1. 核心依赖
- 核心包：`pangu_core.*`（Pipeline/Stages/PromptBuilder/AIClient）
- 数学引擎：`pangu_math.*`（Stats/Signal/Graph/Probability/Optimize）
- 分析层：`pangu_analytics.*`（Economics/Accounting/Control）
- 项目管理层：`pangu_project.*`（Gantt/KPI）
- 配置文件：`.env`（API Keys + Stage路由）

## 2. 写章唯一入口（强制）
所有章节生成必须通过 Pipeline，严禁 Claude 直接写正文：
```bash
python pangu_workshop.py write --project "项目名" --chapter N
```
日志必须出现 `[W2] OK` 和 `[W4] OK`，否则不算调用成功。

## 3. 核心接口
- Pipeline: `pangu_core.pipeline.WritingPipeline`
- Prompt构建: `pangu_core.prompt_builder.PromptBuilder`
- AI调用: `pangu_core.ai_client.call_ai()`
- 情报分析: `pangu_intelligence.analyze_chapter()`
- 策略引擎: `pangu_workshop_smart.SmartStrategyEngine`

## 4. 禁止的操作
- ❌ Claude 直接用 Write 工具写章节正文
- ❌ 绕过 Pipeline 直接调 AI API
- ❌ 不使用 PromptBuilder 手写 system prompt
- ❌ 不使用 pangu_core.rag_engine 做参考检索

## 5. 模式开关
- **工坊模式（默认）**: W0→W1→W2→W3→W4→W5（完整五车间，推荐）
- **快速模式**: W0→W2→W4（跳过W1/W3/W5，仅API异常时使用）
- 切换: `--workshop`（默认） / `--fast`

## 6. 写章完成后必须做的事
1. 验证日志中 `[W2] OK` 和 `[W4] OK`
2. 跑 Pangu 分析：`python pangu_workshop.py review --project "项目名" --chapter N`
3. 检查 KPI：`python pangu_workshop.py status --project "项目名"`
