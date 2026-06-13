---
name: pangu-init
description: 盘古初始化——通过分阶段交互收集创作信息，生成项目骨架、约束文件与写作环境
allowed-tools: Read Write Edit Bash Agent AskUserQuestion
argument-hint: "[项目名] [--from-concept 一句话概念]"
---

# 盘古项目初始化

## 核心理念

**Claude 做创作访谈，不填表。** 通过对话式交互收集创作意图，
由 Claude 将对话内容转化为结构化项目文件。

## 阶段

### 阶段 1：核心概念

Claude 与用户对话，收集：
- 故事一句话（必须能说完）
- 平台选择（知乎盐选/七猫/起点/番茄/晋江）
- 目标字数与章节数
- 核心卖点（读者为什么选这本不看别的？）

产出：写入 `大纲/总纲.md` 的故事一句话 + 核心卖点段。

### 阶段 2：角色

- 主角：姓名、年龄、身份、核心性格（3个词）、缺陷、OOC底线
- 主角的目标与真正渴望
- 关键配角（1-3人）：与主角的关系、独立动机
- 反派/对立力量：不是"坏人"，是"另一种选择"

产出：写入 `设定集/主角卡.md`。

### 阶段 3：世界

根据题材确定世界规则：
- 现实题材 → 时间/城市/行业/社会规则
- 奇幻/仙侠 → 力量体系/等级/代价
- 悬疑 → 规则（有什么不可能的事？违反会怎样？）

产出：写入 `设定集/世界观.md`。

### 阶段 4：结构

Claude 基于前三个阶段引导用户规划结构：
- 卷划分（3-5卷，每卷一个核心冲突）
- 每卷的高潮是什么
- 主角成长弧线（起点→跃迁→蜕变）
- 伏笔表初稿（至少5条主线伏笔）

产出：写入 `大纲/总纲.md` 完整结构段。

### 阶段 5：生成项目

```bash
# 创建项目目录
mkdir -p "{project}/大纲"
mkdir -p "{project}/设定集"
mkdir -p "{project}/正文"
mkdir -p "{project}/审查报告"

# 初始化 state.json
cd {PANGU_ROOT}
python -c "
import json, sys
sys.path.insert(0, '.')
from datetime import datetime

state = {
    'project_info': {
        'title': '{title}',
        'genre': '{genre}',
        'platform': '{platform}',
        'target_words': {target_words},
        'target_chapters': {target_chapters},
        'core_selling_points': '{selling_points}',
        'created_at': '{timestamp}',
    },
    'progress': {
        'current_chapter': 0,
        'total_words': 0,
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    },
    'characters': {},
    'foreshadowing': {'active_threads': []},
    'setting_log': {'locked_rules': []},
    'review_checkpoints': [],
    'chapter_meta': {},
}

state_path = Path('{project}/.webnovel/state.json')
state_path.parent.mkdir(exist_ok=True)
state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Project initialized: {project}')
"
```

### 阶段 6：可选——跑参考书分析

如果用户提供了参考作品名：
```bash
cd {PANGU_ROOT}
python -c "
from knowledge.db_manager import NovelReferenceDB
# 搜参考书 → 分析风格 → 存为项目参考
"
```

## 防劣化规则

- 未完成的阶段不能跳过（可以填"待定"，但不能空着）
- 每个产出文件必须写完整，不使用占位符模板
- `.webnovel/state.json` 必须成功写入，否则项目不完整
