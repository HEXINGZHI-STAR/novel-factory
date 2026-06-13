---
name: pangu-query
description: 盘古查询——查询项目设定、角色状态、伏笔进度、力量体系、章节元数据
allowed-tools: Read Grep Bash Agent
argument-hint: "[查询主题，如 伏笔/角色/设定/进度/林屿]"
---

# 盘古查询

## 核心理念

**快速检索，不做分析。** 用户问什么就查什么，返回结构化信息。
需要分析时给出简要判断，不做长篇解读。

## 查询类型

### 项目概览

```bash
cd {PANGU_ROOT}
python -c "
import json, sys
from pathlib import Path

state = json.loads(Path('{project}/.webnovel/state.json').read_text(encoding='utf-8'))
pi = state.get('project_info', {})
prog = state.get('progress', {})

print(f'作品: {pi.get(\"title\")}')
print(f'平台: {pi.get(\"platform\")}')
print(f'题材: {pi.get(\"genre\")}')
print(f'进度: 第{prog.get(\"current_chapter\", 0)}章 / 目标{pi.get(\"target_chapters\", \"?\")}章')
print(f'字数: {prog.get(\"total_words\", 0)}字')
print(f'核心卖点: {pi.get(\"core_selling_points\", \"\")}')
print(f'最后更新: {prog.get(\"last_updated\", \"\")}')
"
```

### 角色查询

```
查什么:
- 主角卡基本信息（姓名/年龄/性格/缺陷/OOC警戒）
- 当前状态（位置/能力/与其他角色的关系进展）
- 成长弧进度（在第几阶段？下一节点是什么？）

命令:
  python -c "import json; s=json.load(open('{project}/.webnovel/state.json','r',encoding='utf-8')); print(json.dumps(s.get('characters',{}), ensure_ascii=False, indent=2))"
  
同时读: 设定集/主角卡.md（更详细的角色设定）
```

### 伏笔查询

```
查什么:
- 所有活跃伏笔（status=open）
- 每条伏笔：埋设章、描述、预计回收章
- 紧急度：快到回收章但还没推进的伏笔 ⚠
- 孤儿伏笔：没有回收计划的伏笔

Claude 额外判断:
- 哪些伏笔该在本章推进？
- 哪些伏笔快过期了（距离回收章<3章）？
```

### 设定查询

```
查什么:
- locked_rules: 已锁定的设定，不可改
- 世界观硬约束
- 特定领域规则（力量体系/社会结构/货币等）

读: 设定集/世界观.md + state.json 的 setting_log.locked_rules
```

### 进度查询

```
输出:
- 当前章节号 / 目标章节数
- 各卷完成情况
- 最近5章的写作日期和字数
- 审查通过率
```

## 紧急度分析

当查询伏笔时，Claude 自动附加紧急度判断：

```
🚨 紧急（已过期未回收）: 预计回收章 < 当前章
⚠️ 关注（3章内需回收）: 预计回收章 - 当前章 <= 3
✅ 正常: 其他
```

## 输出格式

查询结果用简洁结构化格式输出，不用长篇叙述。
有数据就列数据，没有就说没有，不编造。
