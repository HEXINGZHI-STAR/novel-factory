# 开门见尸 · 项目规则

## 写章规则（不可违反）

- **严禁直接写正文** — 不得使用 Write 工具直接起草章节
- **唯一入口** — 所有章节必须通过盘古 Pipeline 生成
- **验证标准** — 日志中必须出现 `[W2] OK` 和 `[W4] OK`，否则不算调用成功

## 写章命令

```bash
cd D:\study\近思录\小说\盘古AI && python -c "
from dotenv import load_dotenv; load_dotenv(override=True)
from pangu_core.config import reset_config; reset_config()
from pangu_core.pipeline import WritingPipeline, PipelineConfig
from pangu_workshop_smart import SmartStrategyEngine
from pathlib import Path

proj = Path('projects/开门见尸')
engine = SmartStrategyEngine(proj)
task = engine.generate_chapter_task(N)  # 替换 N 为章号

config = PipelineConfig.from_quick_mode(
    project_dir=str(proj), chapter=N, task=task,
    mode='mystery', platform='qimao',
)
pipeline = WritingPipeline(config)
result = pipeline.run()
if result.success:
    print(f'[OK] {len(result.chapter_content)}字')
"
```

## 项目参数
- 平台: 七猫 (快节奏, 强钩子, 对话≥15%, 段落≤3行)
- 题材: 悬疑
- 模式: W2骨架→W3质检→W4悬疑精修
- 目标: 12章, 30000字
